-- Forward-only baseline schema. Domain migrations add constraints before app rollout.
CREATE TABLE IF NOT EXISTS schema_version (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO schema_version(version) VALUES ('0001_initial') ON CONFLICT DO NOTHING;
