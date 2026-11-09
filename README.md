# Narathor

Mesin perangkai naskah short dari pustaka video sebuah channel YouTube.

Narathor mengambil ratusan jam materi yang sudah diucapkan orang yang layak didengar, lalu menyusunnya kembali menjadi naskah short yang utuh: satu tesis, satu alur, setiap fakta terlacak ke detik sumbernya.

Bukan alat potong video. Bukan alat viral. Alat pemindah pemahaman.

---

## Tiga lapis otoritas

```
L0  SOUL.md + soul.lock     konstitusi — tidak dapat diubah brief, config, atau flag
L1  docs/BRAND.md           identitas alat — tetap
L2  briefs/<id>.yaml        arah konten — milik bos, dibatasi L0 dan L1
```

Arah konten tidak ditanam di kode. Ia hidup di satu file yang dapat diganti kapan saja tanpa menyentuh satu baris program.

---

## Peta dokumen

| Dokumen | Menjawab pertanyaan |
|---|---|
| [`SOUL.md`](SOUL.md) | Apa yang tidak boleh dilanggar, oleh siapa pun |
| [`docs/SOUL_GUARD.md`](docs/SOUL_GUARD.md) | Bagaimana soul diperiksa dan diubah |
| [`docs/SPEC.md`](docs/SPEC.md) | Produk ini untuk apa, aturannya apa |
| [`docs/BRAND.md`](docs/BRAND.md) | Bagaimana Narathor berbicara dan tampil |
| [`docs/TECH_STACK.md`](docs/TECH_STACK.md) | Bagian sistem, versi, environment, batasan Windows |
| [`docs/AGENTS.md`](docs/AGENTS.md) | Lima peran, framework, mekanisme konkurensi |
| [`docs/ALGORITHM.md`](docs/ALGORITHM.md) | Apa yang diukur platform, dan apa yang mitos |
| [`docs/CRAFT.md`](docs/CRAFT.md) | Standar kriya: kombinasi, gate, tiga uji khas |
| [`docs/TREND.md`](docs/TREND.md) | Register bahasa dan konteks musiman |
| [`docs/NARRATIVE.md`](docs/NARRATIVE.md) | Kontrak brief, dan alasan penolakannya |
| [`docs/MODELS.md`](docs/MODELS.md) | Model per peran, biaya, cara menggantinya |
| [`docs/PROCESS.md`](docs/PROCESS.md) | Cara merencanakan, membangun, dan menyerahkan |
| [`docs/CODE_STANDARDS.md`](docs/CODE_STANDARDS.md) | Aturan kode |
| [`docs/PLAN.md`](docs/PLAN.md) | Urutan pembangunan dan success criteria |
| [`docs/STATUS.md`](docs/STATUS.md) | Keadaan hari ini, metrik, keputusan |
| [`briefs/_template.yaml`](briefs/_template.yaml) | Template brief |

---

## Alur

```
Channel (400 video)
  ├─ Curator   → video mana yang masuk lingkup
  ├─ Indexer   → segmen bermakna per video (tanpa LLM)
  ├─ Matcher   → Combo: 2–5 segmen dari video berbeda, satu tesis
  ├─ Writer    → naskah penuh + sitasi per klaim
  └─ Critic    → tujuh gate; gagal → dikembalikan
        ↓
  output/<narrative>/<channel>/
    scripts/*.md  scripts/*.json  index.md  blocked.md  run.json
```

---

## Quickstart

Belum ada kode. Setelah Fase 1 di `docs/PLAN.md`:

```bash
uv sync
uv run -m narathor doctor
```

Setelah Fase 8:

```bash
uv run -m narathor soul verify
uv run -m narathor narrative check cerdaskan-bangsa
uv run -m narathor ingest --narrative cerdaskan-bangsa --workers 5
uv run -m narathor mine   --narrative cerdaskan-bangsa --top 50
uv run -m narathor script --narrative cerdaskan-bangsa --count 30 --workers 5
uv run -m narathor report --narrative cerdaskan-bangsa
uv run -m narathor eval   --narrative cerdaskan-bangsa
```

---

## Aturan emas

1. **Dokumen dulu, kode kemudian.** Perubahan perilaku → perbarui spec lebih dulu.
2. **Soul tidak disentuh.** Hanya lewat `soul bump` eksplisit.
3. **Tidak ada tema di kode.** Tema hidup di brief.
4. **Fakta wajib terlacak.** Klaim tanpa sitasi → naskah ditolak.
5. **Tidak ada blacklist frasa.** Kreativitas diuji, bukan dilarang.
6. **Test tidak pernah memanggil model.**
7. **Jangan membuka `data/eval/`.** Itu kunci jawaban.

---

## Yang tidak akan pernah dilakukan Narathor

1. Menerbitkan klaim tanpa jejak ke sumbernya.
2. Menjanjikan di pembuka apa yang tidak diberikan di isi.
3. Menyembunyikan bahwa sumber pernah mengatakan sebaliknya.
4. Membuat orang harus membayar untuk memahami.

Keempatnya bukan kebijakan yang dapat dinegosiasikan. Ketiganya berasal dari `SOUL.md`, dan yang keempat adalah alasan produk ini ada.

---

## Situs

Naskah dan sitasinya dipublikasikan sebagai situs statis:

- https://romiradiansyah99.github.io/narathor/

Dibangun ulang setelah setiap run:

```bash
uv run python tools/build_site.py
git subtree push --prefix site origin gh-pages
```

GitHub Pages hanya menyajikan berkas. Mesinnya berjalan di mesin sendiri lewat CLI.

---

## Status

Fase 0 selesai: dokumen dan konstitusi. Belum ada kode.

Lihat [`docs/STATUS.md`](docs/STATUS.md).
