## ACORD Form Understanding workflow (runbook)

This repo implements a human-in-the-loop extraction workflow:

- **User uploads document** → backend extracts text + fields (+ confidence)
- **User reviews** extracted fields and submits thumbs up/down + corrections
- **System routes**:
  - High confidence + thumbs up → **Approved**
  - Otherwise → **Admin queue**
- **Admin reviews/corrects** and approves/reworks/rejects
- **Approved runs** can be exported to JSONL for manual fine-tuning

### Manual human-in-the-loop training truth

For ACORD manual learning loop, training is based on the final corrected JSON:

1. User uploads document and reviews extraction.
2. If extraction is acceptable, stop (no fine-tuning required).
3. If fields are missing/wrong/null, user edits JSON and submits for review.
4. On admin approval, backend resolves final training truth with priority:
   - admin `corrected_json` in the approval request
   - else most recent `corrected_json` from feedback history
   - else current `acord_extraction_runs.extracted_json`
5. That resolved JSON is persisted into `acord_extraction_runs.extracted_json` and used for dataset export/fine-tuning.

### Backend env vars (required)

In `backend/.env`:

- **Supabase**:
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY`
  - `SUPABASE_SERVICE_ROLE_KEY`
- **LLM (structured ACORD extraction)** — pick one path:

  **A) RunPod / Ollama-style `/generate` (default stack: Qwen2.5-14B-Instruct, no OpenAI key)**  
  - `OFFLINE_LLM_GENERATE_URL` — full URL to your server’s generate endpoint (or use `RUNPOD_GENERATE_URL` as an alias)  
  - `OFFLINE_LLM_MODEL_NAME` — model id your server expects (e.g. `Qwen/Qwen2.5-14B-Instruct` or `/workspace/models/qwen2.5-14b-instruct`)  
  - Optional: `OFFLINE_LLM_AUTH_TOKEN` if the endpoint requires `Authorization: Bearer …`  
  - Leave `OPENAI_API_KEY` empty; the backend will call the offline URL automatically when it is set and no API key is present.  
  - Optional: `ACORD_STRICT_LLAMA8B_ONLY=true` to **force** offline only (legacy name; fails if offline URL envs are missing).

  **B) OpenAI-compatible chat (RunPod vLLM, OpenAI, etc.)**  
  - `OPENAI_API_KEY` (use a placeholder if your server ignores auth)  
  - `OPENAI_CHAT_COMPLETIONS_URL` — e.g. `https://<pod>/v1/chat/completions`  
  - Or set `RUNPOD_OPENAI_COMPAT_URL` instead of `OPENAI_CHAT_COMPLETIONS_URL` (same effect in `app.core.config`)  
  - `OPENAI_MODEL` — must match the served model name (e.g. `Qwen/Qwen2.5-14B-Instruct`)
- **Vector store (RAG)** (optional, separate from fine-tuning):
  - `PGVECTOR_DATABASE_URL` (or `DATABASE_URL`)
  - `PGVECTOR_TABLE` (default `rag_chunks`)

### Optional: ByteScout PDF Extractor (CLI) for PDF ingestion (Windows-only)

If you want to use ByteScout CLI as the first-stage PDF extractor (before `pdfplumber` / OCR), set:

- `BYTESCOUT_ENABLED=true`
- `BYTESCOUT_CLI_PATH=C:\\Path\\To\\ByteScoutCli.exe`
- `BYTESCOUT_CMD_TEMPLATE="\"{cli}\" <args> \"{input_pdf}\" <args> \"{output_txt}\""`
- `BYTESCOUT_TIMEOUT_SECS=30`
- `BYTESCOUT_MAX_PAGES=20`
- `BYTESCOUT_TMP_DIR=D:\\fideon_tmp` (optional)

Notes:
- `BYTESCOUT_CMD_TEMPLATE` is intentionally **configurable** because ByteScout has multiple CLI tools with different flags.
- You can provide **multiple templates** separated by `||` and the backend will try them in order.
- Supported placeholders: `{cli}`, `{input_pdf}`, `{output_txt}`, `{output_dir}`, `{max_pages}`.
- If you set `BYTESCOUT_CLI_PATH` but leave `BYTESCOUT_CMD_TEMPLATE` empty, the backend will try a set of **best-effort default templates** based on the exe name (e.g. `pdf2text.exe` / `pdftotext.exe` patterns).
- Your template **must write extracted text** to `{output_txt}`.
- If ByteScout fails / times out / produces too little text, the backend automatically falls back to `pdfplumber` and then to OCR.

### Supabase migrations

Apply migrations from repo root:

```bash
npx supabase@latest db push --workdir .
```

The ACORD workflow tables are created by:
- `supabase/migrations/20260318120000_acord_extraction_workflow.sql`

### Backend endpoints

All endpoints require `Authorization: Bearer <supabase_access_token>`.

- **Extract + persist draft run**: `POST /api/acord/extract`
  - multipart form: `file`
- **Get run**: `GET /api/acord/runs/{run_id}`
- **User submit (thumbs + corrections)**: `POST /api/acord/runs/{run_id}/submit`
  - JSON: `{ thumbs_up: boolean, notes?: string, corrected_json?: object }`
- **Admin queue**: `GET /api/acord/admin/queue` (admin only)
- **Admin review**: `POST /api/acord/admin/{run_id}/review` (admin only)
  - JSON: `{ decision: 'approve'|'rework'|'reject', notes?: string, corrected_json?: object }`

### Frontend

- User flow is available in **Playground → ACORD Parser**.
- Admin flow is available in **Sidebar → Admin → ACORD Review**.

### Export approved dataset (manual fine-tuning)

From `backend/` (venv activated):

```bash
python -m fine_tuning.export_approved_acord_dataset --out fine_tuning/data/approved_acord.jsonl
python -m fine_tuning.run_pipeline --config fine_tuning/config.yaml --dataset fine_tuning/data/approved_acord.jsonl
```

### Automatic fine-tuning on admin approval

When an admin approves an ACORD run, the backend will:
- create a row in `public.acord_training_jobs`
- spawn `python -m fine_tuning.job_runner --job-id ... --run-id ...`

Env vars:
- `AUTO_FINE_TUNE_ON_ACORD_APPROVAL=true` (default true)
- `FINE_TUNING_CONFIG_PATH=fine_tuning/config.yaml` (optional override)
- `FT_QUALITY_GATE_ENABLED=true` (default true)
- `FT_QUALITY_GATE_ENFORCE_ACORD=true` (default true; enforce JSON extraction quality gates for ACORD jobs too)

Quality gate metrics (from `fine_tuning/evaluate.py`) are JSON-centric for extraction:
- `json_valid_rate` (prediction parses as JSON)
- `json_exact_match` (parsed JSON equals reference)
- `json_field_recall` (reference field-path coverage)
- `json_extra_field_rate` (hallucinated fields)
- `out_of_scope.hallucination_rate`

If a training job fails these thresholds, the job is marked failed and the model is not promoted.

Artifacts:
- datasets + adapters + logs are written under `backend/fine_tuning/runs/`

### Confidence + feedback evaluation

`GET /api/acord/runs/{run_id}` returns:
- stored extraction `overall_confidence` (model-side score)
- `confidence_evaluation` (derived signal combining confidence + feedback/edit history)

`confidence_evaluation` includes:
- `base_confidence`
- `calibrated_confidence`
- `adjustment` + `reasons`
- `feedback_signals` (`corrections_count`, latest thumbs-up/down, etc.)

