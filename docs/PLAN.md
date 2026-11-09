# Plan

Rencana pembangunan Narathor. Dicentang hanya bila sudah diverifikasi. Yang masih kosong menunggu pustaka nyata atau keputusan bos.

Mengikuti `docs/PROCESS.md`: setiap fase punya success criteria yang dapat diverifikasi sendiri. Centang saat lulus, perbarui `docs/STATUS.md`, lalu commit.

---

## Apa yang dibangun

Mesin yang bekerja pada pustaka video satu channel dan menghasilkan naskah short: mengindeks segmen, mengombinasikan segmen dari video berbeda menjadi satu alur, menulis naskah penuh, dan menilai karyanya sendiri.

Keluaran: **naskah dan timestamp**, bukan video.

---

## Arsitektur

```
                    ┌──────────────────────────────┐
                    │  CLI  uv run -m narathor     │
                    └──────────────┬───────────────┘
                                   │ HTTP JSON
┌──────────────┐        ┌──────────▼───────────┐        ┌──────────────┐
│ data/ (read  │─seed──►│  backend/            │◄──────►│ SQLite /     │
│  only)       │        │  FastAPI + SQLAlchemy│        │ Postgres     │
└──────────────┘        └──────────▲───────────┘        └──────────────┘
                                   │ satu-satunya pintu
                        ┌──────────┴───────────┐
                        │  agent/              │
                        │  LangGraph           │──► Command Code Provider API
                        │  supervisor + 5 peran│──► Langfuse (opsional)
                        └──────────────────────┘
```

Backend adalah satu-satunya pintu ke data. Agent memanggil API, tidak membaca `data/` dan tidak menyentuh database.

---

## Data dan state

- `data/` read-only. Backend menyemainya ke database saat pertama jalan.
- `data/eval/` tidak pernah dibuka agent, test, atau tooling. Hanya `narathor eval`.
- Database menyimpan state yang berubah: segmen, combo, naskah, audit, run, panggilan model.
- File SQLite dapat dihapus untuk reset. Tidak ada kode migrasi.

### Status unit kerja

| Status | Arti |
|---|---|
| `pending` | Belum dikerjakan |
| `running` | Sedang dikerjakan |
| `done` | Selesai, hasil tersimpan |
| `returned` | Dikembalikan Critic, menunggu iterasi |
| `deferred` | Gagal dua kali, dilaporkan di akhir |
| `blocked` | Dibuang karena pelanggaran soul atau nilai terlarang |

---

## Fase

### Fase 1: Backend sisi baca

Bangun fondasi: database, seed, dan endpoint baca.

- `backend/db.py`: SQLAlchemy Core, schema `narathor`, seed dari `data/` saat tabel kosong.
- Tabel: `channels`, `videos`, `transcripts`.
- Endpoint: `/api/health`, `/api/soul`, `/api/briefs`, `/api/briefs/{id}`, `/api/videos`, `/api/videos/{id}`.
- Setiap operasi punya `operation_id`, docstring satu baris, tanpa input opsional.
- Fixture database sementara untuk test.

**Success criteria:**

- [x] `uv run pytest backend -q` lulus, tanpa panggilan model.
- [x] `GET /api/videos` mengembalikan seluruh video dari `data/`, dengan `video_id`, `title`, `duration_s`.
- [x] `GET /api/videos/VID-9999` mengembalikan 404 dengan pesan yang menyebut id yang dicari.
- [x] `GET /api/soul` mengembalikan `{version, sha256, ok}` dan `ok: false` bila `SOUL.md` diubah satu byte.
- [x] Menghapus file SQLite lalu restart menyemai ulang.

---

### Fase 2: Soul dan brief enforcement

Bangun penegakan konstitusi dan validasi brief. Ini sebelum fitur apa pun yang memanggil model.

- `soul/verify.py`: hash check, `SoulCheck`.
- `narathor soul verify`, `narathor soul bump`.
- `soul check` dijalankan implisit di awal setiap request backend.
- `briefs/load.py`: parser YAML + validasi schema.
- Validator dua lapis: aturan deterministik, lalu Soul Guard lapis B (model judge).
- `narathor narrative new`, `narathor narrative check`.

**Success criteria:**

- [x] Mengubah `SOUL.md` satu byte → semua endpoint mengembalikan 409, tidak ada artefak ditulis.
- [x] `soul bump` menaikkan `version` dan memindahkan hash lama ke `previous_versions[]`.
- [x] Brief tanpa `learning_outcome` → 400, pesan menyebut field.
- [x] Brief tanpa `seasonal_context.as_of` → 400.
- [x] Brief dengan `values_blocked` yang bertabrakan `values_allowed` → 400.
- [x] Brief ambigu → 400 dengan alasan yang menyebut bagian ambigunya.
- [x] Brief melanggar Pasal 4 (`tone` meminta menunda payoff) → 400 menyebut pasal.
- [x] Brief valid lolos ketiga lapis.
- [x] Tidak ada artefak di `output/` setelah penolakan.

---

### Fase 3: Ingest pustaka

Ambil transkrip dari setiap video di pustaka.

- `ingest/captions.py`: `youtube-transcript-api`, jalur cepat.
- `ingest/whisper.py`: `faster-whisper`, fallback bila caption tidak ada atau kualitas buruk.
- Normalisasi ke `TranscriptDoc {video_id, language, source, segments[]}` dengan `Segment {t0, t1, text, words[]}`.
- Cache transkrip berdasarkan `video_id` + hash audio.

**Success criteria:**

- [ ] Lima video pertama punya transkrip dengan timestamp per segmen.
- [ ] Rerun tanpa `--force` menghasilkan cache hit: tidak ada unduhan ulang, tidak ada transkripsi ulang.
- [x] Video tanpa caption memakai Whisper, dan `source: "whisper"` tercatat.
- [x] Video tanpa audio dapat diunduh ditandai `skipped` di `run.json`, run lanjut.
- [x] `run.json` memuat `source` per video dan total waktu ingest.

---

### Fase 4: Indexer

Segmentasi dan fitur, tanpa LLM.

- `index/segmenter.py`: pecah transkrip pada jeda > 0.8s dan penanda kalimat.
- `index/features.py`: `filler_positions`, `dead_air_spans`, `has_setup_preamble`, `word_count`, `wpm`, `hook_archetype` (heuristik awal), `payoff_present`, `niche_consistency_score`.
- `index/kinds.py`: klasifikasi `kind` — thesis, story, number, rebuttal, close.
- Simpan `Segment` card ~200 token ke tabel `segments`.

**Success criteria:**

- [x] Setiap video menghasilkan minimal 5 segmen ber-`kind`.
- [x] Tidak ada segmen > 70 detik atau < 4 kata.
- [x] Filler `jadi gini`, `apa ya`, `oke guys` terdeteksi pada transkrip uji.
- [x] Segmen yang dibuka `sebelum itu` mendapat `has_setup_preamble: true` dan penalti terukur.
- [x] Ukuran rata-rata kartu segmen ≤ 250 token.
- [x] `uv run pytest index -q` lulus tanpa jaringan.

---

### Fase 5: Matcher dan konkurensi

Bangun supervisor, fan-out `Send`, dan Matcher.

- `agent/graph.py`: `StateGraph`, node `curator`, `index`, `match`.
- Fan-out lewat `Send` per unit.
- `max_concurrency` dari config; backend menolak unit di atas batas.
- `agent/matcher.py`: rakit `Combo` dari `SegmentCard[]`.
- `agent/state.py`: state bersama, idempoten per `unit_key`.

**Success criteria:**

- [x] Stub test: N video menghasilkan N unit `index` yang berjalan.
- [x] Jumlah unit berjalan bersamaan tidak pernah melebihi `max_concurrency` — diukur dari log, bukan asumsi.
- [x] `--concurrency 3` menurunkan batas dan terbukti di log.
- [x] Setiap `Combo` memuat minimal 2 `video_id` berbeda; combo dengan satu video ditolak.
- [x] Combo dengan segmen yang saling membantah ditolak seluruhnya, bukan dipilih salah satu.
- [x] Satu unit gagal tidak menghentikan run; run menyelesaikan unit lain.
- [x] Retry berjalan pada error provider; gagal dua kali → `deferred`.
- [x] `uv run pytest agent -q` lulus tanpa memanggil model.

---

### Fase 6: Writer

Tulis naskah penuh dengan sitasi.

- `agent/writer.py`: prompt dengan brief, segmen penuh, few-shot dari `docs/CRAFT.md`.
- Keluaran `ShortScript` sesuai schema.
- Setiap `is_claim: true` wajib membawa `citation`.
- Backend mencocokkan `quote` ke transkrip sebelum menyimpan.
- `discarded[]` wajib diisi.

**Success criteria:**

- [x] 30 `ShortScript` valid terhadap schema.
- [x] Setiap `beat` dengan `is_claim: true` punya `citation` dengan empat field.
- [x] `quote` pada setiap sitasi ditemukan di transkrip pada rentang `t0..t1`.
- [x] Klaim tanpa sitasi → 400, naskah tidak tersimpan.
- [x] `hook` ≤ 7 kata pada semua naskah yang lolos.
- [x] `payoff_at_s` < 16 untuk target 13–20s.
- [x] `overlay` ≤ 7 kata per baris.
- [x] `single_minded_proposition` dapat diringkas satu kalimat.

---

### Fase 7: Critic, durabilitas, dan eval

Tujuh gate, checkpointer, dan pengukuran.

- `agent/critic.py`: tujuh gate, keluaran `Audit`.
- Gagal gate → `returned` ke Writer, maks 2 iterasi.
- Lewat 2 iterasi → `interrupt()`.
- Checkpointer sinkron; resume setelah kill.
- `eval/`: golden set, `precision@10`, `citation_violation_rate`, `soul_violation_rate`, `craft_pass_rate`, `hook_payoff_violation_rate`.

**Success criteria:**

- [x] Naskah generik (lolos uji tukar) dikembalikan Critic, bukan diterima.
- [x] Naskah dengan payoff yang tidak membayar hook dikembalikan.
- [ ] Setelah 2 iterasi gagal, graf berhenti dan menunggu keputusan bos.
- [ ] Run di-kill di tengah lalu dijalankan ulang: melanjutkan dari node terakhir, `attempts` tidak bertambah, `thread_id` sama.
- [ ] `narathor eval` mengeluarkan kelima metrik.
- [x] `citation_violation_rate = 0` dan `soul_violation_rate = 0` pada golden set.
- [x] Test eval memakai `stealth/crouton-alpha` atau stub, bukan model berbayar.

---

### Fase 8: CLI, perbandingan Writer, handover

- `narathor init`, `doctor`, `ingest`, `index`, `mine`, `script`, `report`, `eval`, `status`.
- `narathor doctor`: cek API key, database, soul, versi model.
- Laporan `index.md`, `blocked.md`, `run.json`.
- Protokol A/B Writer dari `docs/MODELS.md` §6 dijalankan pada 10 naskah.

**Success criteria:**

- [x] `narathor doctor` melaporkan lima pemeriksaan dengan status jelas.
- [ ] Run penuh dari channel 25 video menghasilkan naskah, `index.md`, dan `run.json`.
- [x] `run.json` memuat `soul_version`, `brief_hash`, model per peran, biaya perkiraan.
- [ ] `blocked.md` memuat segmen yang dibuang beserta pasal yang dilanggar.
- [ ] Tabel A/B Writer terisi di `docs/STATUS.md`, dengan keputusan dan alasannya.
- [x] `uv run check` hijau dengan `.env` disingkirkan.
- [x] `git status` bersih.

---

## Di luar scope

Ditulis di sini agar tidak dikerjakan tanpa diminta:

- Dashboard web.
- Render `.mp4`, burn caption, crop 9:16.
- Auto-posting ke platform.
- Login dan multi-pengguna.
- Montage lintas channel.
- Penjaminan viral.

---

## Risks

| Risiko | Mitigasi |
|---|---|
| **Writer murah menghasilkan prosa datar** | Few-shot di prompt, Critic ber-gigi, eval di fase 7, model dapat diganti satu baris |
| **Matcher kehabisan context pada pustaka besar** | Tiga tahap indeks; kartu 200 token; retrieval per tesis |
| **Biaya meledak pada pustaka 400 video** | Cache `unit_key`, cache read murah, cap panggilan model per unit |
| **Sitasi dipalsukan model** | Backend mencocokkan `quote` ke transkrip; Writer tidak dipercaya |
| **Combo dipaksakan agar terlihat pintar** | Aturan non-kontradiksi dan satu tesis; combo buruk dibuang utuh |
| **Dua proses menulis unit yang sama** | Satu proses agent pada satu waktu; checkpointer mencegah tumpang tindih |
| **Windows: checkpointer async tidak jalan** | Checkpointer sinkron |
| **`.env` bocor ke test** | Test menyingkirkan `.env`; `uv run check` dijalankan dengan `.env` disingkirkan |
| **Godaan menambah blacklist frasa** | Dilarang oleh keputusan bos; diganti tiga uji khas |
