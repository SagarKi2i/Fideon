# CI/CD Production Readiness Report

Assessment of `.github/workflows/` for production readiness. Use this as a checklist before going live.

---

## Executive summary

| Area | Status | Notes |
|------|--------|--------|
| **Branch/path consistency** | ⚠️ Needs fix | Two parallel stacks; some workflows reference non-existent `neurapod-app` |
| **Deploy safety** | ✅ Good | Production uses manual approval, blue/green, rollback on failure |
| **Security** | ✅ Good | Trivy, CodeQL, dependency review, SBOM, license deny list |
| **Secrets & config** | ⚠️ Minor | Prefer env for secrets in scripts; ensure all required secrets are set |
| **Testing** | ⚠️ Paths/coverage | Coverage threshold and paths depend on repo layout |
| **Database** | ⚠️ Minor | Migrations workflow has optional schema test path; secret handling improved |

---

## 1. Branch and path consistency (critical)

You have **two parallel CI/CD stacks** that don’t fully match this repo:

### Stack A – NeuraPod (main / develop)

- **Workflows:** `ci.yml`, `deploy-staging.yml`, `deploy-production.yml`
- **Paths:** `neurapod-app/`, `defaults.run.working-directory: neurapod-app`
- **Registry:** `ghcr.io` (GitHub Container Registry)
- **Deploy:** Azure Web App (slots, blue/green)

**Issue:** This repo has **`frontend/`** and **`backend/`**, not **`neurapod-app/`**. These workflows will fail on checkout/build unless you either:

- Rename or symlink `frontend` → `neurapod-app`, or  
- Change all references from `neurapod-app` to `frontend` in:
  - `ci.yml` (working-directory, Docker context/file, coverage paths)
  - `deploy-staging.yml` (working-directory, smoke test path)
  - `deploy-production.yml` (working-directory, smoke test path)

### Stack B – Fideon (v1-dev / v1-staging / v1)

- **Workflows:** `backend-ci.yml`, `frontend-ci.yml`, `deploy-env.yml`, `release-train.yml`, `hotfix-pipeline.yml`
- **Paths:** `frontend/`, `backend/`
- **Registry:** `neurapodacr.azurecr.io` (Azure Container Registry)
- **Deploy:** Azure VM via SSH

**Issue:** `hotfix-pipeline.yml` still uses **`neurapod-app/`** for the frontend (paths, Docker context, image name). For this repo it should use **`frontend/`** and image name `frontend` (or whatever you use in `deploy-env.yml`).

**Recommendation:** Pick one primary flow for “production” and align branch names and paths:

- Either standardize on **main/develop** and **frontend/** (no `neurapod-app`), or  
- Keep **v1-dev / v1-staging / v1** and ensure every workflow uses **frontend/** and **backend/** only.

---

## 2. Production deploy safety ✅

- **Manual gate:** `deploy-production.yml` uses `environment: production-approval` (CODEOWNERS/manual approval).
- **Blue/green:** Deploy to blue slot → health check → swap → post-swap health check.
- **Rollback:** Automatic rollback on health-check failure and on smoke-test failure.
- **Concurrency:** `cancel-in-progress: false` so production deploys are not cancelled mid-run.
- **Pre-flight:** Verifies image exists in registry before deploy.

---

## 3. Security ✅

- **Trivy:** Container scan (CRITICAL/HIGH), SARIF uploaded to GitHub Security.
- **CodeQL:** JavaScript/TypeScript, security-and-quality.
- **Dependency review:** PRs (when run in PR context); fail on high severity; GPL-3.0, LGPL-3.0, AGPL-3.0 denied.
- **npm audit:** Scheduled weekly; fails on high+.
- **SBOM:** Generated and stored (90-day retention).
- **Secrets:** No secrets in logs; use `env` for sensitive values in scripts where possible.

---

## 4. Required secrets and variables

Ensure these are set in GitHub (and in Azure where applicable):

| Secret / Var | Used in | Purpose |
|--------------|--------|---------|
| `AZURE_CREDENTIALS` | deploy-production, deploy-staging | Azure login (Web App) |
| `AZURE_CR_PASSWORD` / `AZURE_CR_USERNAME` | backend-ci, frontend-ci, deploy-env, hotfix | ACR push/pull |
| `CHATBOT_SERVER_KEY` | deploy-env, hotfix | SSH key for VM deploy |
| `AZURE_VM_HOST` / `AZURE_VM_USERNAME` | deploy-env, hotfix | VM SSH |
| `SLACK_WEBHOOK_URL` | Multiple | Notifications |
| `PROD_SUPABASE_*` / `STAGING_SUPABASE_*` | deploy-*, db-migrate | Supabase config |
| `TEST_SUPABASE_*`, `E2E_TEST_EMAIL`, `E2E_TEST_PASSWORD` | ci.yml | Tests |
| `SONAR_TOKEN` / `SONAR_HOST_URL` | backend-ci, ci-component | SonarQube (optional) |
| `SUPABASE_ACCESS_TOKEN` | db-migrate | Supabase CLI |

---

## 5. Testing and coverage

- **CI:** Lint, typecheck, unit tests, E2E (Playwright), coverage threshold (e.g. 80% in `ci.yml`).
- **Coverage path:** `ci.yml` reads `coverage/coverage-summary.json` and uses `defaults.run.working-directory: neurapod-app`. If you switch to `frontend/`, ensure Vitest (or your test runner) writes coverage under that directory (or adjust the path and threshold).
- **Smoke tests:** `deploy-staging.yml` and `deploy-production.yml` run `tests/smoke.spec.ts`. In this repo, smoke-style tests live under **`frontend/tests/*.smoke.*`**. Update the Playwright config and workflow `run` command to point at the actual test path (e.g. `frontend/tests/` and the right spec files).
- **Optional:** Add a job that fails the workflow when coverage drops below threshold (you already have a check; ensure the path exists after moving off `neurapod-app`).

---

## 6. Database migrations

- **db-migrate.yml:** Manual dispatch, dry run by default, production behind `production-approval` environment.
- **Post-migration:** Runs `supabase/seed/schema_tests.sql` if present. That file is not in this repo; add it or remove/guard that step to avoid failures.
- **Secrets:** Project ref and DB password are now passed via `env` in the migration workflow for clearer and safer handling.

---

## 7. Dependency review in security-audit

- **dependency-review** runs on schedule and `workflow_dispatch`. The Dependency Review action is designed for **pull_request** (compare base vs head). On schedule/manual there is no PR, so the action may not behave as expected. Consider:
  - Running dependency-review only in PRs (e.g. in a separate workflow `on: pull_request`), or  
  - Keeping it but accepting that scheduled/manual runs may not add much value.

---

## 8. Notifications

- Slack alerts on CI failure (main), security audit failure, deploy result (staging/production), DB migration result.
- Ensure `SLACK_WEBHOOK_URL` is set in repo/org secrets; otherwise those steps will fail.

---

## 9. Quick checklist before production

- [ ] Resolve **neurapod-app vs frontend** (and optionally backend-only paths): either rename paths or update all workflows to use `frontend/` and `backend/`.
- [ ] Update **smoke test** paths and Playwright config to match actual test location (e.g. `frontend/tests/` and correct spec files).
- [ ] Ensure **coverage path** and **working-directory** in `ci.yml` match the app directory (e.g. `frontend` if that’s where tests run).
- [ ] Create **GitHub environments** `production-approval`, `staging`, `production` with the right protection rules (e.g. required reviewers for production).
- [ ] Add **schema_tests.sql** under `supabase/seed/` or remove/optionalize that step in `db-migrate.yml`.
- [ ] Confirm all **secrets and variables** above are set and that Slack webhook is valid.
- [ ] Pin **critical action versions** to full SHAs where possible for supply-chain safety (you already use v4/v3; consider pinning to SHA).
- [ ] Run a **full production deploy** (with approval) to a test slot or staging to validate the whole pipeline end-to-end.

---

## 10. Suggested next steps

1. **Unify app path:** Decide whether production is “main + frontend/backend” or “v1 + frontend/backend” and update every workflow to use the same directory and image names.
2. **Fix hotfix-pipeline:** Change `neurapod-app` to `frontend` (paths and image name) so hotfixes match the rest of the Fideon stack.
3. **Fix deploy-production smoke step:** Use the correct Playwright project and path (e.g. `frontend/tests/` and the right spec pattern).
4. **Document rollback:** Add a short runbook for manual rollback (which image tag to use, how to swap slots or revert on VM).

Once paths and secrets are aligned with this repo and the checklist is done, the pipeline is in good shape for production use.
