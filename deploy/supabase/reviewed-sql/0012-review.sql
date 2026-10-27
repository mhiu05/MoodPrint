BEGIN;

-- Running upgrade 0011_social_stabilization -> 0012_matching_v2

ALTER TABLE moodprint.published_profiles ADD COLUMN taxonomy_version VARCHAR(8) DEFAULT 'v1' NOT NULL;

ALTER TABLE moodprint.candidate_references ADD COLUMN scoring_version VARCHAR(16) DEFAULT 'rules-v1' NOT NULL;

ALTER TABLE moodprint.candidate_references ADD COLUMN rank SMALLINT;

CREATE TABLE moodprint.matching_stats_daily (
    day DATE NOT NULL, 
    scoring_version VARCHAR(16) NOT NULL, 
    impressions INTEGER DEFAULT '0' NOT NULL, 
    requests INTEGER DEFAULT '0' NOT NULL, 
    accepts INTEGER DEFAULT '0' NOT NULL, 
    CONSTRAINT pk_matching_stats_daily PRIMARY KEY (day, scoring_version)
);

ALTER TABLE moodprint.matching_stats_daily ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.matching_stats_daily FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.matching_stats_daily FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.matching_stats_daily TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.matching_stats_daily FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0012_matching_v2' WHERE moodprint.alembic_version.version_num = '0011_social_stabilization';

COMMIT;

