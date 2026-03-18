-- Production hardening for the devices table.
--
-- 1. Composite index used by the offline detector sweep:
--      WHERE status = 'online' AND last_seen_at < <threshold>
--    The two existing single-column indexes (idx_devices_status,
--    idx_devices_last_seen) force PostgreSQL into an index intersection or a
--    sequential scan on large tables. A composite index eliminates that.
--
-- 2. jwt_issued_after — soft JWT revocation without a blocklist table.
--    The backend sets this to NOW() whenever a new device token is issued.
--    The heartbeat endpoint rejects any JWT whose `iat` predates this value,
--    which means re-registering a device automatically invalidates all
--    previously issued tokens for that device.
--    Admins can also set it to NOW() to immediately revoke all active tokens.

CREATE INDEX IF NOT EXISTS idx_devices_status_last_seen
    ON public.devices (status, last_seen_at DESC);

ALTER TABLE public.devices
    ADD COLUMN IF NOT EXISTS jwt_issued_after TIMESTAMPTZ
    NOT NULL DEFAULT '1970-01-01T00:00:00Z';
