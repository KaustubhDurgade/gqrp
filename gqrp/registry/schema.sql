-- Trial registry schema — append-only, immutability enforced at the DB layer.
-- Spec §6 (the statistical spine) + §A (data model); decision D4 / D7.
--
-- Every mutable operation on a history table is rejected by a BEFORE UPDATE /
-- BEFORE DELETE trigger that RAISE(ABORT)s. This is belt-and-suspenders alongside
-- the writer having no mutate path and the client opening the file read-only.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── trial (config, logged BEFORE results) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS trial (
    trial_id        TEXT PRIMARY KEY,
    family_id       TEXT NOT NULL,
    parent_trial_id TEXT REFERENCES trial(trial_id),
    level           TEXT NOT NULL CHECK (level IN ('family', 'variant', 'hyperparam')),
    weight          REAL NOT NULL,
    run_type        TEXT NOT NULL CHECK (run_type IN ('research', 'pipeline-validation')),
    config_json     TEXT NOT NULL,
    config_hash     TEXT NOT NULL,
    data_window     TEXT NOT NULL CHECK (data_window IN ('development', 'validation', 'holdout')),
    created_at      TEXT NOT NULL,
    status          TEXT NOT NULL,
    -- Fixed weight table (spec §6), enforced structurally so weight can never
    -- diverge from level: family=1.0, variant=0.5, hyperparam=0.2.
    CHECK (
        (level = 'family'     AND weight = 1.0) OR
        (level = 'variant'    AND weight = 0.5) OR
        (level = 'hyperparam' AND weight = 0.2)
    )
);

-- ── trial_result (written AFTER trial; PK enforces one result per trial) ─────
-- The FK to trial makes "config before results" structural: a result cannot be
-- inserted before its trial exists.
CREATE TABLE IF NOT EXISTS trial_result (
    trial_id           TEXT PRIMARY KEY REFERENCES trial(trial_id),
    metrics_json       TEXT NOT NULL,
    gate_verdicts_json TEXT NOT NULL,
    created_at         TEXT NOT NULL
);

-- ── research_memo (hash-locked before implementation; spec §4) ──────────────
CREATE TABLE IF NOT EXISTS research_memo (
    memo_hash    TEXT PRIMARY KEY,
    family_id    TEXT NOT NULL,
    memo_json    TEXT NOT NULL,
    committed_at TEXT NOT NULL
);

-- ── negative_knowledge (quarantine record; spec §11) ────────────────────────
CREATE TABLE IF NOT EXISTS negative_knowledge (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id                  TEXT NOT NULL,
    reason_rejected            TEXT NOT NULL,
    reason_for_reopening       TEXT,
    material_hypothesis_change TEXT,
    why_not_parameter_tuning   TEXT,
    created_at                 TEXT NOT NULL
);

-- ── Immutability triggers — reject every UPDATE / DELETE ────────────────────
CREATE TRIGGER IF NOT EXISTS trial_no_update BEFORE UPDATE ON trial
BEGIN SELECT RAISE(ABORT, 'trial is append-only: UPDATE forbidden (D4)'); END;
CREATE TRIGGER IF NOT EXISTS trial_no_delete BEFORE DELETE ON trial
BEGIN SELECT RAISE(ABORT, 'trial is append-only: DELETE forbidden (D4)'); END;

CREATE TRIGGER IF NOT EXISTS trial_result_no_update BEFORE UPDATE ON trial_result
BEGIN SELECT RAISE(ABORT, 'trial_result is append-only: UPDATE forbidden (D4)'); END;
CREATE TRIGGER IF NOT EXISTS trial_result_no_delete BEFORE DELETE ON trial_result
BEGIN SELECT RAISE(ABORT, 'trial_result is append-only: DELETE forbidden (D4)'); END;

CREATE TRIGGER IF NOT EXISTS research_memo_no_update BEFORE UPDATE ON research_memo
BEGIN SELECT RAISE(ABORT, 'research_memo is append-only: UPDATE forbidden (D4)'); END;
CREATE TRIGGER IF NOT EXISTS research_memo_no_delete BEFORE DELETE ON research_memo
BEGIN SELECT RAISE(ABORT, 'research_memo is append-only: DELETE forbidden (D4)'); END;

CREATE TRIGGER IF NOT EXISTS negative_knowledge_no_update BEFORE UPDATE ON negative_knowledge
BEGIN SELECT RAISE(ABORT, 'negative_knowledge is append-only: UPDATE forbidden (D4)'); END;
CREATE TRIGGER IF NOT EXISTS negative_knowledge_no_delete BEFORE DELETE ON negative_knowledge
BEGIN SELECT RAISE(ABORT, 'negative_knowledge is append-only: DELETE forbidden (D4)'); END;
