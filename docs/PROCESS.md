# Process

Cara kerja di repo ini. Mengikuti `00. Plan Build References/PROCESS.md`, disesuaikan dengan Narathor.

---

## Setup

```bash
uv sync
```

Dependency Python ada di `pyproject.toml` root. Pada Fase 2 ditambah `npm install` untuk dashboard.

---

## Pemeriksaan

```bash
uv run check
```

Menjalankan: ruff (lint + format), pyright, pytest dengan coverage minimal 80%.

Pada Fase 2 ditambah: Prettier, ESLint, tsc, vitest, dan Playwright.

Hook pre-commit menjalankan format, lint, type check, dan unit test pada setiap commit.

---

## Planning

Saat diminta merencanakan — misalnya "tolong rencanakan pilot" — tulis rencana ke `docs/PLAN.md` dan **jangan menulis kode**.

Cara menyusun:

1. Bagi pekerjaan menjadi fase, biasanya 5 sampai 8, masing-masing dibangun di atas fase sebelumnya.
2. Setiap fase punya success criteria detail yang dapat kamu verifikasi sendiri: test yang lulus, perintah dan keluarannya, panggilan API dan responsnya, file yang dihasilkan dan isinya.
3. Tulis setiap criteria sebagai checkbox.
4. Berhenti. Tunggu sampai diminta mengimplementasikan.

Rencana yang tidak bisa diverifikasi sendiri bukan rencana; itu niat.

---

## Implementing

Saat diminta mengimplementasikan, bangun setiap fase berurutan **tanpa berhenti**. Untuk setiap fase:

1. Bangun, dengan test.
2. Periksa setiap success criterion dan perbaiki yang gagal.
3. Centang criteria di `docs/PLAN.md` dan perbarui `docs/STATUS.md`.
4. Commit. Hook pre-commit menjalankan pemeriksaan; kalau gagal, perbaiki dan commit lagi.

Setelah fase terakhir: jalankan `uv run check` dan laporkan hasilnya.

---

## Rules

- **Tambahkan test pada setiap perubahan.** Test tidak pernah memanggil model; gunakan stub model.
- **Jangan pernah membaca `data/eval/`.** Folder itu kunci jawaban. Agent, test, dan tooling tidak menyentuhnya.
- **Jalankan `uv run check` sebelum menyerahkan pekerjaan.**
- **Jangan pernah memakai `git commit --no-verify`.**
- **Jangan pernah menurunkan threshold, mematikan aturan, atau mengecualikan file** agar pemeriksaan hijau. Kalau sebuah aturan terasa salah, berhenti dan tanyakan.
- **Jaga `docs/STATUS.md` tetap benar.**
- **Jangan push.**
- **Semua harus jalan di Windows.** Script lewat `uv run` atau file `.mjs`.
- **Soul tidak disentuh.** Tidak ada task yang boleh mengubah `SOUL.md` atau `soul.lock` kecuali `soul bump` eksplisit yang disetujui bos.
- **Spec dulu, kode kemudian.** Perubahan perilaku → perbarui `docs/SPEC.md` lebih dulu.
- **Tidak ada tema di kode.** `if channel == "..."` atau daftar nilai hardcoded adalah bug. Pindahkan ke brief.
- **Prompt adalah kode.** Simpan di `prompts/` dengan `prompt_version`; perubahan prompt wajib disertai eval.

---

## Urutan kerja per task

1. Baca task.
2. Baca bagian spec yang terkait — jangan menebak.
3. Tulis test lebih dulu.
4. Implementasikan.
5. Jalankan `uv run check`.
6. Perbarui `docs/STATUS.md`.
7. Commit.

Melewati langkah 2 menghasilkan kode yang benar untuk masalah yang salah. Melewati langkah 3 menghasilkan test yang mengikuti implementasi alih-alih menguji perilaku.

---

## Definition of Done

Sebuah task selesai bila **semua** benar:

- [ ] Test lulus, termasuk test untuk perilaku baru.
- [ ] `uv run check` hijau tanpa menurunkan apa pun.
- [ ] Tidak ada test yang memanggil model.
- [ ] Tidak ada referensi ke `data/eval/`.
- [ ] Sample keluaran tersimpan di `output/_samples/` bila task menghasilkan artefak.
- [ ] `docs/STATUS.md` diperbarui.
- [ ] Dokumen yang terpengaruh diperbarui (SPEC, AGENTS, CRAFT, atau NARRATIVE).
- [ ] Bila menyentuh scoring atau prompt: hasil `narathor eval` dilampirkan.

---

## Commit

Format pesan:

```
<fase>: <apa yang berubah>

<alasan singkat bila tidak jelas dari judul>
```

Contoh:

```
fase 4: indexer heuristik + deteksi filler

Segmentasi memakai jeda >0.8s dan penanda kalimat. Filler dideteksi
dengan daftar pola, bukan model, karena Indexer memang tanpa LLM.
```

Commit dalam bahasa Indonesia. Tanpa emoji. Satu commit satu perubahan logis.

---

## Ketika ragu

| Situasi | Tindakan |
|---|---|
| Spec tidak jelas | Berhenti, tanyakan. Jangan menebak |
| Test gagal dan perbaikannya berarti melonggarkan gate | Berhenti. Itu bukan perbaikan |
| Butuh mengubah `SOUL.md` untuk meloloskan sesuatu | Berhenti. Yang salah adalah hal yang ingin diloloskan |
| Butuh menambah field di brief | Perbarui `docs/NARRATIVE.md` dulu |
| Butuh peran agent baru | Perbarui `docs/AGENTS.md` dulu |
| Terpikir flag bypass "hanya untuk sementara" | Tidak ada. Bypass sementara menjadi permanen |
| Model terlalu mahal | Ubah lewat environment, bukan lewat kode |

---

## Laporan akhir

Setelah semua fase selesai, laporkan:

1. Hasil `uv run check`.
2. Hasil satu run nyata: berapa naskah, berapa lolos gate, berapa dikembalikan.
3. Metrik: `precision@10`, `citation_violation_rate`, `soul_violation_rate`, `craft_pass_rate`.
4. Biaya run (dari `run.json`).
5. Apa yang belum dikerjakan dan mengapa.
