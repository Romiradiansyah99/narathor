# Tech Stack

Bentuk sistem dan alasan di baliknya. Versi, bagian, dan batasan.

---

## 1. Bagian sistem

```
narathor/     CLI (Typer). Tipis: memanggil backend, mencetak progress
backend/      FastAPI + SQLAlchemy Core. Satu-satunya pintu ke data
agent/        LangGraph. Lima peran, fan-out, checkpointer
data/         Read-only. Pustaka video, transkrip, eval key
prompts/      Prompt per tahap, dengan prompt_version
output/       Artefak hasil run
briefs/       Narrative Brief milik bos
dashboard/    React + Vite + TS. Fase 2, belum dibangun
e2e/          Playwright. Fase 2, belum dibangun
```

**Backend adalah satu-satunya pintu ke data.** Agent tidak pernah membaca `data/` atau database secara langsung. Ia memanggil API. Ini yang membuat invarian bisa ditegakkan: soul check, gate sitasi, dan cap konkurensi semuanya lewat backend.

---

## 2. Python

Python 3.12, dikelola `uv`. Semua dependency di `pyproject.toml` root.

| Pustaka | Peran | Alasan |
|---|---|---|
| `fastapi` | API backend | Ringan, tipe jelas, otomatis OpenAPI |
| `sqlalchemy` (Core) | Akses database | Satu query untuk SQLite dan Postgres |
| `pydantic` v2 | Kontrak data | Validasi dan serialisasi JSON |
| `typer` | CLI | Argumen bertipe tanpa boilerplate |
| `pyyaml` | Brief parsing | Format brief yang dapat dibaca manusia |
| `httpx` | Klien HTTP | Dipakai CLI dan agent |
| `langchain` | `create_agent` | Supervisor dan tool-use |
| `langgraph` | `StateGraph`, `Send`, checkpointer, `interrupt()` | Graf per peran dan durabilitas |
| `yt-dlp` | Unduh audio/caption | Fallback bila caption tidak tersedia |
| `youtube-transcript-api` | Ambil caption | Jalur cepat, tanpa unduh |
| `faster-whisper` | Transkrip fallback | Opsional; hanya dipakai bila caption buruk |
| `jinja2` | Template laporan | `index.md`, naskah `.md` |
| `pytest` | Test | Stub model, tanpa jaringan |
| `ruff` | Lint + format | Satu alat untuk dua pekerjaan |
| `pyright` | Type check | Ketat |
| `langfuse` | Tracing | Opsional, mati saat key absen |

**Alternatif yang ditolak:**

- *ORM penuh (Django, SQLModel)* — abstraksi berlebih untuk query sederhana. Core cukup.
- *Celery/Redis untuk worker* — fan-out ditangani LangGraph; menambah broker hanya menambah bagian yang bisa rusak.
- *Whisper API berbayar* — fallback lokal sudah cukup dan tidak menambah ketergantungan.
- *Framework agent lain* — `create_agent` + `StateGraph` sudah menutup kebutuhan; referensi proyek juga memakai jalur ini.

---

## 3. Node & browser

| Pustaka | Peran | Status |
|---|---|---|
| Node 26 | Runtime tooling | Dipakai |
| React + Vite + TS | Dashboard | Fase 2 |
| Playwright | E2E | Fase 2 |

TypeScript strict, tanpa `any`. Script `package.json` ditulis sebagai `uv run` atau file `.mjs` agar jalan di Windows.

---

## 4. Model

Ringkasan; detail di `docs/MODELS.md`.

| Peran | Model | Biaya per run |
|---|---|---|
| Indexer | tanpa LLM | $0 |
| Curator, Matcher, Writer | `deepseek/deepseek-v4.1-flash` | ~$3.0 gabungan |
| Critic | `claude-haiku-5-5` | ~$0.1 |
| Eval | `stealth/crouton-alpha` | $0 |
| Cadangan Writer | `claude-sonnet-5-5` | +$32 bila diaktifkan |

Writer mendominasi ~84% biaya. Hanya keputusan model Writer yang signifikan secara ekonomi.

---

## 5. Database

SQLite untuk pengembangan dan test; Postgres untuk data nyata.

- Tabel di schema `narathor`.
- `MetaData(schema="narathor")` + `schema_translate_map={"narathor": None}` → query tanpa kualifikasi, jalan di keduanya.
- Maksimal 4 koneksi per proses.
- Test tidak pernah menyentuh jaringan.
- File SQLite dapat dihapus untuk reset; tidak ada kode migrasi.

Tabel inti: `channels`, `videos`, `transcripts`, `segments`, `combos`, `scripts`, `citations`, `audits`, `runs`, `agent_calls`, `cache`.

---

## 6. API

Setiap operasi wajib punya `operation_id`, docstring satu baris, dan tanpa input opsional. Input opsional menyembunyikan perilaku dan mempersulit test.

Contoh:

```python
@app.get("/api/videos", operation_id="list_videos")
def list_videos():
    """Daftar video dalam pustaka."""
```

Bentuk ringkas:

| Method | Path | operation_id |
|---|---|---|
| GET | `/api/health` | `health` |
| GET | `/api/soul` | `get_soul_status` |
| GET | `/api/briefs` | `list_briefs` |
| GET | `/api/briefs/{brief_id}` | `get_brief` |
| GET | `/api/videos` | `list_videos` |
| GET | `/api/videos/{video_id}` | `get_video` |
| GET | `/api/segments` | `list_segments` |
| POST | `/api/runs` | `start_run` |
| GET | `/api/runs/{run_id}` | `get_run` |
| POST | `/api/runs/{run_id}/finish` | `finish_run` |
| POST | `/api/runs/{run_id}/fail` | `fail_run` |
| PUT | `/api/units/{unit_id}/result` | `record_unit_result` |
| POST | `/api/scripts` | `save_script` |
| GET | `/api/scripts/{script_id}` | `get_script` |

---

## 7. Environment

`.env` di root, masuk `.gitignore`. `.env.example` berisi nama variabel tanpa nilai.

| Variabel | Wajib | Default | Dipakai di |
|---|---|---|---|
| `COMMAND_CODE_API_KEY` | ya | — | Semua panggilan model |
| `DATABASE_URL` | tidak | — | Postgres; tanpa ini pakai SQLite |
| `NARATHOR_DB` | tidak | `narathor.db` | Path SQLite |
| `MODEL_WRITER` | tidak | `deepseek/deepseek-v4.1-flash` | Writer |
| `MODEL_MATCHER` | tidak | `deepseek/deepseek-v4.1-flash` | Matcher |
| `MODEL_CRITIC` | tidak | `claude-haiku-5-5` | Critic |
| `MODEL_CURATOR` | tidak | `deepseek/deepseek-v4.1-flash` | Curator |
| `MODEL_NAME` | tidak | — | Override borongan |
| `LANGFUSE_PUBLIC_KEY` | tidak | — | Tracing |
| `LANGFUSE_SECRET_KEY` | tidak | — | Tracing |
| `MAX_CONCURRENCY` | tidak | `5` | Fan-out |

**Catatan ketidakkonsistenan referensi.** `00. Plan Build References/TECH_STACK.md` menulis `COMMANDCODE_API_KEY`, sedangkan `PLAN.md` menulis `COMMAND_CODE_API_KEY`. Yang dipakai di sini: **`COMMAND_CODE_API_KEY`**, sesuai dokumentasi headless Command Code. Jangan memakai dua nama sekaligus.

Tanpa `LANGFUSE_*`, tracing mati total. Test tidak pernah membutuhkan jaringan.

---

## 8. Batasan Windows

Diperlukan karena mesin pengembangan utama Windows:

- Semua script lewat `uv run` atau file `.mjs`; tidak ada `python3`.
- Path selalu `pathlib.Path`. Tidak ada string path yang dirangkai manual.
- Checkpointer sinkron. Checkpointer async Postgres tidak bekerja dengan event loop bawaan Windows.
- Encoding eksplisit `utf-8` saat membaca dan menulis file. Default Windows bukan utf-8.
- PowerShell untuk contoh perintah; `curl` sebagai alternatif di catatan, bukan asumsi.

---

## 9. Output

```
output/<narrative_id>/<channel>/
  scripts/<script_id>.json       kontrak untuk mesin render (Fase 2)
  scripts/<script_id>.md         versi baca manusia
  index.md                       semua naskah, terurut skor
  blocked.md                     segmen yang dibuang + pasal yang dilanggar
  segments.jsonl                 kartu segmen
  combos.json                    combo dan skornya
  run.json                       soul_version, brief_hash, model per peran, waktu
```

Artefak tanpa `run.json` tidak boleh ditulis. Tanpa jejak, keluaran tidak dapat direproduksi.

### 9.1 Keluaran `narathor script`

Perintah ini tidak mencetak naskah ke stdout. Ia menulis artefak dan mencetak ringkasan:

```
narathor script --narrative cerdaskan-bangsa --count 30 --workers 5

run_2026-11-09T142233  cerdaskan-bangsa  @example
  unit: 30 diminta   27 selesai   2 dikembalikan   1 ditunda
  gate : satu_tesis 27/27 · terlacak 27/27 · dibayar 25/27
  biaya: $2.61 (writer 84%)
  output: output/cerdaskan-bangsa/example/
```

Detail per naskah ada di `index.md`; yang gagal ada di `index.md` bagian "dikembalikan" beserta gate yang gagal dan alasannya.

Exit code: `0` bila minimal satu naskah lolos, `1` bila semua gagal, `2` bila brief atau soul ditolak.

---

## 10. Pemeriksaan

Satu perintah menjalankan semua:

```bash
uv run check    # ruff format, ruff check, pyright, pytest --cov (min 80%)
```

Aturan: jangan menurunkan threshold, mematikan aturan, atau mengecualikan file agar hijau. Kalau sebuah aturan terasa salah, hentikan dan tanyakan.

Test wajib memakai stub model. Tidak ada test yang memanggil model nyata, dan tidak ada test yang membaca `data/eval/`.
