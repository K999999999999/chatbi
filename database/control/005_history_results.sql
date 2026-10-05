-- 长期历史仅保存至Control DB；显式迁移，不在请求中DDL。
CREATE TABLE IF NOT EXISTS history_records (
    id UUID PRIMARY KEY,
    owner_user_id BIGINT NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL CONSTRAINT history_record_kind CHECK (kind IN ('query', 'analysis')),
    title TEXT NOT NULL,
    first_question TEXT NOT NULL,
    creation_operation_id UUID NOT NULL,
    creation_operation_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    context_revision BIGINT NOT NULL DEFAULT 0 CONSTRAINT history_context_revision CHECK (context_revision >= 0),
    record_revision BIGINT NOT NULL DEFAULT 0 CONSTRAINT history_record_revision CHECK (record_revision >= 0),
    next_ordinal BIGINT NOT NULL DEFAULT 1 CONSTRAINT history_next_ordinal CHECK (next_ordinal > 0),
    last_success_turn_id UUID,
    active_turn_id UUID,
    execution_generation BIGINT NOT NULL DEFAULT 0 CONSTRAINT history_generation CHECK (execution_generation >= 0),
    analysis_run_id UUID UNIQUE,
    deleted_at TIMESTAMPTZ,
    UNIQUE (owner_user_id, creation_operation_id),
    CONSTRAINT history_analysis_identity CHECK ((kind = 'analysis') = (analysis_run_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS history_records_owner_updated_idx
    ON history_records(owner_user_id, kind, updated_at DESC, id DESC) WHERE deleted_at IS NULL;
CREATE TABLE IF NOT EXISTS history_turns (
    id UUID PRIMARY KEY,
    history_id UUID NOT NULL REFERENCES history_records(id),
    ordinal BIGINT NOT NULL CONSTRAINT history_turn_ordinal CHECK (ordinal > 0),
    operation_id UUID NOT NULL,
    operation_hash CHAR(64) NOT NULL,
    question TEXT NOT NULL,
    request_id TEXT NOT NULL,
    status TEXT NOT NULL CONSTRAINT history_turn_status CHECK (status IN ('accepted', 'succeeded', 'failed', 'unconfirmed')),
    runtime_epoch UUID NOT NULL,
    execution_generation BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    public_error JSONB,
    attempt_input JSONB,
    snapshot_version INTEGER,
    snapshot JSONB,
    UNIQUE (history_id, ordinal),
    UNIQUE (history_id, operation_id),
    UNIQUE (history_id, id),
    CONSTRAINT history_turn_success_snapshot CHECK ((status = 'succeeded') = (snapshot IS NOT NULL)),
    CONSTRAINT history_turn_snapshot_version CHECK (snapshot IS NULL OR snapshot_version = 1)
);
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'history_active_turn_fk' AND conrelid='history_records'::regclass) THEN
        ALTER TABLE history_records ADD CONSTRAINT history_active_turn_fk
            FOREIGN KEY (id, active_turn_id) REFERENCES history_turns(history_id, id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'history_success_turn_fk' AND conrelid='history_records'::regclass) THEN
        ALTER TABLE history_records ADD CONSTRAINT history_success_turn_fk
            FOREIGN KEY (id, last_success_turn_id) REFERENCES history_turns(history_id, id);
    END IF;
END $$;
CREATE TABLE IF NOT EXISTS saved_results (
    id UUID PRIMARY KEY,
    owner_user_id BIGINT NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL CONSTRAINT saved_kind CHECK (kind IN ('query', 'analysis')),
    title TEXT NOT NULL,
    record_revision BIGINT NOT NULL DEFAULT 0 CONSTRAINT saved_revision CHECK (record_revision >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_history_id UUID NOT NULL,
    source_turn_id UUID NOT NULL,
    snapshot_version INTEGER NOT NULL CONSTRAINT saved_snapshot_version CHECK (snapshot_version = 1),
    snapshot JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS saved_results_owner_updated_idx
    ON saved_results(owner_user_id, kind, updated_at DESC, id DESC);
CREATE TABLE IF NOT EXISTS history_runtime (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CONSTRAINT history_singleton CHECK (singleton),
    runtime_epoch UUID NOT NULL
);
GRANT SELECT, INSERT, UPDATE, DELETE ON history_records, history_turns, saved_results TO chatbi_control_user;
GRANT SELECT, INSERT, UPDATE ON history_runtime TO chatbi_control_user;
INSERT INTO schema_migrations(version) VALUES ('chatbi-control-v3') ON CONFLICT (version) DO NOTHING;
