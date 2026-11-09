# The Narathor brief

Dari pemilik produk, bersama tim konten.

## Bagaimana konten bekerja hari ini

Setiap orang menonton short. Attention span memendek, dan sebagian besar waktu itu dibelanjakan untuk hal yang tidak meninggalkan apa pun.

Di sisi lain, ada ribuan jam materi serius yang sudah diucapkan orang yang layak didengar — di YouTube, dalam video panjang satu jam, oleh orang yang paham apa yang mereka bicarakan. Materi itu hampir tidak pernah sampai ke orang yang paling membutuhkannya, karena bentuknya tidak cocok dengan cara orang menonton hari ini.

Jarak antara dua kenyataan itu adalah masalah yang ingin kami selesaikan. Bukan dengan membuat konten baru yang lebih ramai, tapi dengan **memindahkan pemahaman** dari tempat ia diucapkan ke tempat ia dibutuhkan.

## Apa yang kami inginkan

Sebuah mesin yang bekerja pada **pustaka video sebuah channel** — misalnya 400 video dari satu channel — dan menghasilkan naskah short yang utuh, siap diproduksi.

Mesin itu harus:

1. **Mengindeks** setiap video menjadi segmen-segmen bermakna, dengan timestamp.
2. **Mengombinasikan** segmen dari video-video **berbeda** menjadi satu alur yang membentuk satu tesis. Bukan memotong satu momen, tapi merangkai beberapa.
3. **Menulis naskah penuh** — hook, rangkaian kalimat, payoff, teks layar, judul, caption — dengan bahasa manusia, bukan ringkasan kaku.
4. **Menjaga setiap fakta terlacak** ke timestamp di mana ia diucapkan.
5. **Menilai karyanya sendiri** dan mengembalikan yang belum cukup baik, bukan meneruskannya.

Arah kontennya tidak ditentukan oleh mesin. Itu ditentukan oleh kami lewat Narrative Brief, dan mesin tunduk pada brief itu.

## Rules

- **Soul mengikat.** `SOUL.md` tidak dapat diubah oleh brief, config, atau flag. Setiap brief yang lebih longgar daripada soul akan ditolak.
- **Fakta wajib terlacak.** Naskah boleh ditulis dengan kata sendiri, tapi setiap klaim faktual wajib punya rujukan timestamp yang benar-benar ada di transkrip. Klaim tanpa sitasi → naskah ditolak.
- **Hook wajib dibayar.** Apa pun yang dijanjikan pembuka harus muncul di isi. Tidak ada penundaan payoff untuk menahan tontonan.
- **Kombinasi minimal dua video.** Kalau hanya satu video, itu potongan, bukan karya.
- **Tanpa clickbait, tanpa paywall, tanpa eksploitasi ketakutan.**
- **Tidak ada daftar frasa terlarang.** Kreativitas dinilai lewat tiga uji khas, bukan lewat daftar larangan. Yang dilarang adalah niat menipu, bukan pilihan kata.
- **Arah konten ditentukan lewat `briefs/<id>.yaml`.** Tidak ada tema, channel, atau nilai yang boleh ditanam di kode.
- **Keluaran MVP adalah naskah dan timestamp.** Render video bukan bagian dari build ini.

## Apa yang tim harus lihat

- Daftar naskah dengan tesisnya, satu baris per naskah, terurut menurut skor.
- Untuk setiap naskah: segmen mana yang dipakai, dari video mana, pada detik berapa.
- Naskah yang dikembalikan, beserta gate mana yang gagal dan alasannya.
- Naskah yang ditolak karena pelanggaran soul atau sitasi, beserta pasal yang dilanggar.
- Status run: berapa unit selesai, berapa berjalan, berapa tertunda.
- Ringkasan evaluasi: presisi pemilihan, tingkat pelanggaran sitasi, tingkat lolos gate kriya.

## Data kami

`data/` berisi pustaka video, transkrip, dan metadata channel. Read-only. Mesin menyemainya ke database sendiri dan tidak pernah menulis balik.

`data/eval/` berisi kunci jawaban — penilaian manusia atas momen mana yang layak. **Agent tidak boleh membukanya.** Test juga tidak. Ia dipakai hanya oleh `narathor eval` untuk mengukur, bukan untuk belajar.

## Tidak untuk sekarang

- Dashboard web.
- Render video, burn caption, crop 9:16.
- Auto-posting ke platform.
- Login dan multi-pengguna.
- Penjaminan viral. Yang dijamin adalah kepatuhan pada sinyal yang diketahui, bukan hasil.

## Bagaimana kami tahu ini berhasil

Bukan dari jumlah naskah yang dihasilkan. Dari tiga hal:

1. Naskah yang lolos gate bisa dibaca sekali dan langsung dipahami.
2. Setiap fakta di dalamnya bisa ditelusuri ke detik di video aslinya.
3. Setelah diproduksi, penonton bertahan lebih lama daripada rata-rata — dan yang lebih penting, mereka tidak menyesal menontonnya.
