-- Enable Supabase Realtime for the devices table so the UI receives
-- live status updates (online → offline) without polling.
ALTER PUBLICATION supabase_realtime ADD TABLE devices;
