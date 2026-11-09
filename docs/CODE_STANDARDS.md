# Code Standards

Aturan main untuk semua kode di repo ini. Mengikuti `00. Plan Build References/CODE_STANDARDS.md`, dengan tambahan yang khas Narathor.

---

## Umum

1. **Sederhana dulu.** Jangan mengabstraksi sampai ada dua pemakai nyata, bukan dua pemakai yang dibayangkan.
2. **Komentar hanya bila perlu.** Kode yang butuh komentar untuk dipahami biasanya butuh nama yang lebih baik.
3. **Ringkas.** README pendek. Tanpa emoji di kode, commit, maupun dokumen teknis.
4. **Hindari defensive berlebih.** Tangani exception di batas sistem (input pengguna, API luar, filesystem). Percayai kode internal sendiri.
5. **Selalu `uv run`.** Jangan pernah `python3` atau `python` langsung.
6. **TypeScript strict, tanpa `any`.** Berlaku saat dashboard dibangun (Fase 2).

---

## Khas Narathor

7. **Tidak ada perilaku bertema di kode.** Kalau muncul `if channel == "..."` atau daftar nilai hardcoded, itu bug. Pindahkan ke Narrative Brief.
8. **Soul bukan variabel.** Jangan pernah menaruh isi soul, hash-nya, atau jalur bypass-nya di kode yang dapat diubah lewat config.
9. **Invarian ditegakkan di backend, bukan di prompt.** Prompt bisa diabaikan model. Endpoint tidak bisa.
10. **Setiap operasi API punya `operation_id`, docstring satu baris, dan tanpa input opsional.** Mengikuti `docs/TECH_STACK.md`.
11. **Test tidak pernah memanggil model.** Gunakan stub model. Tidak ada pengecualian.
12. **Jangan membaca `data/eval/`.** Folder itu answer key. Agent, test, dan tooling tidak menyentuhnya.
13. **Prompt adalah kode.** Prompt disimpan di `prompts/` dengan `prompt_version`, dan perubahan prompt wajib disertai eval.
14. **Cache key wajib memuat versi.** `unit_id + prompt_version + brief_hash + soul_version + craft_version`. Cache tanpa versi menghasilkan keluaran basi yang tampak sah.

---

## Python

- Python 3.12, dikelola `uv`.
- Pydantic v2 untuk semua kontrak data. Model kontrak ada di satu tempat, bukan tersebar.
- `ruff` untuk lint dan format; `pyright` untuk tipe.
- Fungsi murni dipisah dari yang menyentuh I/O. Segmentasi transkrip, perhitungan fitur, dan pemeriksaan gate harus dapat diuji tanpa database, tanpa jaringan, tanpa model.
- Tidak ada `time.sleep` di kode aplikasi. Retry memakai middleware.
- Path selalu lewat `pathlib`. String path yang dirangkai manual adalah bug di Windows.

---

## Konkurensi

- Fan-out memakai `Send` dari LangGraph, bukan loop `asyncio` buatan sendiri.
- `max_concurrency` **selalu** eksplisit. Default 5. Tidak pernah tak terbatas.
- Setiap unit kerja idempoten. Node yang dijalankan ulang setelah crash tidak boleh menggandakan biaya atau data.
- Merge hasil deterministik: sort by `script_id`, bukan urutan kedatangan.
- Satu unit gagal tidak boleh menghentikan run.

---

## Error

- Gagal karena pelanggaran soul atau sitasi → **berhenti**, bukan lanjut dengan peringatan.
- Gagal karena provider/timeout → retry sekali, lalu `deferred`, run lanjut.
- Gagal karena input buruk (video tidak punya audio, transkrip kosong) → `skipped`, dicatat di `run.json`, run lanjut.
- Pesan error menyebut apa yang salah dan apa yang harus dilakukan. "Error 400" bukan pesan.

---

## Yang tidak boleh

- `git commit --no-verify`.
- Menurunkan threshold, mematikan aturan, atau mengecualikan file agar pemeriksaan hijau.
- Menambah flag bypass untuk soul, sitasi, atau gate kriya.
- Menyimpan secret di repo. Semua lewat `.env`, dan `.env` masuk `.gitignore`.
- Menulis artefak tanpa `run.json`.
