BEGIN;

-- Running upgrade 0012_matching_v2 -> 0013_shared_activities

ALTER TABLE moodprint.connections ADD COLUMN activity_seq BIGINT DEFAULT '0' NOT NULL;

CREATE TABLE moodprint.activity_sessions (
    id UUID NOT NULL, 
    connection_id UUID NOT NULL, 
    pair_id UUID NOT NULL, 
    kind VARCHAR(16) NOT NULL, 
    definition_version VARCHAR(24) NOT NULL, 
    inviter_id UUID NOT NULL, 
    invitee_id UUID NOT NULL, 
    state VARCHAR(12) NOT NULL, 
    end_reason VARCHAR(24), 
    round SMALLINT DEFAULT '0' NOT NULL, 
    phase VARCHAR(12) DEFAULT 'invited' NOT NULL, 
    content JSONB DEFAULT '{}'::jsonb NOT NULL, 
    timer JSONB, 
    score JSONB, 
    version INTEGER DEFAULT '1' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    ended_at TIMESTAMP WITH TIME ZONE, 
    deadline_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_activity_sessions PRIMARY KEY (id), 
    CONSTRAINT ck_activity_sessions_kind CHECK (kind IN ('icebreaker','coop_quiz','focus')), 
    CONSTRAINT ck_activity_sessions_state CHECK (state IN ('invited','active','paused','completed','ended','declined','cancelled','expired','aborted')), 
    CONSTRAINT ck_activity_sessions_distinct_participants CHECK (inviter_id <> invitee_id), 
    CONSTRAINT fk_activity_sessions_connection_id_connections FOREIGN KEY(connection_id) REFERENCES moodprint.connections (id), 
    CONSTRAINT fk_activity_sessions_pair_id_pairs FOREIGN KEY(pair_id) REFERENCES moodprint.pairs (id), 
    CONSTRAINT fk_activity_sessions_inviter_id_users FOREIGN KEY(inviter_id) REFERENCES moodprint.users (id), 
    CONSTRAINT fk_activity_sessions_invitee_id_users FOREIGN KEY(invitee_id) REFERENCES moodprint.users (id)
);

CREATE UNIQUE INDEX uq_activity_open_per_connection ON moodprint.activity_sessions (connection_id) WHERE state IN ('invited','active','paused');

CREATE INDEX ix_activity_sessions_deadline ON moodprint.activity_sessions (deadline_at) WHERE state IN ('invited','active','paused');

CREATE INDEX ix_activity_sessions_connection_created ON moodprint.activity_sessions (connection_id, created_at DESC);

CREATE INDEX ix_activity_sessions_inviter_created ON moodprint.activity_sessions (inviter_id, created_at);

CREATE TABLE moodprint.activity_participants (
    session_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    role VARCHAR(8) NOT NULL, 
    accepted_at TIMESTAMP WITH TIME ZONE, 
    ready_round SMALLINT DEFAULT '0' NOT NULL, 
    feedback VARCHAR(12), 
    feedback_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_activity_participants PRIMARY KEY (session_id, user_id), 
    CONSTRAINT ck_activity_participants_role CHECK (role IN ('inviter','invitee')), 
    CONSTRAINT ck_activity_participants_feedback CHECK (feedback IS NULL OR feedback IN ('liked','neutral','not_for_me')), 
    CONSTRAINT fk_activity_participants_session_id_activity_sessions FOREIGN KEY(session_id) REFERENCES moodprint.activity_sessions (id) ON DELETE CASCADE, 
    CONSTRAINT fk_activity_participants_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_activity_participants_user_id ON moodprint.activity_participants (user_id);

CREATE TABLE moodprint.activity_responses (
    session_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    round SMALLINT NOT NULL, 
    item_id VARCHAR(32) NOT NULL, 
    choice SMALLINT, 
    text VARCHAR(140), 
    skipped BOOLEAN DEFAULT 'false' NOT NULL, 
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_activity_responses PRIMARY KEY (session_id, user_id, round), 
    CONSTRAINT ck_activity_responses_round CHECK (round BETWEEN 1 AND 10), 
    CONSTRAINT ck_activity_responses_answer CHECK (skipped OR choice IS NOT NULL OR text IS NOT NULL), 
    CONSTRAINT fk_activity_responses_session_id_activity_sessions FOREIGN KEY(session_id) REFERENCES moodprint.activity_sessions (id) ON DELETE CASCADE, 
    CONSTRAINT fk_activity_responses_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_activity_responses_user_id ON moodprint.activity_responses (user_id);

ALTER TABLE moodprint.activity_sessions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.activity_sessions FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.activity_sessions FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.activity_sessions TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.activity_sessions FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.activity_participants ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.activity_participants FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.activity_participants FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.activity_participants TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.activity_participants FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.activity_responses ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.activity_responses FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.activity_responses FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.activity_responses TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.activity_responses FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0013_shared_activities' WHERE moodprint.alembic_version.version_num = '0012_matching_v2';

COMMIT;

