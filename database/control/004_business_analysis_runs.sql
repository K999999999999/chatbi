-- Business Analysis run ownership and expiry registry.
-- Checkpoint payload tables are installed by the pinned LangGraph saver migration.
CREATE TABLE IF NOT EXISTS business_analysis_runs (
    analysis_run_id UUID PRIMARY KEY,
    owner_subject TEXT NOT NULL,
    question_sha256 CHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS business_analysis_runs_expiry_idx
    ON business_analysis_runs(expires_at);

GRANT SELECT, INSERT, UPDATE ON TABLE business_analysis_runs TO chatbi_control_user;

INSERT INTO schema_migrations(version)
VALUES ('chatbi-control-v2')
ON CONFLICT (version) DO NOTHING;
