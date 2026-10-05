-- R4 持久化后台执行身份和终态；不复制 history snapshot /成功上下文。
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'history_records_id_owner_unique'
          AND conrelid = 'history_records'::regclass
    ) THEN
        ALTER TABLE history_records
            ADD CONSTRAINT history_records_id_owner_unique UNIQUE (id, owner_user_id);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS history_executions (
    id UUID PRIMARY KEY,
    owner_user_id BIGINT NOT NULL,
    history_id UUID NOT NULL,
    turn_id UUID NOT NULL,
    operation_id UUID NOT NULL,
    request_hash CHAR(64) NOT NULL,
    mode TEXT NOT NULL CONSTRAINT history_execution_mode CHECK (mode IN ('query', 'analysis')),
    operation_kind TEXT NOT NULL CONSTRAINT history_execution_operation_kind
        CHECK (operation_kind IN ('query', 'analysis_resume', 'history_requery', 'saved_result_requery')),
    status TEXT NOT NULL CONSTRAINT history_execution_status
        CHECK (status IN ('accepted', 'running', 'stopping', 'succeeded', 'failed', 'cancelled', 'timed_out', 'unconfirmed')),
    stop_reason TEXT,
    runtime_epoch UUID NOT NULL,
    execution_generation BIGINT NOT NULL CONSTRAINT history_execution_generation CHECK (execution_generation > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    deadline_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    public_error JSONB,
    CONSTRAINT history_execution_owner_history_fk
        FOREIGN KEY (history_id, owner_user_id)
        REFERENCES history_records(id, owner_user_id) ON DELETE CASCADE,
    CONSTRAINT history_execution_history_turn_fk
        FOREIGN KEY (history_id, turn_id)
        REFERENCES history_turns(history_id, id) ON DELETE CASCADE,
    UNIQUE (owner_user_id, operation_id),
    UNIQUE (history_id, turn_id)
);

CREATE INDEX IF NOT EXISTS history_executions_owner_created_idx
    ON history_executions(owner_user_id, created_at DESC, id DESC);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE history_executions TO chatbi_control_user;

INSERT INTO schema_migrations(version)
VALUES ('chatbi-control-v4')
ON CONFLICT (version) DO NOTHING;
