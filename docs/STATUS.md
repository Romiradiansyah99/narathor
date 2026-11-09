# Status

Keadaan repo hari ini. Diperbarui setiap fase selesai.

---

## Ringkasan

Fase 1 sampai 6 selesai dan terverifikasi. Fase 7 dan 8 selesai sebagian: yang menunggu pustaka nyata dan golden set masih terbuka.

`uv run check` hijau: ruff, ruff format, pyright, pytest 76 lulus, coverage 80%.

---

## Yang sudah ada

| Bagian | Keadaan |
|---|---|
| `SOUL.md` + `soul.lock` | v1, hash cocok, tidak disentuh sepanjang pembangunan |
| `contracts.py` | Seluruh kontrak Pydantic di satu tempat |
| `backend/` | FastAPI + SQLAlchemy Core, 8 endpoint, seed dari `data/`, gate soul di setiap request |
| `briefs/load.py` | Parser YAML + validasi dua belas alasan penolakan |
| `ingest/` | Caption YouTube, fallback Whisper, cache per video, laporan run |
| `index/` | Segmenter, fitur heuristik, klasifikasi kind, kartu segmen |
| `agent/` | LangGraph: plan, index, match, write, critique, tujuh gate |
| `report/render.py` | `scripts/*.md`, `*.json`, `index.md`, `blocked.md`, `run.json` |
| `eval/metrics.py` | Lima metrik, golden set hanya dibaca di sini |
| `narathor/` | CLI Typer: soul, narrative, ingest, index, mine, script, report, eval, doctor, status, check |
| `tests/` | 76 test, semuanya tanpa model dan tanpa jaringan |
| `data/` | Belum ada pustaka nyata. Test memakai fixture di `tests/fixtures.py` |

---

## Metrik

| Metrik | Target | Sekarang |
|---|---|---|
| Test lulus | semua | 76 |
| Coverage | >= 80% | 80% |
| `pyright` | 0 error | 0 |
| `ruff` | bersih | bersih |
| `citation_violation_rate` | = 0 | 0 pada golden set kosong dan fixture |
| `soul_violation_rate` | = 0 | 0 pada fixture |
| `precision@10` | >= 0.6 | belum diukur, golden set belum ada |
| Biaya per run (30 naskah) | <= $5 | belum diukur, butuh pustaka nyata |

---

## Perbandingan Writer

Belum dijalankan. Menunggu golden set dan 10 `Combo` yang sama.

| Tanggal | Kandidat | Cadangan | Menang | Keputusan |
|---|---|---|---|---|
| - | `deepseek/deepseek-v4.1-flash` | `claude-sonnet-5-5` | - | Belum diuji |

---

## Soul Compliance Log

| Tanggal | Versi soul | `soul verify` | Naskah dibuang | Catatan |
|---|---|---|---|---|
| 2026-11-09 | 1 | ok | - | Soul v1, hash tidak berubah sepanjang pembangunan |

---

## Decision Log

| Tanggal | Keputusan | Alasan | Dampak |
|---|---|---|---|
| 2026-11-09 | Kontrak data di `contracts.py` di akar repo | Backend, agent, dan CLI butuh schema yang sama; satu tempat mencegah schema bercabang | Semua modul mengimpor dari sini |
| 2026-11-09 | `data/` dipisah: `channel.json`, `videos.json`, `transcripts/<video_id>.json` | `docs/` tidak menentukan bentuk pustaka; ini bentuk paling sederhana yang cocok dengan `TranscriptDoc` | Backend menyemai dari sini, tidak menulis balik |
| 2026-11-09 | Gate soul dijalankan sebagai dependency FastAPI, bukan middleware | Dependency bisa diuji dan muncul di OpenAPI; middleware menyembunyikan urutan | Setiap endpoint mengembalikan 409 saat hash tidak cocok |
| 2026-11-09 | Retry Writer dilakukan di dalam node, bukan lewat edge balik | Edge balik ke node fan-out `Send` tidak didukung bersih di LangGraph | `attempts` tercatat per combo, `deferred` setelah dua percobaan |
| 2026-11-09 | `critique` merangkap iterasi kedua | Menjaga graf tetap asiklik dan mudah diuji tanpa model | Maks dua iterasi, lalu `deferred` dan dilaporkan |
| 2026-11-09 | `brand_fit` deterministik memakai irisan kata dengan stemming ringan | Anchor di `NARRATIVE.md` masih dipakai; versi ini pengganti sementara saat model belum dipanggil | Ambang 0.12 untuk skor 5, 0.05 untuk skor 3 |
| 2026-11-09 | Coverage diukur dengan `omit = ["data/*", "tests/*"]` | Pola `*/data/*` ikut memotong seluruh repo karena repo berada di `/opt/data` | Coverage 80% terbaca benar |

---

## Risks aktif

| Risiko | Keadaan |
|---|---|
| Writer murah menghasilkan prosa datar | Belum terukur; butuh golden set dan model nyata |
| Pustaka `data/` masih kosong | Menunggu bos menyebut channel pertama |
| Golden set belum ada | Harus ditandai manusia, 10-20 momen per brief |
| `interrupt()` LangGraph belum dipakai | Iterasi kedua jatuh ke `deferred`, bukan menunggu keputusan bos |
| Resume setelah kill belum diuji | Checkpointer `MemorySaver`, belum ada test crash-resume |
| `review Feb 2027` untuk `ALGORITHM.md` | Di luar kendali kode |

---

## Open Questions

1. **Channel pertama.** Brief contoh memakai `@example`. Channel nyata mana untuk run pertama?
2. **Golden set.** Siapa menandai 10-20 momen layak per brief?
3. **Montage.** `output.montages` masih 0 di semua brief. Masuk MVP atau fase berikutnya?
4. **Bahasa kedua.** `output.language` hanya `id`. Perlu `en`?

---

## Cara menjalankan

```bash
uv sync --extra dev
uv run narathor soul verify
uv run narathor doctor
uv run narathor narrative check cerdaskan-bangsa
uv run narathor ingest --narrative cerdaskan-bangsa
uv run narathor index  --narrative cerdaskan-bangsa
uv run narathor mine   --narrative cerdaskan-bangsa --top 50
uv run narathor script --narrative cerdaskan-bangsa --count 30 --concurrency 5
uv run narathor report --narrative cerdaskan-bangsa
uv run narathor eval   --narrative cerdaskan-bangsa
uv run narathor check
```
