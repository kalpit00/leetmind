-- Leetmind local cache schema. Plain SQLite, no ORM.
-- Topics are stored as a JSON array string on the problem row for simplicity;
-- list membership and submissions are normalized into their own tables.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS problems (
    slug         TEXT PRIMARY KEY,
    frontend_id  TEXT,
    title        TEXT NOT NULL,
    difficulty   TEXT,
    paid_only    INTEGER DEFAULT 0,
    status       TEXT,              -- "ac", "notac", or NULL
    topics_json  TEXT DEFAULT '[]', -- JSON array of {"name","slug"}
    updated_at   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_problems_frontend_id ON problems(frontend_id);
CREATE INDEX IF NOT EXISTS idx_problems_status ON problems(status);

CREATE TABLE IF NOT EXISTS lists (
    slug        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    is_public   INTEGER DEFAULT 0,
    updated_at  INTEGER
);

CREATE TABLE IF NOT EXISTS list_problems (
    list_slug     TEXT NOT NULL,
    problem_slug  TEXT NOT NULL,
    PRIMARY KEY (list_slug, problem_slug)
);

CREATE INDEX IF NOT EXISTS idx_list_problems_problem ON list_problems(problem_slug);

CREATE TABLE IF NOT EXISTS submissions (
    id             TEXT PRIMARY KEY,
    problem_slug   TEXT NOT NULL,
    problem_title  TEXT,
    status_display TEXT,
    lang           TEXT,
    timestamp      INTEGER,
    runtime        TEXT,
    memory         TEXT,
    has_notes      INTEGER DEFAULT 0,
    notes          TEXT,
    code           TEXT,           -- populated lazily by submission-detail sync
    updated_at     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_submissions_problem ON submissions(problem_slug);

-- Bookkeeping for incremental sync.
CREATE TABLE IF NOT EXISTS sync_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_at  INTEGER
);

-- Full-text search over a denormalized per-problem document. Populated by
-- search.keyword_search.rebuild_index(). 'unindexed' columns are stored for
-- retrieval/scoring but not tokenized.
CREATE VIRTUAL TABLE IF NOT EXISTS search_docs USING fts5(
    slug UNINDEXED,
    frontend_id,
    title,
    difficulty,
    topics,
    lists,
    status UNINDEXED,
    languages,
    notes,
    code,
    tokenize = 'porter unicode61'
);
