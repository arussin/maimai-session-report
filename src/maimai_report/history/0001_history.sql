CREATE TABLE IF NOT EXISTS history_migrations (version INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS captures (
  id TEXT PRIMARY KEY CHECK(length(id)=64), scope TEXT NOT NULL,
  input_hash TEXT NOT NULL, manifest_key TEXT NOT NULL, manifest_hash TEXT NOT NULL,
  captured_ms INTEGER NOT NULL, sort_ms INTEGER NOT NULL, start_ms INTEGER, end_ms INTEGER,
  timezone TEXT NOT NULL, versions TEXT NOT NULL, meaningful INTEGER NOT NULL,
  promote INTEGER NOT NULL DEFAULT 0, score_count INTEGER NOT NULL, pb_count INTEGER NOT NULL,
  source_id TEXT NOT NULL, renderer_commit TEXT NOT NULL, missing TEXT NOT NULL,
  report_key TEXT, report_hash TEXT, b50_key TEXT, b50_hash TEXT, b50_provenance TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'staged' CHECK(state IN ('staged','ready'))
);
CREATE INDEX IF NOT EXISTS capture_history ON captures(scope,state,meaningful,sort_ms DESC,id DESC);
CREATE TABLE IF NOT EXISTS rating_snapshots (
  capture_id TEXT NOT NULL REFERENCES captures(id), phase TEXT NOT NULL CHECK(phase IN ('before','after')),
  reconstructed INTEGER, naive INTEGER, old_rating INTEGER, new_rating INTEGER,
  old_floor INTEGER, new_floor INTEGER, old_count INTEGER, new_count INTEGER, pb_count INTEGER,
  new_pool_played INTEGER, PRIMARY KEY(capture_id,phase)
);
CREATE TABLE IF NOT EXISTS archive_state (
  scope TEXT PRIMARY KEY, latest_id TEXT REFERENCES captures(id), schema_version INTEGER NOT NULL DEFAULT 1
);
CREATE TRIGGER IF NOT EXISTS capture_complete_before_ready
BEFORE UPDATE OF state ON captures WHEN NEW.state='ready'
BEGIN
  SELECT RAISE(ABORT,'Both rating snapshots are required')
  WHERE (SELECT COUNT(*) FROM rating_snapshots WHERE capture_id=NEW.id)<>2;
END;
CREATE TRIGGER IF NOT EXISTS capture_latest_after_ready
AFTER UPDATE OF state ON captures WHEN NEW.state='ready' AND NEW.meaningful=1 AND NEW.promote=1 AND NEW.report_key IS NOT NULL
BEGIN
  INSERT INTO archive_state(scope,latest_id,schema_version) VALUES(NEW.scope,NEW.id,1)
  ON CONFLICT(scope) DO UPDATE SET latest_id=NEW.id
  WHERE archive_state.latest_id IS NULL OR EXISTS(
    SELECT 1 FROM captures previous WHERE previous.id=archive_state.latest_id
    AND (NEW.sort_ms>previous.sort_ms OR (NEW.sort_ms=previous.sort_ms AND NEW.id>previous.id))
  );
END;
CREATE TRIGGER IF NOT EXISTS ready_capture_immutable
BEFORE UPDATE ON captures WHEN OLD.state='ready'
BEGIN
  SELECT RAISE(ABORT,'Ready captures are immutable');
END;
CREATE TRIGGER IF NOT EXISTS ready_rating_immutable
BEFORE UPDATE ON rating_snapshots
WHEN EXISTS(SELECT 1 FROM captures WHERE id=OLD.capture_id AND state='ready')
BEGIN
  SELECT RAISE(ABORT,'Ready rating snapshots are immutable');
END;
INSERT OR IGNORE INTO history_migrations(version) VALUES(1);
