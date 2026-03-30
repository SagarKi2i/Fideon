-- Ensure idempotent eval persistence: one row per (job_id, eval_set)
ALTER TABLE public.acord_eval_results
  DROP CONSTRAINT IF EXISTS acord_eval_results_job_eval_set_unique;

ALTER TABLE public.acord_eval_results
  ADD CONSTRAINT acord_eval_results_job_eval_set_unique UNIQUE (job_id, eval_set);

