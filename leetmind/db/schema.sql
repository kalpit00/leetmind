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

-- ===========================================================================
-- Knowledge Base (feature/knowledge-base)
-- ===========================================================================

-- Structured analysis of one accepted submission, produced offline by an LLM
-- (kb.analyzer). One row per problem_slug (the analyzed representative
-- submission). code_hash + analysis_version drive incremental re-analysis:
-- unchanged code at the current version is skipped.
CREATE TABLE IF NOT EXISTS solution_analyses (
    problem_slug      TEXT PRIMARY KEY,
    submission_id     TEXT,
    problem_title     TEXT,
    language          TEXT,
    pattern_name      TEXT,           -- e.g. "Monotonic Increasing Stack"
    core_idea         TEXT,           -- 1-3 sentence description of the approach
    invariant         TEXT,           -- the key loop/structure invariant
    complexity        TEXT,           -- e.g. "O(n) time, O(n) space"
    pitfalls_json     TEXT DEFAULT '[]',   -- JSON array of strings
    template_code     TEXT,           -- generalized reusable skeleton
    style_notes_json  TEXT DEFAULT '[]',   -- JSON array of observed style traits
    techniques_json   TEXT DEFAULT '[]',   -- JSON array of technique labels
    code_hash         TEXT,           -- hash of analyzed code (incremental guard)
    analysis_version  INTEGER DEFAULT 1,
    analyzed_at       INTEGER
);

CREATE INDEX IF NOT EXISTS idx_analyses_pattern ON solution_analyses(pattern_name);

-- Directed relationships between a target problem and a problem the user has
-- already solved. Produced by kb.bridge and cached here.
CREATE TABLE IF NOT EXISTS problem_bridges (
    source_problem_slug   TEXT NOT NULL,   -- the already-solved anchor
    target_problem_slug   TEXT NOT NULL,   -- the new problem being asked about
    relationship          TEXT,            -- how target reduces to / relates to source
    shared_patterns_json  TEXT DEFAULT '[]',
    transfer_steps_json   TEXT DEFAULT '[]',
    confidence            REAL DEFAULT 0.0,
    created_at            INTEGER,
    PRIMARY KEY (target_problem_slug, source_problem_slug)
);

CREATE INDEX IF NOT EXISTS idx_bridges_target ON problem_bridges(target_problem_slug);

-- FTS over the analyses so patterns/templates/style are keyword-searchable.
-- Rebuilt by kb.pattern_search.rebuild_pattern_index().
CREATE VIRTUAL TABLE IF NOT EXISTS pattern_docs USING fts5(
    problem_slug UNINDEXED,
    title,
    pattern_name,
    core_idea,
    invariant,
    techniques,
    pitfalls,
    style_notes,
    template_code,
    tokenize = 'porter unicode61'
);

-- Local semantic index over solution_analyses. We intentionally store vectors
-- as JSON for now instead of adding a vector DB: with a few thousand analyzed
-- submissions, Python cosine similarity over SQLite rows is simple and fast
-- enough for local use.
CREATE TABLE IF NOT EXISTS solution_embeddings (
    problem_slug     TEXT PRIMARY KEY,
    embedding_model  TEXT NOT NULL,
    embedding_json   TEXT NOT NULL,
    content_hash     TEXT NOT NULL,
    embedded_at      INTEGER
);

CREATE INDEX IF NOT EXISTS idx_solution_embeddings_model
    ON solution_embeddings(embedding_model);
