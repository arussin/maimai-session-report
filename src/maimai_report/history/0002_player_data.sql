CREATE TABLE IF NOT EXISTS player_revisions (
  scope TEXT NOT NULL, revision TEXT NOT NULL CHECK(length(revision)=64),
  metadata TEXT NOT NULL, PRIMARY KEY(scope,revision)
);
CREATE TABLE IF NOT EXISTS player_state (
  scope TEXT PRIMARY KEY, revision TEXT,
  FOREIGN KEY(scope,revision) REFERENCES player_revisions(scope,revision)
);
INSERT OR IGNORE INTO history_migrations(version) VALUES(2);
