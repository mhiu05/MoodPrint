BEGIN;

CREATE TABLE moodprint.alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_foundation

CREATE TABLE moodprint.users (
    id UUID NOT NULL, 
    auth_subject UUID NOT NULL, 
    alias VARCHAR(40) NOT NULL, 
    age_band VARCHAR(12) NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    timezone VARCHAR(64) NOT NULL, 
    auth_version INTEGER NOT NULL, 
    data_version INTEGER NOT NULL, 
    profile_version INTEGER NOT NULL, 
    CONSTRAINT pk_users PRIMARY KEY (id), 
    CONSTRAINT ck_users_age_band CHECK (age_band in ('unknown','under16','teen','adult')), 
    CONSTRAINT uq_users_auth_subject UNIQUE (auth_subject)
);

CREATE TABLE moodprint.ai_runs (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    conversation_id UUID NOT NULL, 
    bot_id VARCHAR(16) NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_ai_runs PRIMARY KEY (id), 
    CONSTRAINT fk_ai_runs_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_ai_runs_conversation_id ON moodprint.ai_runs (conversation_id);

CREATE INDEX ix_ai_runs_user_id ON moodprint.ai_runs (user_id);

CREATE UNIQUE INDEX uq_ai_active_conversation ON moodprint.ai_runs (conversation_id) WHERE status = 'running';

CREATE TABLE moodprint.auth_sessions (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    csrf_hash VARCHAR(64) NOT NULL, 
    provider_session_id UUID NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    revoked BOOLEAN NOT NULL, 
    auth_version INTEGER NOT NULL, 
    CONSTRAINT pk_auth_sessions PRIMARY KEY (id), 
    CONSTRAINT fk_auth_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id), 
    CONSTRAINT uq_auth_sessions_token_hash UNIQUE (token_hash)
);

CREATE INDEX ix_auth_sessions_expires_at ON moodprint.auth_sessions (expires_at);

CREATE INDEX ix_auth_sessions_user_id ON moodprint.auth_sessions (user_id);

CREATE TABLE moodprint.blocks (
    blocker_id UUID NOT NULL, 
    blocked_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_blocks PRIMARY KEY (blocker_id, blocked_id), 
    CONSTRAINT ck_blocks_block_distinct CHECK (blocker_id <> blocked_id), 
    CONSTRAINT fk_blocks_blocked_id_users FOREIGN KEY(blocked_id) REFERENCES moodprint.users (id), 
    CONSTRAINT fk_blocks_blocker_id_users FOREIGN KEY(blocker_id) REFERENCES moodprint.users (id)
);

CREATE TABLE moodprint.candidate_references (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    peer_id UUID NOT NULL, 
    profile_version INTEGER NOT NULL, 
    peer_profile_version INTEGER NOT NULL, 
    consent_version INTEGER NOT NULL, 
    peer_consent_version INTEGER NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_candidate_references PRIMARY KEY (id), 
    CONSTRAINT ck_candidate_references_candidate_distinct CHECK (user_id <> peer_id), 
    CONSTRAINT fk_candidate_references_peer_id_users FOREIGN KEY(peer_id) REFERENCES moodprint.users (id), 
    CONSTRAINT fk_candidate_references_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_candidate_references_expires_at ON moodprint.candidate_references (expires_at);

CREATE INDEX ix_candidate_references_user_id ON moodprint.candidate_references (user_id);

CREATE TABLE moodprint.consent_events (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    purpose VARCHAR(8) NOT NULL, 
    enabled BOOLEAN NOT NULL, 
    version INTEGER NOT NULL, 
    policy_version VARCHAR(32) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_consent_events PRIMARY KEY (id), 
    CONSTRAINT fk_consent_events_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_consent_events_user_id ON moodprint.consent_events (user_id);

CREATE TABLE moodprint.consents (
    user_id UUID NOT NULL, 
    purpose VARCHAR(8) NOT NULL, 
    enabled BOOLEAN NOT NULL, 
    version INTEGER NOT NULL, 
    policy_version VARCHAR(32) NOT NULL, 
    CONSTRAINT pk_consents PRIMARY KEY (user_id, purpose), 
    CONSTRAINT ck_consents_purpose CHECK (purpose in ('AI','MEM','MATCH','VOICE')), 
    CONSTRAINT fk_consents_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

CREATE TABLE moodprint.idempotency_keys (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    operation VARCHAR(120) NOT NULL, 
    key VARCHAR(128) NOT NULL, 
    digest VARCHAR(64) NOT NULL, 
    receipt JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_idempotency_keys PRIMARY KEY (id), 
    CONSTRAINT fk_idempotency_keys_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id), 
    CONSTRAINT uq_idempotency_keys_user_id UNIQUE (user_id, operation, key)
);

CREATE TABLE moodprint.matching_drafts (
    user_id UUID NOT NULL, 
    payload JSONB NOT NULL, 
    version INTEGER NOT NULL, 
    preview_digest VARCHAR(64), 
    preview_expires_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_matching_drafts PRIMARY KEY (user_id), 
    CONSTRAINT fk_matching_drafts_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

CREATE TABLE moodprint.moods (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    local_date DATE NOT NULL, 
    value INTEGER NOT NULL, 
    note VARCHAR(120) NOT NULL, 
    timezone VARCHAR(64) NOT NULL, 
    version INTEGER NOT NULL, 
    CONSTRAINT pk_moods PRIMARY KEY (id), 
    CONSTRAINT ck_moods_value CHECK (value between 1 and 5), 
    CONSTRAINT fk_moods_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id), 
    CONSTRAINT uq_moods_user_id UNIQUE (user_id, local_date)
);

CREATE TABLE moodprint.outbox (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    kind VARCHAR(40) NOT NULL, 
    resource_id VARCHAR(64) NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    delivered BOOLEAN NOT NULL, 
    CONSTRAINT pk_outbox PRIMARY KEY (id), 
    CONSTRAINT fk_outbox_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_outbox_delivered ON moodprint.outbox (delivered);

CREATE INDEX ix_outbox_user_id ON moodprint.outbox (user_id);

CREATE TABLE moodprint.pairs (
    id UUID NOT NULL, 
    low_user_id UUID NOT NULL, 
    high_user_id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    cooldown_until TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_pairs PRIMARY KEY (id), 
    CONSTRAINT ck_pairs_canonical_pair CHECK (low_user_id < high_user_id), 
    CONSTRAINT fk_pairs_high_user_id_users FOREIGN KEY(high_user_id) REFERENCES moodprint.users (id), 
    CONSTRAINT fk_pairs_low_user_id_users FOREIGN KEY(low_user_id) REFERENCES moodprint.users (id), 
    CONSTRAINT uq_pairs_low_user_id UNIQUE (low_user_id, high_user_id)
);

CREATE INDEX ix_pairs_high_user_id ON moodprint.pairs (high_user_id);

CREATE INDEX ix_pairs_low_user_id ON moodprint.pairs (low_user_id);

CREATE TABLE moodprint.private_items (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    text TEXT NOT NULL, 
    origin VARCHAR(12) NOT NULL, 
    status VARCHAR(12) NOT NULL, 
    version INTEGER NOT NULL, 
    CONSTRAINT pk_private_items PRIMARY KEY (id), 
    CONSTRAINT ck_private_items_text_length CHECK (char_length(text)<=120), 
    CONSTRAINT fk_private_items_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_private_items_user_id ON moodprint.private_items (user_id);

CREATE TABLE moodprint.published_profiles (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    payload JSONB NOT NULL, 
    version INTEGER NOT NULL, 
    consent_version INTEGER NOT NULL, 
    valid BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_published_profiles PRIMARY KEY (id), 
    CONSTRAINT fk_published_profiles_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id), 
    CONSTRAINT uq_published_profiles_user_id UNIQUE (user_id, version)
);

CREATE INDEX ix_published_profiles_user_id ON moodprint.published_profiles (user_id);

CREATE UNIQUE INDEX uq_published_active_owner ON moodprint.published_profiles (user_id) WHERE valid;

CREATE TABLE moodprint.connection_requests (
    id UUID NOT NULL, 
    pair_id UUID NOT NULL, 
    sender_id UUID NOT NULL, 
    recipient_id UUID NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    version INTEGER NOT NULL, 
    snapshots JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    connection_id UUID, 
    CONSTRAINT pk_connection_requests PRIMARY KEY (id), 
    CONSTRAINT ck_connection_requests_request_status CHECK (status in ('pending','accepted','declined','cancelled','expired','invalidated')), 
    CONSTRAINT ck_connection_requests_request_distinct CHECK (sender_id <> recipient_id), 
    CONSTRAINT fk_connection_requests_pair_id_pairs FOREIGN KEY(pair_id) REFERENCES moodprint.pairs (id), 
    CONSTRAINT fk_connection_requests_recipient_id_users FOREIGN KEY(recipient_id) REFERENCES moodprint.users (id), 
    CONSTRAINT fk_connection_requests_sender_id_users FOREIGN KEY(sender_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_connection_requests_expires_at ON moodprint.connection_requests (expires_at);

CREATE INDEX ix_connection_requests_pair_id ON moodprint.connection_requests (pair_id);

CREATE INDEX ix_connection_requests_recipient_id ON moodprint.connection_requests (recipient_id);

CREATE INDEX ix_connection_requests_sender_id ON moodprint.connection_requests (sender_id);

CREATE UNIQUE INDEX uq_pending_pair ON moodprint.connection_requests (pair_id) WHERE status='pending';

CREATE TABLE moodprint.connections (
    id UUID NOT NULL, 
    pair_id UUID NOT NULL, 
    low_user_id UUID NOT NULL, 
    high_user_id UUID NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    version INTEGER NOT NULL, 
    snapshots JSONB NOT NULL, 
    next_seq BIGINT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_connections PRIMARY KEY (id), 
    CONSTRAINT ck_connections_connection_status CHECK (status in ('open','closed','blocked')), 
    CONSTRAINT ck_connections_connection_canonical CHECK (low_user_id < high_user_id), 
    CONSTRAINT fk_connections_high_user_id_users FOREIGN KEY(high_user_id) REFERENCES moodprint.users (id), 
    CONSTRAINT fk_connections_low_user_id_users FOREIGN KEY(low_user_id) REFERENCES moodprint.users (id), 
    CONSTRAINT fk_connections_pair_id_pairs FOREIGN KEY(pair_id) REFERENCES moodprint.pairs (id)
);

CREATE INDEX ix_connections_high_user_id ON moodprint.connections (high_user_id);

CREATE INDEX ix_connections_low_user_id ON moodprint.connections (low_user_id);

CREATE INDEX ix_connections_pair_id ON moodprint.connections (pair_id);

CREATE UNIQUE INDEX uq_open_pair ON moodprint.connections (pair_id) WHERE status='open';

CREATE TABLE moodprint.memories (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    bot_id VARCHAR(16) NOT NULL, 
    text VARCHAR(120) NOT NULL, 
    version INTEGER NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    proposal_id UUID NOT NULL, 
    source_id UUID, 
    source_version INTEGER, 
    CONSTRAINT pk_memories PRIMARY KEY (id), 
    CONSTRAINT fk_memories_source_id_private_items FOREIGN KEY(source_id) REFERENCES moodprint.private_items (id), 
    CONSTRAINT fk_memories_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id), 
    CONSTRAINT uq_memories_proposal_id UNIQUE (proposal_id)
);

CREATE INDEX ix_memories_scope ON moodprint.memories (user_id, bot_id, status);

CREATE INDEX ix_memories_source_id ON moodprint.memories (source_id);

CREATE TABLE moodprint.human_messages (
    id UUID NOT NULL, 
    connection_id UUID NOT NULL, 
    sender_id UUID NOT NULL, 
    client_message_id UUID NOT NULL, 
    seq BIGINT NOT NULL, 
    text VARCHAR(500) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_human_messages PRIMARY KEY (id), 
    CONSTRAINT ck_human_messages_message_length CHECK (char_length(text) between 1 and 500), 
    CONSTRAINT fk_human_messages_connection_id_connections FOREIGN KEY(connection_id) REFERENCES moodprint.connections (id), 
    CONSTRAINT fk_human_messages_sender_id_users FOREIGN KEY(sender_id) REFERENCES moodprint.users (id), 
    CONSTRAINT uq_human_messages_client_id UNIQUE (connection_id, sender_id, client_message_id), 
    CONSTRAINT uq_human_messages_sequence UNIQUE (connection_id, seq)
);

CREATE INDEX ix_human_messages_connection_id ON moodprint.human_messages (connection_id);

CREATE INDEX ix_human_messages_sender_id ON moodprint.human_messages (sender_id);

INSERT INTO moodprint.alembic_version (version_num) VALUES ('0001_foundation') RETURNING moodprint.alembic_version.version_num;

-- Running upgrade 0001_foundation -> 0002_safety

CREATE TABLE moodprint.identity_fields (
    user_id UUID NOT NULL, 
    field VARCHAR(16) NOT NULL, 
    value VARCHAR(40) NOT NULL, 
    version INTEGER NOT NULL, 
    CONSTRAINT pk_identity_fields PRIMARY KEY (user_id, field), 
    CONSTRAINT fk_identity_fields_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

CREATE TABLE moodprint.reports (
    id UUID NOT NULL, 
    reporter_id UUID NOT NULL, 
    subject_id UUID NOT NULL, 
    reason VARCHAR(120) NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    evidence JSONB NOT NULL, 
    CONSTRAINT pk_reports PRIMARY KEY (id), 
    CONSTRAINT fk_reports_reporter_id_users FOREIGN KEY(reporter_id) REFERENCES moodprint.users (id), 
    CONSTRAINT fk_reports_subject_id_users FOREIGN KEY(subject_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_reports_reporter_id ON moodprint.reports (reporter_id);

CREATE INDEX ix_reports_subject_id ON moodprint.reports (subject_id);

CREATE TABLE moodprint.reveal_access (
    id UUID NOT NULL, 
    connection_id UUID NOT NULL, 
    owner_id UUID NOT NULL, 
    recipient_id UUID NOT NULL, 
    field VARCHAR(16) NOT NULL, 
    identity_version INTEGER NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    version INTEGER NOT NULL, 
    preview_digest VARCHAR(64) NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    cooldown_until TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_reveal_access PRIMARY KEY (id), 
    CONSTRAINT fk_reveal_access_connection_id_connections FOREIGN KEY(connection_id) REFERENCES moodprint.connections (id), 
    CONSTRAINT fk_reveal_access_owner_id_users FOREIGN KEY(owner_id) REFERENCES moodprint.users (id), 
    CONSTRAINT fk_reveal_access_recipient_id_users FOREIGN KEY(recipient_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_reveal_access_connection_id ON moodprint.reveal_access (connection_id);

CREATE INDEX ix_reveal_access_owner_id ON moodprint.reveal_access (owner_id);

CREATE INDEX ix_reveal_access_recipient_id ON moodprint.reveal_access (recipient_id);

CREATE UNIQUE INDEX uq_active_reveal ON moodprint.reveal_access (connection_id, owner_id, recipient_id, field) WHERE status = 'granted';

UPDATE moodprint.alembic_version SET version_num='0002_safety' WHERE moodprint.alembic_version.version_num = '0001_foundation';

-- Running upgrade 0002_safety -> 0003_lifecycle

CREATE TABLE moodprint.data_jobs (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    kind VARCHAR(16) NOT NULL, 
    scope VARCHAR(32) NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    version INTEGER NOT NULL, 
    attempts INTEGER NOT NULL, 
    lease_token UUID, 
    lease_until TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_data_jobs PRIMARY KEY (id), 
    CONSTRAINT fk_data_jobs_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_data_jobs_status ON moodprint.data_jobs (status);

CREATE INDEX ix_data_jobs_user_id ON moodprint.data_jobs (user_id);

ALTER TABLE moodprint.auth_sessions ADD COLUMN reauthenticated_at TIMESTAMP WITH TIME ZONE DEFAULT '1970-01-01 00:00:00+00' NOT NULL;

ALTER TABLE moodprint.users ADD COLUMN deletion_pending BOOLEAN DEFAULT 'false' NOT NULL;

UPDATE moodprint.alembic_version SET version_num='0003_lifecycle' WHERE moodprint.alembic_version.version_num = '0002_safety';

-- Running upgrade 0003_lifecycle -> 0004_eligibility

CREATE TABLE moodprint.age_declarations (
    user_id UUID NOT NULL, 
    birth_year SMALLINT NOT NULL, 
    version INTEGER NOT NULL, 
    policy_version VARCHAR(32) NOT NULL, 
    declared_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    adult_confirmed_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_age_declarations PRIMARY KEY (user_id), 
    CONSTRAINT fk_age_declarations_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id), 
    CONSTRAINT ck_age_declarations_birth_year_range CHECK (birth_year between 1900 and 9999), 
    CONSTRAINT ck_age_declarations_age_declaration_version CHECK (version >= 1)
);

UPDATE moodprint.alembic_version SET version_num='0004_eligibility' WHERE moodprint.alembic_version.version_num = '0003_lifecycle';

-- Running upgrade 0004_eligibility -> 0005_export_scope

ALTER TABLE moodprint.data_jobs ALTER COLUMN scope TYPE VARCHAR(64);

UPDATE moodprint.alembic_version SET version_num='0005_export_scope' WHERE moodprint.alembic_version.version_num = '0004_eligibility';

COMMIT;

