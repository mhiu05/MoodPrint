BEGIN;

-- Running upgrade 0010_account_deletion -> 0011_social_stabilization

ALTER TABLE moodprint.users ADD COLUMN last_seen_at TIMESTAMP WITH TIME ZONE;

CREATE TABLE moodprint.connection_reads (
    connection_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    last_read_seq BIGINT DEFAULT '0' NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_connection_reads PRIMARY KEY (connection_id, user_id), 
    CONSTRAINT ck_connection_reads_read_seq CHECK (last_read_seq >= 0), 
    CONSTRAINT fk_connection_reads_connection_id_connections FOREIGN KEY(connection_id) REFERENCES moodprint.connections (id), 
    CONSTRAINT fk_connection_reads_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_connection_reads_user_id ON moodprint.connection_reads (user_id);

CREATE INDEX ix_blocks_blocked_id ON moodprint.blocks (blocked_id);

CREATE INDEX ix_candidate_references_peer_id ON moodprint.candidate_references (peer_id);

CREATE INDEX ix_connection_requests_recipient_status ON moodprint.connection_requests (recipient_id, status);

ALTER TABLE moodprint.connection_reads ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.connection_reads FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.connection_reads FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.connection_reads TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.connection_reads FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0011_social_stabilization' WHERE moodprint.alembic_version.version_num = '0010_account_deletion';

COMMIT;

