# Narrative Brief

Kontrak untuk mengarahkan Narathor. Brief adalah milik bos — satu-satunya tempat arah konten ditentukan.

Alat ini netral. Arahnya ada di sini.

---

## 1. Di mana brief berada dalam hierarki

```
L0  SOUL.md + soul.lock      ← tidak bisa diubah siapa pun
L1  docs/BRAND.md            ← identitas alat, tetap
L2  briefs/<id>.yaml         ← milik bos, dibatasi L0 dan L1
```

Brief tidak dapat melonggarkan soul. Validator memeriksa itu sebelum run dimulai, bukan setelah.

---

## 2. Lokasi dan penamaan

```
briefs/<narrative_id>.yaml
```

`narrative_id` huruf kecil, angka, dan tanda hubung. Contoh: `cerdaskan-bangsa`, `literasi-utang-2027`.

Setiap brief punya folder output sendiri: `output/<narrative_id>/<channel>/`. Dua brief berbeda pada channel yang sama tidak pernah berbagi artefak.

---

## 3. Schema lengkap

```yaml
id: cerdaskan-bangsa
title: "Mencerdaskan bangsa lewat atensi yang berguna"

# --- Wajib: apa yang audiens pahami setelah menonton ---
learning_outcome: >
  Penonton memahami bahwa masalah keuangan pribadi jarang soal jumlah
  penghasilan, dan lebih sering soal arah aliran.

# --- Tesis: satu gagasan yang menyatukan semua naskah ---
thesis: >
  Atensi adalah aset terbatas. Konten yang layak ditonton adalah yang
  meninggalkan satu gagasan utuh, bukan sekadar kejutan emosi.

# --- Audiens ---
audience:
  primary: "Indonesia, 18-35, terbiasa short, belum punya dasar"
  literacy_level: menengah
  pain_points:
    - "merasa sudah tahu tapi hasilnya tidak berubah"
    - "mudah terpancing judul provokatif"

# --- Nilai: apa yang boleh dan tidak boleh muncul ---
values_allowed:
  - kejujuran_intelektual
  - kerja_keras_tanpa_shortcut
  - tanggung_jawab_personal
  - literasi_finansial_yang_sehat
values_blocked:
  - janji_kaya_instan
  - membenci_kelompok
  - pseudosains
  - manipulasi_emosi_untuk_engagement

# --- Gaya ---
register_level: 2            # 1..4, lihat docs/TREND.md
tone:
  target: "tegas, jernih, tidak menggurui"
  avoid:
    - "menggurui"
    - "memohon perhatian"

# --- Musim ---
seasonal_context:
  as_of: 2026-11-09          # WAJIB
  period: "Q4 2026"
  moments: []
  trend_notes: ""
  trend_expiry: null

# --- Sumber ---
sources:
  channels:
    - "https://www.youtube.com/@example"
  recency_preference: any    # any | recent | classic
  min_duration_s: 180

# --- Bentuk keluaran ---
output:
  scripts: 30
  target_duration_s: 15      # 13..20 atau 60
  language: id
  montages: 0

# --- Penyetelan skor (opsional) ---
scoring_overrides:
  brand_fit_weight: 0.05
```

---

## 4. Semantik tiap field

| Field | Wajib | Arti |
|---|---|---|
| `id` | ya | Identitas brief. Tidak boleh sama dengan brief lain. |
| `title` | ya | Nama untuk manusia. Muncul di laporan. |
| `learning_outcome` | **ya** | Satu kalimat pemahaman. Tanpa ini, brief ditolak (Pasal 1 dan 2). |
| `thesis` | ya | Satu gagasan yang menyatukan seluruh naskah dalam run ini. |
| `audience.primary` | ya | Siapa. Spesifik, bukan "semua orang". |
| `audience.literacy_level` | ya | `rendah` / `menengah` / `tinggi`. Memengaruhi penjelasan istilah. |
| `audience.pain_points` | tidak | Masalah nyata audiens. Membantu Matcher memilih segmen relevan. |
| `values_allowed` | ya | Nilai yang boleh muncul. Boleh kosong hanya bila `values_blocked` terisi. |
| `values_blocked` | ya | Nilai yang dibuang permanen. Boleh kosong. |
| `register_level` | ya | 1–4, lihat `docs/TREND.md`. |
| `tone.target` | ya | Satu frasa. Contoh: "tegas, jernih, tidak menggurui". |
| `tone.avoid` | tidak | Yang harus dihindari dalam gaya. |
| `seasonal_context.as_of` | **ya** | Tanggal konteks disusun. |
| `seasonal_context.trend_expiry` | tidak | Kapan catatan tren harus ditinjau. |
| `sources.channels` | ya | Minimal satu URL channel. |
| `sources.recency_preference` | ya | `any` / `recent` / `classic`. |
| `sources.min_duration_s` | tidak | Saring video terlalu pendek. Default 180. |
| `output.scripts` | ya | Berapa naskah diminta. |
| `output.target_duration_s` | ya | 13–20 atau 60. Nilai 30 ditolak kecuali mode eksperimental. |
| `output.language` | ya | `id` untuk sekarang. |
| `output.montages` | tidak | 0 = tidak menghasilkan montage. |
| `scoring_overrides` | tidak | Penyetelan bobot. Lihat §6. |

---

## 5. Anchor `brand_fit`

`brand_fit` adalah kecocokan sebuah segmen dengan brief. Ia dinilai dengan anchor, bukan selera — supaya dua brief berbeda menghasilkan ranking yang berbeda secara terukur.

**Skor 5** — segmen secara langsung melayani `learning_outcome` atau `thesis`, dan tidak menyentuh satu pun `values_blocked`.

> Contoh: segmen membahas kebocoran pengeluaran kecil, sementara brief bertesis bahwa masalahnya arah aliran.

**Skor 3** — segmen relevan dengan topik tapi tidak langsung melayani tesis; berguna sebagai bukti atau konteks.

> Contoh: segmen berisi angka statistik konsumsi, tanpa argumen tentang aliran.

**Skor 1** — segmen menyentuh topik yang sama sekali berbeda; hanya terhubung lewat asosiasi longgar.

**Skor 0** — segmen menyentuh salah satu `values_blocked` → **drop permanen**, `total` diabaikan.

Aturan: skor `brand_fit` di bawah 3 pada brief yang ketat → segmen tidak masuk combo.

---

## 6. `scoring_overrides`

Hanya field ini yang boleh diubah, dengan batas:

| Field | Default | Batas |
|---|---|---|
| `brand_fit_weight` | 0.05 | 0.00–0.30 |
| `satisfaction_weight` | 0.20 | 0.10–0.35 |
| `hook_weight` | 0.25 | 0.15–0.30 |

**Aturan anti-geser:** `hook_weight` tidak boleh melebihi `satisfaction_weight + 0.10`. Tujuannya mencegah brief mengubah produk menjadi mesin hook — itu pelanggaran Pasal 4.

`length_fit` bukan bobot. Ia gate, tidak bisa di-override.

---

## 7. Alasan brief ditolak

Dua belas kondisi. Masing-masing menyebut dasar penolakannya.

| # | Kondisi | Dasar |
|---|---|---|
| 1 | `learning_outcome` kosong atau tidak ada | Pasal 1, 2 |
| 2 | `thesis` kosong | Tidak ada yang menyatukan naskah |
| 3 | `seasonal_context.as_of` kosong | Gaya tanpa tanggal tidak dapat dipertanggungjawabkan |
| 4 | `values_blocked` bertabrakan dengan `values_allowed` | Kontradiksi internal |
| 5 | `values_blocked` memuat nilai yang justru diwajibkan soul | Pasal 3, 4, 6 |
| 6 | `tone` atau `trend_notes` meminta melonggarkan sitasi | Pasal 5 |
| 7 | `tone` atau `trend_notes` meminta memaafkan clickbait | Pasal 4 |
| 8 | `target_duration_s` = 30 tanpa mode eksperimental | `docs/ALGORITHM.md` §4 |
| 9 | `sources.channels` kosong atau tidak valid | Tidak ada bahan |
| 10 | `register_level` di luar 1–4 | `docs/TREND.md` §1 |
| 11 | `scoring_overrides` melampaui batas §6 | Anti-geser |
| 12 | **Ambiguitas** — validator tidak dapat memastikan brief lolos atau melanggar | Fail-closed |

**Tentang nomor 12.** Ini keputusan yang disengaja. Brief yang tidak jelas aman diperlakukan sebagai tidak aman. Tidak ada karantina, tidak ada "lolos dengan peringatan", tidak ada peninjauan manusia yang menunda. Brief ambigu ditolak, alasan penolakan menyebut bagian mana yang ambigu, dan bos memperbaikinya.

Alasannya: jalur karantina selalu berubah menjadi jalur pintas. Kalau ada cara meloloskan brief yang tidak jelas, orang akan memakainya.

---

## 8. Perilaku saat ditolak

- Exit non-zero.
- Alasan cetak ke stderr, menyebut nomor kondisi dan pasal.
- **Tidak ada artefak** ditulis ke `output/`.
- **Tidak ada panggilan model generatif** setelah penolakan.

Contoh keluaran:

```
Brief "cerdaskan-bangsa" ditolak.

[12] Ambiguitas pada field values_blocked:
     "konten yang terlalu berhati-hati" tidak dapat dipetakan ke nilai mana pun.
     Perjelas, atau hapus.

[5] Pelanggaran Pasal 4:
     tone.target memuat "bikin penasaran sampai akhir".
     Ini meminta penundaan payoff.

Tidak ada artefak yang ditulis.
```

---

## 9. Dua contoh utuh

### 9.1 Brief ketat

```yaml
id: literasi-utang-2027
title: "Literasi utang tanpa menakut-nakuti"

learning_outcome: >
  Penonton memahami perbedaan antara utang yang membangun dan utang yang
  menggerus, dan dapat menyebut satu tanda yang berlaku pada dirinya.

thesis: >
  Utang bukan moral, tapi matematika dan waktu. Yang berbahaya adalah
  utang yang dipakai menutup utang.

audience:
  primary: "Indonesia, 22-40, punya cicilan aktif"
  literacy_level: menengah
  pain_points:
    - "cicilan bertambah tapi tidak merasa hidup lebih baik"

values_allowed:
  - kejujuran_intelektual
  - tanggung_jawab_personal
values_blocked:
  - janji_kaya_instan
  - manipulasi_emosi_untuk_engagement
  - menyalahkan_korban

register_level: 2
tone:
  target: "tenang, jelas, tanpa menghakimi"
  avoid: ["menakut-nakuti", "menggurui"]

seasonal_context:
  as_of: 2026-11-09
  period: "Q4 2026"
  moments: ["akhir tahun fiskal"]
  trend_notes: "Audiens responsif pada contoh angka konkret, bukan nasihat umum."
  trend_expiry: 2027-02-01

sources:
  channels: ["https://www.youtube.com/@example"]
  recency_preference: any
  min_duration_s: 300

output:
  scripts: 20
  target_duration_s: 15
  language: id
  montages: 0
```

**Kenapa ketat:** `values_blocked` memuat tiga hal yang mudah dilanggar konten finansial. `tone.avoid` melarang dua pendekatan paling umum. `learning_outcome` menuntut hasil yang bisa diukur pada penonton.

### 9.2 Brief longgar

```yaml
id: sains-sehari-hari
title: "Sains yang ada di dapur"

learning_outcome: >
  Penonton memahami satu prinsip ilmiah yang menjelaskan sesuatu yang
  mereka lakukan setiap hari.

thesis: >
  Sains bukan pelajaran, tapi penjelasan atas hal yang sudah biasa.

audience:
  primary: "Indonesia, 15-30, rasa ingin tahu tinggi"
  literacy_level: rendah

values_allowed: [kejujuran_intelektual]
values_blocked: [pseudosains]

register_level: 1
tone:
  target: "santai, konkret"
  avoid: ["menggurui"]

seasonal_context:
  as_of: 2026-11-09
  period: "Q4 2026"
  moments: []
  trend_notes: ""
  trend_expiry: 2027-02-01

sources:
  channels: ["https://www.youtube.com/@example-2"]
  recency_preference: any

output:
  scripts: 40
  target_duration_s: 15
  language: id
```

**Kenapa longgar:** hanya satu nilai diblokir (`pseudosains` — batas mutlak), register terendah, tone bebas. Tapi `learning_outcome` tetap wajib: kelonggaran ada pada gaya, bukan pada tujuan.

---

## 10. Uji kausal yang wajib lolos

Tiga hal yang membuktikan brief benar-benar dipakai, bukan diabaikan:

1. **Ganti brief, ranking berubah.** Dua brief berbeda pada channel yang sama harus menghasilkan urutan segmen berbeda secara terukur.
2. **Brief melanggar soul → ditolak tanpa artefak.**
3. **Nilai di `values_blocked` → segmen hilang dari index dan muncul di `blocked.md`** beserta pasal yang dirujuk.

Kalau salah satu tidak terpenuhi, brief tidak benar-benar dibaca sistem — dan seluruh dokumen ini jadi hiasan.

---

## 11. Yang tidak boleh

- Menaruh tema, channel, atau nilai di kode. Semua lewat brief.
- Menyalin satu brief untuk semua kebutuhan lalu mengubah sedikit. Setiap perubahan arah adalah brief baru dengan `id` baru.
- Memakai `trend_notes` sebagai instruksi.
- Menambahkan field di luar schema tanpa memperbarui dokumen ini lebih dulu.
- Menganggap `learning_outcome` sebagai formalitas. Ia adalah alasan keberadaan run.
