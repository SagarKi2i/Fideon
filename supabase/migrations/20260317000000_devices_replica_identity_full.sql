-- Enable REPLICA IDENTITY FULL on the devices table so that Supabase Realtime
-- includes both old and new row values in UPDATE event payloads.
-- This allows the frontend to compare old.status vs new.status and skip
-- unnecessary re-fetches on heartbeat-only updates (last_seen_at changes).
ALTER TABLE devices REPLICA IDENTITY FULL;
