# Agents

Lima peran, satu graf, dan mekanisme konkurensi yang mengaturnya.

Dokumen ini menjawab dua pertanyaan yang sering tertinggal: **di mana bagian yang mengatur lima agent bekerja bersamaan**, dan **framework apa yang dipakai**.

---

## 1. Framework

| Lapisan | Teknologi | Peran |
|---|---|---|
| Orkestrasi peran | **LangGraph `StateGraph`** | Graf lima node, state bersama, edge kondisional |
| Fan-out paralel | **LangGraph `Send`** | Mengirim N unit kerja ke node yang sama secara paralel |
| Batas konkurensi | **`max_concurrency`** di config invoke | Menegakkan maksimal 5 unit berjalan bersamaan |
| Durabilitas | **LangGraph checkpointer** (sinkron) | Simpan state tiap node; resume setelah crash |
| Persetujuan manusia | **LangGraph `interrupt()`** | Berhenti saat Critic borderline, lanjut setelah bos memutuskan |
| Supervisor | **LangChain `create_agent`** | Merencanakan urutan kerja, memilih unit, meringkas |
| Tracing | **Langfuse** (opsional) | Satu session per run, satu span per peran |
| Model | **Command Code Provider API** via LangChain | Lihat `docs/MODELS.md` |

Semua panggilan model lewat LangChain chat model, bukan subprocess CLI. Pemilihannya ada di `agent/models.py` dan dapat diganti per peran lewat environment.

---

## 2. Lima peran

| Peran | Lingkup | Input | Output | Model |
|---|---|---|---|---|
| **Curator** | channel + brief | `NarrativeBrief`, daftar video | `VideoSelection[]` + alasan | LLM murah |
| **Indexer** | per video | `TranscriptDoc` | `Segment[]` + `kind` + fitur | **tanpa LLM** |
| **Matcher** | per tesis kandidat | `SegmentCard[]` lintas video | `Combo[]` (2–5 segmen, ≥2 video) | LLM murah |
| **Writer** | per `Combo` | combo, segmen penuh, brief, `CRAFT.md` | `ShortScript` + sitasi | LLM (lihat `MODELS.md`) |
| **Critic** | per `ShortScript` | script, transkrip, soul, 7 gate | `Audit {gates, cites_ok, verdict, pressed[], reason}` | LLM instruction-following |

### 2.1 Curator

Menentukan video mana yang masuk lingkup, dan mengapa. Memberi `niche_consistency_score` — seberapa konsisten topik video dengan tesis brief.

Peran ini lebih penting daripada perkiraan awal. Karena naskah dibangun dari ucapan sumber, memilih pustaka yang tepat adalah keputusan kriya paling berpengaruh, jauh sebelum satu kalimat ditulis.

### 2.2 Indexer

**Tidak memanggil model.** Segmentasi transkrip dan perhitungan fitur sepenuhnya heuristik:

- pembagian pada jeda > 0.8s dan penanda kalimat
- deteksi filler (`jadi gini`, `apa ya`, `gimana ya`, `oke guys`)
- deteksi pembuka administratif (`sebelum itu`, `di video kali ini`)
- `kind`: thesis, story, number, rebuttal, close
- ekstraksi `key_quote` per segmen

Keluaran: `Segment` card ringkas ~200 token, disimpan di database. Inilah yang membuat skala 400 video mungkin.

### 2.3 Matcher

Menemukan kombinasi. Satu unit kerja = satu tesis kandidat.

Aturan yang ditegakkan (bukan diharapkan):

- minimal 2 video berbeda
- tidak boleh kontradiksi antar segmen
- satu tesis
- urutan mendukung alur klaim → bukti → konsekuensi → penutup
- keragaman sumber dinilai

### 2.4 Writer

Menulis naskah penuh di atas satu `Combo`: hook, beats, payoff, overlay, title, caption.

Kewajiban:

- setiap `beat` dengan `is_claim: true` membawa `citation {video_id, t0, t1, quote}`
- `quote` wajib **benar-benar ada** di transkrip pada rentang itu
- `hook` ≤ 7 kata, kata pertama sebelum detik 1
- `payoff_at_s` < 16 untuk target 13–20s
- `overlay` ≤ 7 kata per baris
- menandai apa yang **tidak** dipakai (`discarded[]`)

### 2.5 Critic

Menjalankan tujuh gate dari `docs/CRAFT.md` §6. Gagal satu → kembalikan ke Writer. Maks dua iterasi, lalu `interrupt()`.

Critic juga memverifikasi sitasi secara independen. Writer yang menyatakan sitasi valid tidak dipercaya begitu saja; backend mencocokkan, Critic memeriksa kewajaran kutipan terhadap klaim.

---

## 3. Graf

```
                    ┌────────────┐
                    │ supervisor │  (create_agent)
                    └──────┬─────┘
                           │ Send per unit
        ┌──────────┬───────┴────────┬───────────┐
        ▼          ▼                ▼           ▼
   ┌─────────┐ ┌────────┐     ┌────────┐  ┌────────┐
   │ curator │ │ index  │     │ match  │  │ write  │
   └────┬────┘ └───┬────┘     └───┬────┘  └───┬────┘
        │          │              │            │
        └──────────┴──────────────┴────────────┘
                           │
                    ┌──────▼─────┐
                    │  critique  │
                    └──────┬─────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           lolos      kembalikan    interrupt
           (END)      (→ write)     (tunggu bos)
```

Node `index`, `match`, `write`, dan `critique` adalah target `Send`. Satu node dapat menerima N unit sekaligus — di sinilah paralelisme terjadi.

---

## 4. Konkurensi — spesifikasi eksplisit

### 4.1 Fan-out

```python
# supervisor memutuskan unit, bukan menjalankan loop
sends = [Send("index", {"video_id": v}) for v in selected_videos]
```

Tidak ada `for` yang menunggu satu per satu. Tidak ada `asyncio.gather` buatan sendiri.

### 4.2 Batas

```python
graph.invoke(state, config={"max_concurrency": 5})
```

- Default **5**. Dapat diubah: `--concurrency N` atau `MAX_CONCURRENCY`.
- Backend menolak `Send` yang membuat unit berjalan melebihi batas. Ini invarian, bukan harapan.
- Nilai 0, negatif, atau tak hingga → ditolak saat startup.

**Mengapa 5.** Cukup untuk menutupi latensi model, cukup rendah agar biaya per menit terkendali, dan cukup kecil agar log tetap terbaca saat debug.

### 4.3 Thread per unit

| Peran | `thread_id` |
|---|---|
| Indexer | `{narrative_id}:{video_id}` |
| Matcher | `{narrative_id}:thesis-{n}` |
| Writer | `{narrative_id}:combo-{combo_id}` |
| Critic | `{narrative_id}:combo-{combo_id}` |

Thread stabil → resume menemukan state yang sama. Writer dan Critic berbagi thread karena Critic harus melihat riwayat iterasi.

### 4.4 Idempotensi

Kunci unit:

```
unit_key = hash(unit_id, prompt_version, brief_hash, soul_version, craft_version)
```

Node yang dijalankan ulang setelah crash tidak menggandakan biaya atau data. Hasil yang sudah ada dengan `unit_key` sama dikembalikan dari cache.

Konsekuensi yang disengaja: **ganti soul atau brief menginvalidasi seluruh cache.** Naskah dari konstitusi berbeda tidak boleh dipakai ulang seolah sah.

### 4.5 Durabilitas

Checkpointer menyimpan state setelah setiap node. Run yang dibunuh:

- dilanjutkan pada node terakhir yang selesai
- **tidak** menambah `attempts`
- memakai `thread_id` yang sama

Sinkron, bukan async. Checkpointer async Postgres tidak bekerja dengan event loop bawaan Windows.

### 4.6 Cap panggilan model

| Peran | Maks panggilan per unit |
|---|---|
| Curator | 1 |
| Indexer | 0 |
| Matcher | 1 |
| Writer | 3 (tulis + maks 2 revisi) |
| Critic | 1 |

Lewat cap → node gagal terkontrol. Bukan loop, bukan diam-diam berhenti. Dihitung di tabel `agent_calls`.

### 4.7 Retry

`ModelRetryMiddleware`, satu retry untuk error provider atau timeout. Gagal dua kali → unit ditandai `deferred`, run lanjut. Unit yang `deferred` dilaporkan di akhir, tidak menghentikan run.

### 4.8 Isolasi kegagalan

Satu unit gagal tidak menghentikan run. Run menyelesaikan unit lain, lalu melaporkan:

```
selesai: 27   dikembalikan: 2   ditunda: 1
```

### 4.9 Merge deterministik

Hasil digabung dengan sort `script_id`, bukan urutan kedatangan. Dua run dengan input sama menghasilkan urutan sama.

---

## 5. Batas skala

400 video × 1 jam ≈ **5 juta token** transkrip. Tidak muat di context 1M mana pun, termasuk yang terbesar di katalog.

Karena itu matching tiga tahap:

**Tahap 1 — kartu segmen.** Indexer menghasilkan ~200 token per segmen, ~10 segmen per video. 400 video → ~800.000 token tersimpan di database, bukan di context.

**Tahap 2 — klaster tesis.** Batch 50 kartu per panggilan. Model murah membaca kartu, bukan transkrip. Menghasilkan 30–50 tesis kandidat.

**Tahap 3 — rakit combo.** Untuk satu tesis, ambil hanya segmen relevan (berdasarkan `topic` dan `kind`). Writer menerima 2–5 segmen penuh, bukan seluruh pustaka.

Tanpa tiga tahap ini, Matcher gagal karena context penuh dan biaya meledak secara kuadratik.

---

## 6. Invarian yang ditegakkan backend

Prompt bisa diabaikan model. Endpoint tidak bisa.

| Invarian | Kapan diperiksa | Akibat pelanggaran |
|---|---|---|
| Soul hash cocok | Awal **setiap** request agent | 409, agent berhenti |
| Brief valid, tidak ambigu, tidak kedaluwarsa | Sebelum run dibuat | 400 + pasal |
| `values_blocked` tidak bocor | Saat menyimpan `ShortScript` | 400, naskah dibuang |
| Setiap `is_claim` punya sitasi valid | Saat menyimpan | 400, naskah ditolak |
| `quote` benar-benar ada di transkrip | Saat menyimpan | 400, naskah ditolak |
| `payoff_pays_off` | Saat menyimpan | 400, dikembalikan ke Writer |
| Tujuh gate kriya | Saat menyimpan | 400, dikembalikan |
| Tidak ada naskah ganda | Saat menyimpan | Idempoten, 200 |
| Concurrency ≤ batas | Saat `Send` | Tolak unit |
| Cap panggilan model | Setiap panggilan | Tolak, tandai gagal |

---

## 7. Testing tanpa model

Wajib. Tidak ada test yang memanggil model nyata.

Stub model per peran mengembalikan respons skrip. Yang dibuktikan:

1. Fan-out menghasilkan N unit sesuai jumlah `Send`.
2. `max_concurrency` tidak pernah terlampaui — diukur dari jumlah unit berjalan bersamaan di log, bukan dari asumsi.
3. Retry berjalan pada error provider, lalu unit jadi `deferred`.
4. `interrupt()` menghentikan graf dan melanjutkannya saat resume.
5. Unit gagal tidak menghentikan run.
6. Gate sitasi menolak klaim tanpa rujukan.
7. Gate khas menolak naskah yang bisa ditukar dengan short lain.

Test berjalan tanpa jaringan. Kalau sebuah test butuh jaringan, test itu salah rancang.

---

## 8. Yang tidak boleh

- Mengganti fan-out `Send` dengan loop sekuensial.
- Menjalankan `max_concurrency` tanpa batas.
- Menyimpan hasil sebelum backend memverifikasi sitasi.
- Membiarkan agent membaca `data/` atau database langsung.
- Memakai model berbeda antara uji dan produksi pada metrik yang dibandingkan.
- Membuat worker baru di luar lima peran tanpa memperbarui dokumen ini lebih dulu.
- Menunda soul check sampai setelah naskah ditulis.

---

## 9. Hubungan dengan dokumen lain

| Dokumen | Hubungan |
|---|---|
| `SOUL.md` | Diperiksa di awal setiap request |
| `docs/CRAFT.md` | Tujuh gate yang dijalankan Critic |
| `docs/MODELS.md` | Model per peran dan cara override |
| `docs/NARRATIVE.md` | Brief yang dibaca Curator dan Writer |
| `docs/TECH_STACK.md` | Bagian sistem dan API |
| `docs/PLAN.md` | Urutan pembangunan |
