# Algorithm

Riset sinyal distribusi YouTube Shorts dan TikTok. **Bertanggal** — dokumen ini wajib ditinjau ulang setiap kuartal.

**Tanggal riset:** 9 November 2026
**Peninjauan berikutnya:** Februari 2027

---

## 1. Tingkat keyakinan

Tidak semua klaim di bawah setara. Setiap bagian menyebut tingkatnya:

- **Tinggi** — dinyatakan platform sendiri melalui dokumentasi atau perwakilannya.
- **Menengah** — analisis pihak ketiga atas data agregat besar.
- **Rendah** — angka vendor yang menjual jasa engagement. Arah saja, bukan hukum.

Mencampur ketiganya tanpa label adalah cara paling umum membuat dokumen algoritma jadi tidak dapat dipercaya.

---

## 2. Sinyal YouTube Shorts — keyakinan tinggi

Berasal dari dokumentasi YouTube dan pernyataan Todd Sherman (product lead YouTube Shorts).

| Sinyal | Peran | Implikasi |
|---|---|---|
| **Viewed vs. Swiped Away** | Tes pertama dan paling menentukan | Hook harus menang di frame pertama. Tidak ada intro. |
| **Average View Duration / % Viewed** | Tinggi | Payoff harus datang cepat. |
| **Satisfaction** (like, dislike, survey pasca-tonton) | Tinggi, eksplisit | Retensi tinggi tanpa kepuasan tetap gagal. |
| **Watch history & topic interest** | Tinggi | Satu channel harus punya niche konsisten. |
| **Sounds** | Menengah | Naskah harus siap untuk voice-over atau audio populer. |
| Competition & seasonality | Menengah | Jadwal dan topik berpengaruh. |

**Bukan sinyal** — mitos yang harus ditolak:

- Jumlah subscriber. Feed dirancang menampilkan channel yang belum di-follow.
- Frekuensi posting. Tidak ada minimum; posting lebih sering hanya menambah kesempatan.
- Cross-posting ke TikTok/Instagram/Facebook. Membawa traffic luar, tapi tidak dihitung sistem ranking.
- Kepadatan hashtag. Hashtag menyumbang di bawah 1% views.

**Perubahan definisi "view" (31 Maret 2025):** setiap pemutaran atau ulangan dihitung view. Angka besar di dashboard adalah jangkauan, bukan tontonan. "Engaged views" adalah angka yang lebih ketat dan yang menghitung untuk monetisasi. Karena itu angka views 2026 tidak sebanding dengan 2025.

---

## 3. Arketipe hook — keyakinan menengah/rendah

Data dari analisis vendor atas ~12.400 post TikTok. **Vendor menjual jasa engagement — perlakukan sebagai arah, bukan kebenaran.**

| Arketipe | Median watch time | Median like rate | Retensi 2 detik |
|---|---|---|---|
| Confession | 14.8s | 6.8% | 84% |
| Counter-intuitive claim | 13.1s | 5.4% | 81% |
| Specific number | 12.5s | 4.9% | 79% |
| Mid-action cold open | 11.9s | 4.4% | 77% |
| Generic sales opener | 7.2s | 2.7% | 61% |
| Trend-audio-only | 6.4s | 2.1% | 58% |

Temuan operasional:

- Keputusan scroll pertama terjadi sekitar **detik ke-2**.
- Kata pertama harus terdengar **sebelum detik ke-1**.
- Storytelling mengalahkan sales hook sekitar **1.9×** pada like rate.

**Cara Narathor memakai tabel ini:** empat arketipe teratas adalah **inspirasi pilihan**, bukan aturan wajib. Tidak ada daftar frasa terlarang. Critic menilai apakah arketipe yang dipilih *bekerja pada naskah ini*, bukan apakah arketipe itu ada di daftar.

Dua arketipe terbawah dilarang bukan karena namanya, tapi karena konsekuensinya: keduanya berperforma terendah **dan** menempatkan produk di wilayah clickbait. Larangan ganda, bukan kompromi.

---

## 4. Durasi — temuan yang mengubah desain

**Analisis 35 miliar views Shorts** menemukan Shorts berperforma terbaik pada **13 detik** atau **60 detik** — dua puncak, bukan spektrum rata.

**Metricool 2026** (799.718 video, 71.177 akun) mengukur rata-rata watch time turun ke **~16 detik**, dari ~0.79 menit setahun sebelumnya.

Kesimpulan: **montage 30 detik adalah dead zone.** Ia kehilangan payoff sebelum penonton pergi, dan tidak cukup panjang untuk membangun struktur tiga babak.

Aturan Narathor:

| Durasi | Status | Struktur |
|---|---|---|
| 13–20 detik | **Default** | Satu tesis, hook langsung, payoff sebelum detik 16, tanpa babak |
| 60 detik | Didukung | Tiga babak: klaim → bukti/cerita → konsekuensi |
| 30 detik | `--experimental` | Hanya untuk uji banding, tidak untuk produksi |

**Aturan keras:** `payoff_at_s < 16` untuk target 13–20s. Untuk target 60s, payoff pertama harus tetap muncul sebelum detik 16, lalu payoff utama di paruh kedua.

---

## 5. Keunggulan struktural konten edukatif

Metricool 2026, tentang umur sebuah Short:

> Short melakukan sebagian besar kerjanya lebih awal. Hari pertama membawa porsi besar views. Tiga hari pertama adalah rentang terkuat. Setelah itu melambat tanpa berhenti — YouTube terus menampilkan Short ke audiens baru.
>
> *"one with a solid topic can keep picking up views for months at a quieter pace. That kind of shelf life is rare in short-form video. It rewards Shorts built around topics that still matter after the trend fades."*

Konten mencerdaskan **secara inheren punya shelf life panjang**. Ini keunggulan kompetitif yang selaras soul, bukan kompromi terhadapnya. Masuk strategi distribusi, bukan sekadar optimasi teknis.

Konsekuensi untuk `Critic`: gate **"layak ditonton enam bulan lagi"** bukan idealisme. Itu prediktor jangka panjang yang didukung data.

---

## 6. Temuan yang menegaskan soul

YouTube menempatkan **Satisfaction** sebagai sinyal eksplisit. Metricool merumuskannya:

> *"A Short can hold attention and still leave people feeling like they wasted their time. The system is built to spot the difference."*

Kebijakan YouTube (Juli 2025) juga melarang monetisasi konten **mass-produced repetitive** — templat identik, slideshow sama, voice-over berulang.

**Kesimpulan yang mengikat produk ini:** di 2026 algoritma **menghukum** clickbait-tanpa-payoff dan **menghargai** nilai nyata. Mengoptimalkan retensi kosong bukan hanya tidak etis — sudah tidak efektif.

Narathor mengoptimalkan **satisfaction-weighted retention**. Ini pilihan yang sekaligus benar secara moral dan benar secara metrik. Bila keduanya bertentangan, dokumen ini akan mengatakannya — tapi per November 2026 keduanya sejalan.

---

## 7. Perilaku distribusi yang perlu diketahui

Dari Metricool 2026:

- **Shorts feed menyumbang 61.5%** organic views. Subscriber 11.3%, search 8.8%.
- Akun kecil tumbuh paling cepat. Akun >1M subscriber kehilangan 74% views per Short.
- Per-post terbaik pada **2–4 post per minggu**. Volume lebih tinggi menurunkan angka per post sedikit, tapi menambah total.
- Menposting Shorts **tidak merugikan** long-form. Tidak menposting Shorts justru berkorelasi dengan views long-form di bawah rata-rata.

Implikasi untuk brief: `sources.channels` sebaiknya satu niche. Melompat topik memecah sinyal audiens.

---

## 8. Batas kejujuran

Yang harus dibaca sebelum memakai dokumen ini:

1. **Platform tidak mempublikasikan bobot.** Semua angka relatif adalah inferensi.
2. **Angka TikTok berasal dari vendor engagement.** Perlakuan: arah, bukan target.
3. **Semua angka berubah.** Tanggal riset tercantum di atas; peninjauan kuartalan wajib.
4. **Narathor tidak menjanjikan viral.** Yang dijamin adalah kepatuhan pada sinyal yang diketahui.
5. **Korelasi bukan sebab.** Channel yang menposting Shorts punya views long-form lebih tinggi — itu bisa berarti Shorts membantu, atau bisa berarti channel itu memang lebih aktif.

Dokumen yang menyembunyikan batas-batas ini lebih berbahaya daripada tidak ada dokumen.

---

## 9. Ritme peninjauan

| Kuartal | Yang diperiksa |
|---|---|
| Q1 2027 | Apakah definisi engaged view berubah? Apakah durasi optimal bergeser? |
| Q2 2027 | Apakah sinyal satisfaction masih eksplisit? Kebijakan konten AI berubah? |
| Q3 2027 | Apakah tabel arketipe masih relevan, atau vendor sudah berganti metodologi? |

Perubahan pada dokumen ini **tidak** mengubah soul. Yang berubah: bobot rubrik, target durasi, dan isi `CRAFT.md`.

---

## Sumber

- [vidIQ — How Does the YouTube Shorts Algorithm Work in 2026?](https://vidiq.com/blog/post/youtube-shorts-algorithm/)
- [Metricool — YouTube Shorts Algorithm Explained + Tips to Grow in 2026](https://metricool.com/youtube-shorts-algorithm/)
- [SMMNut — TikTok Hook Strategy 2026 (vendor engagement; arah saja)](https://smmnut.com/blog/tiktok-hook-strategy/)
