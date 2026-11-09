# Soul Guard

Manual operasional untuk `SOUL.md`. Dokumen ini boleh diperbaiki kapan saja; `SOUL.md` tidak.

Alasan pemisahan: kalau manual dan konstitusi ada di file yang sama, setiap perbaikan kalimat di manual akan memicu mismatch soul.

---

## 1. Verifikasi

```bash
uv run -m narathor soul verify
```

Yang dilakukan:

1. Baca `SOUL.md`.
2. Hitung SHA-256 atas isi file apa adanya (byte-per-byte, tanpa normalisasi line ending).
3. Bandingkan dengan `sha256` di `soul.lock`.
4. Laporkan `SoulCheck {ok, expected_hash, actual_hash, version, checked_at}`.

Hasil:

| Kondisi | Perilaku |
|---|---|
| Hash cocok | `ok: true`, eksekusi lanjut |
| Hash tidak cocok | `ok: false`, **seluruh command berhenti**, exit non-zero |
| `soul.lock` tidak ada | `ok: false`, pesan menyebut cara regenerasi |
| `SOUL.md` tidak ada | `ok: false`, sistem tidak dapat dijalankan |

Verifikasi berjalan **implisit di awal setiap command**, termasuk di dalam setiap request agent ke backend. Bukan hanya saat `soul verify` dipanggil manual.

Saat mismatch, yang **tidak** terjadi: tidak ada panggilan model, tidak ada artefak ditulis, tidak ada entri database baru. Sistem berhenti sebelum pekerjaan dimulai.

---

## 2. Mismatch: apa yang harus dilakukan

Jangan langsung menimpa `soul.lock`. Mismatch adalah alarm, bukan gangguan.

1. **Cari tahu apa yang berubah.**
   ```bash
   git diff SOUL.md
   ```
   Kalau bukan commit yang kamu buat sendiri, hentikan semua pekerjaan dan periksa repo.

2. **Kalau perubahan tidak disengaja** — kembalikan:
   ```bash
   git checkout -- SOUL.md
   uv run -m narathor soul verify
   ```

3. **Kalau perubahan disengaja** — itu `soul bump`. Lanjut ke bagian 3.

Mismatch yang ditimpa tanpa diperiksa menghapus satu-satunya jaminan yang dimiliki sistem ini.

---

## 3. Prosedur `soul bump`

Mengubah soul bukan tugas rutin. Ini mengubah dasar seluruh produk.

**Langkah 1 — Tulis alasan.** Satu paragraf. Apa yang salah dengan pasal lama, mengapa pasal baru lebih benar. Tanpa alasan, tidak ada bump.

**Langkah 2 — Edit `SOUL.md`.** Naikkan `Versi` di akhir dokumen. Perubahan harus berupa pasal utuh, bukan tambalan kalimat.

**Langkah 3 — Periksa dampak.** Pasal mana yang berubah, dan bagian sistem mana yang bergantung padanya:

| Pasal | Bergantung pada |
|---|---|
| 1 | `learning_outcome` wajib di brief |
| 2 | `single_minded_proposition` di naskah |
| 3 | pemeriksaan CTA |
| 4 | `payoff_pays_off`, batas rasio bobot |
| 5 | gate sitasi |
| 6 | dua lapis pemeriksaan `values_blocked` |
| 7 | `run.json` |

**Langkah 4 — Jalankan bump.**
```bash
uv run -m narathor soul bump --reason "Pasal 5: verbatim diganti setia jejak karena output kini naskah penuh"
```
Yang terjadi: `soul.lock` menaikkan `version`, menyimpan hash lama ke `previous_versions[]`, menulis hash baru, mencatat tanggal dan alasan.

**Langkah 5 — Re-evaluasi.** `soul_version` adalah bagian dari cache key. Semua naskah yang dihasilkan dengan soul lama **tidak lagi sah**. Jalankan ulang eval:
```bash
uv run -m narathor eval --narrative <id>
```
Tanpa langkah ini, bump tidak sah.

**Langkah 6 — Catat di Decision Log.** Tambahkan entri di `docs/STATUS.md`:

```
| Tanggal | Keputusan | Alasan | Dampak |
|---|---|---|---|
| 2026-11-09 | Soul v1 → v2, Pasal 5 | output kini naskah penuh | semua narrative perlu re-eval |
```

---

## 4. Format changelog soul

`previous_versions[]` menyimpan jejak, bukan isi:

```json
{
  "version": 2,
  "sha256": "<hash baru>",
  "locked_at": "2026-11-09",
  "locked_by": "boss",
  "previous_versions": [
    {
      "version": 1,
      "sha256": "<hash lama>",
      "replaced_at": "2026-11-09",
      "reason": "Pasal 5: verbatim diganti setia jejak"
    }
  ]
}
```

Isi lama selalu tersedia di git history. `soul.lock` hanya perlu membuktikan bahwa perubahan tercatat.

---

## 5. Integritas cache

`soul_version` masuk ke cache key setiap tahap:

```
cache_key = hash(unit_id, prompt_version, brief_hash, soul_version, craft_version)
```

Konsekuensi yang penting dipahami: **ganti soul menginvalidasi seluruh cache.** Itu disengaja. Naskah yang dihasilkan di bawah pasal yang berbeda tidak boleh dipakai ulang seolah masih sah.

Biaya re-eval setelah bump kira-kira sama dengan satu run penuh. Itu harga dari perubahan konstitusi, dan wajar.

---

## 6. Batas jaminan — dinyatakan terbuka

Yang **dijamin**:

- Setiap ketidakcocokan `SOUL.md` dengan `soul.lock` menghentikan eksekusi.
- Perubahan soul tidak dapat terjadi tanpa mengubah `soul.lock`.
- Setiap perubahan `soul.lock` tercatat di git history.
- Setiap artefak menyebut `soul_version` yang berlaku saat ia dibuat.

Yang **tidak dijamin**:

- Bahwa seseorang tidak dapat mengedit `SOUL.md` **dan** `soul.lock` sekaligus. Pada mesin lokal, siapa pun yang menguasai repo bisa.
- Bahwa hash membuktikan siapa yang mengubah. Hash hanya mendeteksi, tidak mengidentifikasi.

Karena itu istilah yang dipakai adalah **tamper-evident**, bukan tamper-proof. Menyebutnya tamper-proof akan menjadi kebohongan yang membuat orang mempercayai jaminan yang tidak ada.

---

## 7. Pengerasan Fase 2 (belum dikerjakan)

Dicatat sebagai rencana, bukan sebagai kemampuan hari ini:

1. **Signing key di luar repo.** `soul.lock` ditandatangani; public key dibagikan terpisah. Mengedit lock tidak cukup tanpa private key.
2. **Remote attestation.** Hash soul dipublikasikan di endpoint yang tidak dapat diubah dari mesin lokal.
3. **Soul sebagai artefak rilis.** Soul ikut dalam paket rilis yang ditandatangani; binary menolak berjalan dengan soul yang tidak cocok dengan rilisnya.

Ketiganya menambah friksi. Untuk MVP, tamper-evident sudah cukup, asal tidak diklaim lebih.

---

## 8. Yang tidak boleh dilakukan

- Menimpa `soul.lock` tanpa memeriksa diff.
- Menjalankan `soul bump` tanpa alasan tertulis.
- Mengubah soul untuk meloloskan satu brief yang gagal. Kalau brief gagal, yang salah adalah brief.
- Menambahkan flag `--skip-soul` untuk keadaan darurat. Tidak ada keadaan darurat yang membenarkan melewati konstitusi.
- Menyebut sistem ini tamper-proof.

---

## 9. Referensi silang

| Dokumen | Hubungan |
|---|---|
| `SOUL.md` | Yang dilindungi |
| `soul.lock` | Bukti integritas |
| `docs/SPEC.md` | Aturan produk yang diturunkan dari soul |
| `docs/NARRATIVE.md` | Hal yang boleh dan tidak boleh ada di brief |
| `docs/AGENTS.md` | Di mana soul check berada di pipeline |
| `docs/STATUS.md` | Decision Log dan Soul Compliance Log |
