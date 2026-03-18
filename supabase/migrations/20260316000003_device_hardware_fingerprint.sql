-- Add hardware_fingerprint_hash column to devices table for idempotent device registration.
-- The column stores a SHA-256 hash of the raw hardware fingerprint (never the raw value).
-- UNIQUE constraint ensures one device record per physical device.
-- Nullable to preserve backward compatibility with existing devices created via pairing.

ALTER TABLE devices
  ADD COLUMN IF NOT EXISTS hardware_fingerprint_hash TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS devices_hardware_fingerprint_hash_key
  ON devices (hardware_fingerprint_hash)
  WHERE hardware_fingerprint_hash IS NOT NULL;

COMMENT ON COLUMN devices.hardware_fingerprint_hash IS
  'SHA-256 hex digest of the device hardware fingerprint. NULL for devices created via pairing flow.';
