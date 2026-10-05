-- Ticket 03 records the durable time at which the first stop reason won.
ALTER TABLE history_executions
    ADD COLUMN IF NOT EXISTS stop_requested_at TIMESTAMPTZ;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE history_executions TO chatbi_control_user;

INSERT INTO schema_migrations(version)
VALUES ('chatbi-control-v5')
ON CONFLICT (version) DO NOTHING;
