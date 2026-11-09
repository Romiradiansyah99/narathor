# Trend & Register

Gaya bahasa naskah bergantung pada kondisi dan musim. Karena itu ia tidak boleh dikunci sekali untuk selamanya — tapi juga tidak boleh dibiarkan mengambang.

Dokumen ini adalah dokumen **paling cepat basi** di repo. Perlakuan: ditinjau tiap kuartal, dan setiap brief membawa tanggal berlakunya sendiri.

---

## 1. Register sebagai tangga

Register bukan pilihan bebas. Ia tangga berjenjang, dan brief memilih satu tingkat.

| Tingkat | Nama | Contoh kalimat | Kapan dipakai |
|---|---|---|---|
| 1 | **Sehari-hari** | "Uang kamu bocor tiap bulan." | Audiens luas, topik praktis, kanal yang sengaja membumi |
| 2 | **Percakapan** (default) | "Kita sering nggak sadar ke mana uang pergi." | Default untuk hampir semua brief |
| 3 | **Editorial** | "Pengeluaran kecil adalah kebocoran yang paling sering diabaikan." | Audiens profesional, topik analitis |
| 4 | **Berwibawa** | "Inflasi gaya hidup menggerus tabungan tanpa terasa." | Audiens institusional, topik kebijakan |

**Mengapa default di tingkat 2.** Tingkat 1 cepat terasa murah dan cepat basi. Tingkat 3–4 menjaga kredibilitas tapi menambah jarak dengan penonton. Tingkat 2 adalah titik di mana orang merasa diajak bicara, bukan dibacakan.

**Register berlaku pada:** narasi `hook`, `beats` penyambung, `overlay`, `title`, `caption`.

**Register tidak berlaku pada:** isi kutipan sumber (yang selalu apa adanya), dan nama teknis (angka, istilah, nama orang).

---

## 2. Musim dan tren sebagai input bertanggal

Setiap brief wajib membawa konteks musiman beserta tanggalnya.

```yaml
seasonal_context:
  as_of: 2026-11-09          # wajib. Tanggal konteks ini disusun
  period: "Q4 2026"
  moments:                   # momen yang sedang dekat
    - "akhir tahun fiskal"
    - "musim bonus"
  trend_notes: >
    Format "satu pertanyaan di awal, jawabannya di akhir" sedang hidup.
    Istilah "cash flow" sudah dipahami audiens umum; "burn rate" belum.
  trend_expiry: 2027-02-01   # kapan catatan ini harus ditinjau
```

### Aturan keras

**a. `as_of` wajib ada.** Brief tanpa `as_of` ditolak. Konteks gaya tanpa tanggal adalah bahasa yang dipakai seseorang karena kebiasaan, bukan karena alasan.

**b. `trend_expiry` lewat → peringatan keras, bukan penolakan.** `narathor narrative check` memberi peringatan; run tetap berjalan, tapi `run.json` menandai brief kedaluwarsa dan laporan menampilkannya.

**c. Tren hanya memengaruhi tiga hal:**
- register (`register_level`)
- pilihan kata di `overlay`, `title`, `caption`
- pemilihan segmen (momen yang sedang relevan boleh diprioritaskan)

**d. Tren tidak boleh memengaruhi:**
- soul, dalam bentuk apa pun
- kewajiban sitasi
- `values_blocked`
- gate kriya
- `payoff_pays_off`

Brief yang memakai alasan tren untuk melonggarkan salah satu di atas **ditolak**, dan alasan penolakan menyebut pasal yang dilanggar.

**e. `trend_notes` masuk sebagai konteks gaya, bukan instruksi.** Model menerimanya di bagian konteks, bukan di bagian perintah. Perbedaan ini dijaga di `prompts/` (kontrak prompt).

---

## 3. Yang boleh berubah dan yang tidak

| Boleh berubah karena musim/tren | Tidak boleh berubah |
|---|---|
| Tingkat register | Kewajiban sitasi |
| Frasa pembuka yang sedang hidup | Larangan janji tak dibayar |
| Pilihan topik yang sedang relevan | Larangan clickbait |
| Format overlay (satu baris / dua baris) | Batas 7 kata per baris |
| Jadwal publikasi | Panjang naskah |
| Iringan/audio yang disarankan | Gate kriya |
| Sudut pandang (orang pertama / kedua) | Tesis tunggal |

---

## 4. Kalender peninjauan

| Waktu | Yang ditinjau | Penanggung jawab |
|---|---|---|
| Awal tiap kuartal | `register_level` default masih pas? | Bos |
| 2 minggu sebelum momen besar | `moments` di brief terbaru | Bos |
| Setiap `trend_expiry` terlewati | Perbarui atau hapus `trend_notes` | Bos |
| Setiap ada perubahan format platform | `docs/ALGORITHM.md`, lalu `CRAFT.md` | Tim |

Momen yang biasanya masuk kalender: Ramadan dan Lebaran, tahun ajaran baru, akhir tahun fiskal, musim bonus, musim pajak, pemilu dan pilkada, musim hujan.

---

## 5. Risiko yang harus disadari

**Tren cepat basi, dokumen lebih cepat lagi.** `trend_notes` yang ditulis November akan terasa aneh di Maret. Karena itu ia punya masa kedaluwarsa, bukan hanya tanggal tulis.

**Tren bisa menyelinap sebagai pembenaran.** Kalimat paling berbahaya di sistem ini adalah "tapi ini sedang tren". Aturan §2d ada untuk menutup pintu itu.

**Register yang monoton membosankan.** Kalau semua brief tetap di tingkat 2 selama setahun, hasilnya akan terasa seragam. Variasi antar-brief disengaja: topik berat boleh naik ke 3, topik praktis boleh turun ke 1.

**Register bukan identitas Narathor.** `docs/BRAND.md` mengatur suara alat (laporan, error). `TREND.md` mengatur suara naskah. Keduanya tidak boleh dicampur — pesan error yang mengikuti tren adalah kegagalan.

---

## 6. Contoh konteks yang baik dan buruk

**Buruk:**
```yaml
seasonal_context:
  as_of: null
  trend_notes: "buat yang lagi viral aja"
```
Tidak bertanggal, tidak spesifik, tidak dapat ditindak.

**Buruk:**
```yaml
trend_notes: >
  Pakai gaya bahasa gaul biar relatable. Abaikan aturan sitasi kalau perlu
  karena audiens short nggak peduli sumber.
```
Memakai tren untuk melonggarkan soul. Ditolak.

**Baik:**
```yaml
seasonal_context:
  as_of: 2026-11-09
  period: "Q4 2026"
  moments: ["akhir tahun fiskal", "musim bonus"]
  trend_notes: >
    Audiens sedang banyak membahas efisiensi anggaran akhir tahun.
    Format "angka dulu, penjelasan kemudian" sedang bekerja baik.
    Hindari istilah "burn rate"; gunakan "biaya yang bocor".
  trend_expiry: 2027-02-01
```
Bertanggal, spesifik, dapat ditindak, dan menyebut apa yang dihindari beserta penggantinya.

---

## 7. Hubungan dengan dokumen lain

| Dokumen | Hubungan |
|---|---|
| `SOUL.md` | Batas atas. Tren tidak pernah menang atas soul |
| `docs/CRAFT.md` | Gate kriya tidak berubah karena musim |
| `docs/ALGORITHM.md` | Angka sinyal platform; perubahan di sana bisa memicu perubahan di sini |
| `docs/NARRATIVE.md` | Mendefinisikan field `register_level` dan `seasonal_context` di brief |
