# Models

Strategi model Narathor. Dokumen ini berubah setiap ada model baru, jadi dipisah dari `TECH_STACK.md` dan `AGENTS.md`.

Semua id di bawah adalah id **exact** dari katalog Command Code. Jangan mengarang id.

---

## 1. Prinsip

Satu model untuk semua peran adalah kesalahan ekonomi dan kesalahan mutu. Lima peran punya kebutuhan berbeda:

- Pekerjaan yang bisa dikerjakan heuristik → **jangan pakai model sama sekali**.
- Pekerjaan yang inputnya kecil dan outputnya terstruktur → model murah sudah cukup.
- Pekerjaan yang menentukan mutu produk → satu-satunya tempat kualitas model benar-benar penting.
- Pekerjaan yang menilai kepatuhan → model dengan instruction-following kuat, bukan model dengan prosa terbaik.

---

## 2. Alokasi per peran

| Peran | Model | Id exact | $/1M in/out | Cache read | Alasan |
|---|---|---|---|---|---|
| **Indexer** | tanpa LLM | — | $0 | — | Segmentasi dan deteksi filler murni heuristik: timestamp, regex, jeda. Model tidak menambah apa pun selain biaya. |
| **Curator** | DeepSeek V4.1 Flash | `deepseek/deepseek-v4.1-flash` | $0.15 / $0.60 | $0.003 | Input hanya judul dan deskripsi video. 1M context, murah, cukup. |
| **Matcher** | DeepSeek V4.1 Flash | `deepseek/deepseek-v4.1-flash` | $0.15 / $0.60 | $0.003 | Input besar (kartu segmen lintas video). Cache read $0.003 adalah inti ekonomi sistem ini. |
| **Writer** | DeepSeek V4.1 Flash | `deepseek/deepseek-v4.1-flash` | $0.15 / $0.60 | $0.003 | Keputusan bos: ekonomis dulu. Lihat §4. |
| **Critic** | Claude Haiku 5.5 | `claude-haiku-5-5` | $0.10 / $0.50 | $0.01 | Menilai tujuh gate, bukan menulis prosa. Instruction-following kuat pada harga rendah. |
| **Eval / uji** | Crouton Alpha | `stealth/crouton-alpha` | $0 / $0 | $0 | Iterasi pipeline dan uji tanpa biaya. 1.05M context. |
| **Writer cadangan** | Claude Sonnet 5.5 | `claude-sonnet-5-5` | $2 / $10 | $0.10 | Diaktifkan hanya bila eval membuktikan Writer utama kurang. |

Catatan: `claude-haiku-5-5` dan `claude-sonnet-5-5` memerlukan plan **GOAT** ke atas. `stealth/crouton-alpha` memerlukan **Go** ke atas. Model DeepSeek memerlukan **Go** ke atas.

---

## 3. Biaya satu run penuh

Asumsi: channel 400 video, rata-rata 1 jam, menghasilkan 30 naskah.

| Tahap | Volume | Perkiraan token | Biaya |
|---|---|---|---|
| Indeks pustaka | 400 video × ~8 panggilan | ~2.0M input, 0.3M output | **~$0.30** |
| Thesis clustering | ~8 panggilan batch 50 kartu | ~0.15M | ~$0.02 |
| Combo assembly | 30 tesis × 1 | ~0.45M | ~$0.07 |
| Menulis naskah (2 iterasi) | 30 × 3 panggilan | ~4.2M input, 0.6M output | **~$2.60** |
| Critic | 30 × 1 | ~0.2M | ~$0.10 |
| **Total** | | | **~$3.10** |

**Writer mendominasi ~84% biaya.** Konsekuensi praktis:

- Matcher dan Curator boleh murah tanpa ragu.
- Hanya keputusan model Writer yang signifikan secara ekonomi.
- Menurunkan biaya Writer 10× hanya menghemat $2.3 dari $3.1. Tidak sepadan bila mutunya jatuh.

Dengan cadangan Sonnet 5.5, total naik ke **~$35 per run**. Untuk 30 naskah siap produksi, itu masih wajar — tapi keputusannya harus berbasis eval, bukan rasa.

---

## 4. Writer: ekonomis dulu, dengan penutup risiko

Model murah menulis prosa Indonesia yang cenderung datar dan berpola. Itu risiko nyata terhadap standar kriya.

Karena itu beban mutu **dipindahkan dari model ke struktur**:

1. **Few-shot di prompt.** `docs/CRAFT.md` memuat 3–5 naskah emas. Contoh konkret menaikkan keluaran Writer murah lebih besar daripada menaikkan kelas model tanpa contoh.
2. **Critic punya gigi.** Naskah datar dikembalikan, bukan diterima. Maks dua iterasi, lalu `interrupt()` ke bos.
3. **Model bisa diganti satu baris.** `MODEL_WRITER=claude-sonnet-5-5`. Tanpa ubah kode.
4. **Eval harness dibangun di fase 7**, bukan fase 8, supaya keputusan ganti model berbasis data.
5. **Perbandingan A/B wajib** sebelum keputusan. Protokol di §6.

**Plafon realistis dengan Writer termurah: rapi dan jelas, belum tentu berkilau.** Itu konsekuensi yang diterima secara sadar, dan eval akan mengukurnya — bukan menyembunyikannya.

---

## 5. Override

Berlapis, dari paling spesifik ke paling umum:

```bash
# per peran
MODEL_WRITER=claude-sonnet-5-5
MODEL_MATCHER=deepseek/deepseek-v4.1-flash
MODEL_CRITIC=claude-haiku-5-5
MODEL_CURATOR=deepseek/deepseek-v4.1-flash

# override borongan (mengikuti pola referensi)
MODEL_NAME=stealth/crouton-alpha
```

Aturan:

- `MODEL_NAME` menimpa semua peran sekaligus; berguna untuk uji gratis.
- Variabel per peran menang atas `MODEL_NAME`.
- Tanpa override apa pun, nilai default di §2 berlaku.
- Reasoning effort: low untuk semua peran kecuali Writer (medium). Model tanpa dukungan effort tidak diberi parameter itu.
- Override dicatat di `run.json`. Run yang tidak mencatat model tidak dapat direproduksi.

---

## 6. Protokol ganti Writer

Jangan ganti berdasarkan kesan. Ikuti ini:

1. Ambil 10 `Combo` yang sama. Jalankan Writer kandidat dan Writer cadangan pada input identik.
2. Hasilkan 10 naskah dari masing-masing.
3. Nilai dengan `narathor eval` pada metrik yang sama: `craft_pass_rate`, `citation_violation_rate`, `hook_payoff_violation_rate`.
4. Baca kesepuluh pasang naskah tanpa tahu mana yang mana. Pilih yang lebih baik per pasangan.
5. Kalau kandidat menang di ≥ 7 dari 10 dan `craft_pass_rate` lebih tinggi → ganti. Selain itu → pertahankan.
6. Catat hasilnya di `docs/STATUS.md` tabel perbandingan.

Tanpa langkah 4 (uji buta), keputusan akan dipengaruhi merek model, bukan mutu keluaran.

---

## 7. Reasoning effort & parameter

| Peran | Effort | Catatan |
|---|---|---|
| Curator | low | Klasifikasi; kedalaman tidak membantu |
| Matcher | low | Perakitan; kedalaman membantu pada combo rumit, tapi tidak default |
| Writer | medium | Satu-satunya tempat kedalaman berpengaruh pada mutu prosa |
| Critic | low | Penilaian gate; instruksi eksplisit lebih penting daripada penalaran dalam |
| Eval | off | Uji pipeline; tidak menilai mutu |

`max_retries=0` di level client. Retry ditangani `ModelRetryMiddleware`, bukan SDK.

---

## 8. Yang tidak boleh

- Mengarang id model. Semua id di dokumen ini berasal dari katalog.
- Memakai model mahal untuk peran yang bisa heuristik (Indexer).
- Memakai model murah untuk Critic. Critic yang longgar membuat seluruh gate kehilangan arti.
- Mengganti model tanpa eval.
- Menyembunyikan model yang dipakai. Setiap `run.json` mencantumkan model per peran.
- Memakai model berbeda antara run produksi dan run eval pada metrik yang dibandingkan.
