BEGIN;

-- Running upgrade 0013_shared_activities -> 0014_moderation

CREATE TABLE moodprint.staff_roles (
    user_id UUID NOT NULL, 
    role VARCHAR(16) NOT NULL, 
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    granted_by VARCHAR(64) NOT NULL, 
    CONSTRAINT pk_staff_roles PRIMARY KEY (user_id), 
    CONSTRAINT ck_staff_roles_role CHECK (role IN ('moderator','admin')), 
    CONSTRAINT fk_staff_roles_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

ALTER TABLE moodprint.reports ADD COLUMN version INTEGER DEFAULT '1' NOT NULL;

ALTER TABLE moodprint.reports ADD COLUMN connection_id UUID;

ALTER TABLE moodprint.reports ADD CONSTRAINT fk_reports_connection_id_connections FOREIGN KEY(connection_id) REFERENCES moodprint.connections (id);

ALTER TABLE moodprint.reports ADD COLUMN reviewed_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE moodprint.reports ADD COLUMN resolution VARCHAR(16);

ALTER TABLE moodprint.reports ADD CONSTRAINT ck_reports_resolution CHECK (resolution IS NULL OR resolution IN ('dismissed','warned','restricted','suspended'));

CREATE INDEX ix_reports_status_created ON moodprint.reports (status, created_at);

CREATE TABLE moodprint.moderation_actions (
    id UUID NOT NULL, 
    report_id UUID, 
    subject_id UUID NOT NULL, 
    staff_id UUID NOT NULL, 
    action VARCHAR(16) NOT NULL, 
    until_at TIMESTAMP WITH TIME ZONE, 
    note VARCHAR(500) DEFAULT '' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_moderation_actions PRIMARY KEY (id), 
    CONSTRAINT ck_moderation_actions_action CHECK (action IN ('dismiss','warn','restrict','suspend','lift')), 
    CONSTRAINT fk_moderation_actions_report_id_reports FOREIGN KEY(report_id) REFERENCES moodprint.reports (id), 
    CONSTRAINT fk_moderation_actions_subject_id_users FOREIGN KEY(subject_id) REFERENCES moodprint.users (id), 
    CONSTRAINT fk_moderation_actions_staff_id_users FOREIGN KEY(staff_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_moderation_actions_subject ON moodprint.moderation_actions (subject_id, created_at);

ALTER TABLE moodprint.users ADD COLUMN social_restricted_until TIMESTAMP WITH TIME ZONE;

ALTER TABLE moodprint.users ADD COLUMN suspended_until TIMESTAMP WITH TIME ZONE;

ALTER TABLE moodprint.staff_roles ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.staff_roles FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.staff_roles FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.staff_roles TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.staff_roles FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.moderation_actions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.moderation_actions FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.moderation_actions FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.moderation_actions TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.moderation_actions FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0014_moderation' WHERE moodprint.alembic_version.version_num = '0013_shared_activities';

COMMIT;

