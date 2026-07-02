"""
Data layer for the UCAT Prep app.

Dual backend, mirroring the rest of this repo: when DATABASE_URL is set (Neon /
any cloud PostgreSQL) and psycopg2 is available it talks to Postgres; otherwise
it falls back to a local SQLite file so the app runs with zero configuration.
"""

import os
import re
import json
import hashlib
import secrets
from datetime import datetime, date, timedelta
from pathlib import Path

# ── Backend detection (lazy so env var can be injected before first use) ───────
try:
    import psycopg2
    import psycopg2.extras
    _HAS_PG = True
except ImportError:
    _HAS_PG = False

import sqlite3
DB_PATH = Path(__file__).parent / "ucat.db"

_USE_PG: bool | None = None
_DB_URL: str = ""
_BOOTSTRAPPED: bool = False
_CONN = None  # cached Postgres connection, reused for the life of the process


def _setup() -> bool:
    global _USE_PG, _DB_URL
    if _USE_PG is None:
        _DB_URL = os.environ.get("DATABASE_URL", "")
        _USE_PG = bool(_DB_URL and _HAS_PG)
    return _USE_PG


def _ph() -> str:
    return "%s" if _setup() else "?"


def _connect_pg():
    # Neon (and most cloud PostgreSQL) requires SSL — add sslmode=require if absent
    url = _DB_URL
    if "sslmode" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    # Single long-lived connection: autocommit avoids a failed statement leaving
    # the connection in an aborted-transaction state that poisons later queries.
    conn.autocommit = True
    return conn


def get_conn():
    """Return a database connection.

    For Postgres/Neon the connection is cached and reused for the life of the
    process — opening a fresh SSL connection on every query was the main source
    of per-interaction latency. A closed/dropped connection is reopened on the
    next call. SQLite is a local file and cheap to open, so it stays per-call.
    """
    global _CONN
    if _setup():
        if _CONN is None or getattr(_CONN, "closed", 1):
            _CONN = _connect_pg()
        return _CONN
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _drop_conn():
    """Discard the cached Postgres connection so the next call reconnects."""
    global _CONN
    if _CONN is not None:
        try:
            _CONN.close()
        except Exception:
            pass
        _CONN = None


def _pg_call(run):
    """Run ``run(conn)`` on the cached Postgres connection, reconnecting and
    retrying once if it has been dropped (e.g. a Neon idle timeout)."""
    try:
        return run(get_conn())
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        _drop_conn()
        return run(get_conn())


def _n(sql: str) -> str:
    """Convert :name placeholders → %(name)s for psycopg2."""
    if _setup():
        return re.sub(r":(\w+)", r"%(\1)s", sql)
    return sql


def _q(conn, sql: str, params=()):
    """Execute and return all rows as dicts."""
    if _setup():
        def run(c):
            with c.cursor() as cur:
                cur.execute(sql, params or None)
                return [dict(r) for r in cur.fetchall()]
        return _pg_call(run)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _q1(conn, sql: str, params=()):
    """Execute and return first row as dict, or None."""
    if _setup():
        def run(c):
            with c.cursor() as cur:
                cur.execute(sql, params or None)
                row = cur.fetchone()
                return dict(row) if row else None
        return _pg_call(run)
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _run(conn, sql: str, params=()):
    """Execute DML; returns lastrowid for INSERT statements."""
    if _setup():
        is_insert = sql.strip().upper().startswith("INSERT") and "RETURNING" not in sql.upper()
        exec_sql = (sql.rstrip(";") + " RETURNING id") if is_insert else sql
        def run(c):
            with c.cursor() as cur:
                cur.execute(exec_sql, params or None)
                if is_insert:
                    row = cur.fetchone()
                    return row["id"] if row else None
            return None
        return _pg_call(run)
    cur = conn.execute(sql, params)
    return cur.lastrowid


def _commit(conn):
    # Postgres runs in autocommit mode (see _connect_pg); commit() is a harmless
    # no-op there. SQLite still needs an explicit commit.
    if not _setup():
        conn.commit()


def _close(conn):
    # The Postgres connection is cached and reused, so closing it here would
    # defeat the purpose. SQLite connections are per-call and must be closed.
    if not _setup():
        conn.close()


# ── Schema ─────────────────────────────────────────────────────────────────────

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    created_at    TEXT
);
CREATE TABLE IF NOT EXISTS subjects (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    code      TEXT NOT NULL UNIQUE,
    name      TEXT NOT NULL,
    color     TEXT DEFAULT '#1f77b4',
    sort_order INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS topics (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    high_yield INTEGER DEFAULT 0,
    summary    TEXT,
    content    TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS passages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    topic_id    INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    created_at  TEXT
);
CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    topic_id    INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    passage_id  INTEGER REFERENCES passages(id) ON DELETE CASCADE,
    stem        TEXT NOT NULL,
    option_a    TEXT NOT NULL,
    option_b    TEXT NOT NULL,
    option_c    TEXT NOT NULL,
    option_d    TEXT NOT NULL,
    option_e    TEXT,
    correct     TEXT NOT NULL,
    explanation TEXT,
    difficulty  TEXT DEFAULT 'Medium' CHECK(difficulty IN ('Easy','Medium','Hard')),
    question_format TEXT DEFAULT 'single' CHECK(question_format IN ('single','multi')),
    active      INTEGER DEFAULT 1,
    created_at  TEXT
);
CREATE TABLE IF NOT EXISTS attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    chosen      TEXT NOT NULL,
    is_correct  INTEGER NOT NULL,
    seconds     REAL DEFAULT 0,
    created_at  TEXT
);
CREATE TABLE IF NOT EXISTS mock_results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    correct    INTEGER NOT NULL,
    total      INTEGER NOT NULL,
    cog_total  INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS flashcards (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id    INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    topic_id      INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    front         TEXT NOT NULL,
    back          TEXT NOT NULL,
    ease          REAL DEFAULT 2.5,
    interval_days INTEGER DEFAULT 0,
    reps          INTEGER DEFAULT 0,
    due_date      TEXT,
    last_reviewed TEXT,
    created_at    TEXT
);
CREATE TABLE IF NOT EXISTS flashcard_progress (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    flashcard_id  INTEGER NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
    ease          REAL DEFAULT 2.5,
    interval_days INTEGER DEFAULT 0,
    reps          INTEGER DEFAULT 0,
    due_date      TEXT,
    last_reviewed TEXT,
    UNIQUE(user_id, flashcard_id)
);
CREATE TABLE IF NOT EXISTS study_tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    subject_id   INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
    task_type    TEXT DEFAULT 'Review',
    due_date     TEXT,
    duration_min INTEGER DEFAULT 60,
    status       TEXT DEFAULT 'Todo' CHECK(status IN ('Todo','In Progress','Done')),
    notes        TEXT,
    created_at   TEXT
);
CREATE TABLE IF NOT EXISTS chat_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content    TEXT NOT NULL,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS app_context (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS user_context (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TEXT,
    PRIMARY KEY (user_id, key)
);
"""

_PG_TABLES = [
    """CREATE TABLE IF NOT EXISTS users (
        id            SERIAL PRIMARY KEY,
        username      TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        salt          TEXT NOT NULL,
        created_at    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS subjects (
        id         SERIAL PRIMARY KEY,
        code       TEXT NOT NULL UNIQUE,
        name       TEXT NOT NULL,
        color      TEXT DEFAULT '#1f77b4',
        sort_order INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS topics (
        id         SERIAL PRIMARY KEY,
        subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        name       TEXT NOT NULL,
        high_yield INTEGER DEFAULT 0,
        summary    TEXT,
        content    TEXT,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS passages (
        id          SERIAL PRIMARY KEY,
        subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        topic_id    INTEGER REFERENCES topics(id) ON DELETE SET NULL,
        title       TEXT NOT NULL,
        body        TEXT NOT NULL,
        created_at  TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS questions (
        id          SERIAL PRIMARY KEY,
        subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        topic_id    INTEGER REFERENCES topics(id) ON DELETE SET NULL,
        passage_id  INTEGER REFERENCES passages(id) ON DELETE CASCADE,
        stem        TEXT NOT NULL,
        option_a    TEXT NOT NULL,
        option_b    TEXT NOT NULL,
        option_c    TEXT NOT NULL,
        option_d    TEXT NOT NULL,
        option_e    TEXT,
        correct     TEXT NOT NULL,
        explanation TEXT,
        difficulty  TEXT DEFAULT 'Medium' CHECK(difficulty IN ('Easy','Medium','Hard')),
        question_format TEXT DEFAULT 'single' CHECK(question_format IN ('single','multi')),
        active      INTEGER DEFAULT 1,
        created_at  TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS attempts (
        id          SERIAL PRIMARY KEY,
        user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
        question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
        subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        chosen      TEXT NOT NULL,
        is_correct  INTEGER NOT NULL,
        seconds     DOUBLE PRECISION DEFAULT 0,
        created_at  TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS mock_results (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
        correct    INTEGER NOT NULL,
        total      INTEGER NOT NULL,
        cog_total  INTEGER,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS flashcards (
        id            SERIAL PRIMARY KEY,
        subject_id    INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        topic_id      INTEGER REFERENCES topics(id) ON DELETE SET NULL,
        front         TEXT NOT NULL,
        back          TEXT NOT NULL,
        ease          DOUBLE PRECISION DEFAULT 2.5,
        interval_days INTEGER DEFAULT 0,
        reps          INTEGER DEFAULT 0,
        due_date      TEXT,
        last_reviewed TEXT,
        created_at    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS flashcard_progress (
        id            SERIAL PRIMARY KEY,
        user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        flashcard_id  INTEGER NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
        ease          DOUBLE PRECISION DEFAULT 2.5,
        interval_days INTEGER DEFAULT 0,
        reps          INTEGER DEFAULT 0,
        due_date      TEXT,
        last_reviewed TEXT,
        UNIQUE(user_id, flashcard_id)
    )""",
    """CREATE TABLE IF NOT EXISTS study_tasks (
        id           SERIAL PRIMARY KEY,
        user_id      INTEGER REFERENCES users(id) ON DELETE CASCADE,
        title        TEXT NOT NULL,
        subject_id   INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
        task_type    TEXT DEFAULT 'Review',
        due_date     TEXT,
        duration_min INTEGER DEFAULT 60,
        status       TEXT DEFAULT 'Todo' CHECK(status IN ('Todo','In Progress','Done')),
        notes        TEXT,
        created_at   TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS chat_history (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
        role       TEXT NOT NULL CHECK(role IN ('user','assistant')),
        content    TEXT NOT NULL,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS app_context (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS user_context (
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        key        TEXT NOT NULL,
        value      TEXT NOT NULL,
        updated_at TEXT,
        PRIMARY KEY (user_id, key)
    )""",
]


def _column_exists(conn, table, column):
    if _setup():
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
                (table, column))
            return cur.fetchone() is not None
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def _migrate_user_ids(conn):
    """Add a user_id column to tables that predate multi-user accounts, so
    older deployments (e.g. an existing Neon database) pick up per-user data
    isolation without losing any existing rows. Pre-existing rows are left
    with user_id = NULL and simply won't show up for any account — they were
    recorded before accounts existed, so there's no user to attribute them to."""
    for table in ("attempts", "study_tasks", "chat_history"):
        if _column_exists(conn, table, "user_id"):
            continue
        if _setup():
            with conn.cursor() as cur:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
        else:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id)")
    _commit(conn)


def _migrate_passage_id(conn):
    """Add questions.passage_id to databases created before passage-based
    content (a long shared passage → a series of linked questions, as in real
    UCAT VR) existed, so existing deployments gain the column without losing
    rows. The passages table itself is created by the schema's CREATE TABLE IF
    NOT EXISTS, so only the new column on the pre-existing questions table needs
    an explicit ALTER here."""
    if _column_exists(conn, "questions", "passage_id"):
        return
    if _setup():
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE questions ADD COLUMN passage_id INTEGER "
                        "REFERENCES passages(id) ON DELETE CASCADE")
    else:
        conn.execute("ALTER TABLE questions ADD COLUMN passage_id INTEGER REFERENCES passages(id)")
    _commit(conn)


def _migrate_question_options(conn):
    """Bring the questions table up to the format the real UCAT needs: a fifth
    option (option_e) for Quantitative Reasoning's five-choice items, and an
    `active` flag so legacy questions can be retired without deleting user
    attempt history. Each step is guarded so it is safe to re-run and safe on
    databases that predate it. The `correct` column's CHECK constraint is
    handled by _migrate_question_format, which runs after this and drops it
    permanently — Decision Making's real 'Yes/No statements' format needs
    `correct` to hold more than one letter (e.g. 'B,E'), so re-adding a
    single-letter CHECK here would break on any database that already has
    multi-format rows."""
    # option_e (nullable — most subtests use fewer than five options)
    if not _column_exists(conn, "questions", "option_e"):
        if _setup():
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE questions ADD COLUMN option_e TEXT")
        else:
            conn.execute("ALTER TABLE questions ADD COLUMN option_e TEXT")
    # active flag (default on)
    if not _column_exists(conn, "questions", "active"):
        if _setup():
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE questions ADD COLUMN active INTEGER DEFAULT 1")
        else:
            conn.execute("ALTER TABLE questions ADD COLUMN active INTEGER DEFAULT 1")
    _commit(conn)


def _migrate_question_format(conn):
    """Add question_format ('single' vs 'multi') and drop the single-letter CHECK
    on `correct`, so Decision Making's real 'Yes/No statements' format — where a
    question can have more than one correct letter, stored as a sorted
    comma-separated string like 'B,E' — is representable. Guarded to be safe to
    re-run and safe on databases that predate it."""
    if not _column_exists(conn, "questions", "question_format"):
        if _setup():
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE questions ADD COLUMN question_format TEXT DEFAULT 'single'")
        else:
            conn.execute("ALTER TABLE questions ADD COLUMN question_format TEXT DEFAULT 'single'")
    if _setup():
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE questions DROP CONSTRAINT IF EXISTS questions_correct_check")
    _commit(conn)


def init_db():
    """Create tables, migrate older schemas, seed starter content on first
    run, and backfill any newer seed content into an already-populated
    database. The work runs once per process — Streamlit reruns this script
    on every interaction, so the guard keeps each rerun cheap."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    conn = get_conn()
    try:
        if _setup():
            with conn.cursor() as cur:
                for stmt in _PG_TABLES:
                    cur.execute(stmt)
        else:
            conn.executescript(_SQLITE_SCHEMA)
        _commit(conn)
        _migrate_user_ids(conn)
        _migrate_passage_id(conn)
        _migrate_question_options(conn)
        _migrate_question_format(conn)
    finally:
        _close(conn)
    seed_content()
    backfill_content()
    _BOOTSTRAPPED = True


# ── Subjects ───────────────────────────────────────────────────────────────────

def get_subjects():
    conn = get_conn()
    try:
        return _q(conn, "SELECT * FROM subjects ORDER BY sort_order, name")
    finally:
        _close(conn)


def get_subject_map():
    """Return {id: row} and {code: row} for quick lookups."""
    subs = get_subjects()
    return {s["id"]: s for s in subs}, {s["code"]: s for s in subs}


# ── Users / accounts ─────────────────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def create_user(username: str, password: str):
    """Create a new account. Returns the new user id, or None if the username is taken."""
    username = username.strip()
    ph = _ph()
    conn = get_conn()
    try:
        if _q1(conn, f"SELECT id FROM users WHERE username = {ph}", (username,)):
            return None
        salt = secrets.token_hex(16)
        uid = _run(conn, _n("""
            INSERT INTO users (username, password_hash, salt, created_at)
            VALUES (:u, :h, :s, :ca)
        """), {"u": username, "h": _hash_password(password, salt), "s": salt,
               "ca": datetime.now().isoformat()})
        _commit(conn)
        return uid
    finally:
        _close(conn)


def verify_user(username: str, password: str):
    """Return the user row if the username/password match, else None."""
    ph = _ph()
    conn = get_conn()
    try:
        row = _q1(conn, f"SELECT * FROM users WHERE username = {ph}", (username.strip(),))
        if row and _hash_password(password, row["salt"]) == row["password_hash"]:
            return row
        return None
    finally:
        _close(conn)


def set_password(user_id, new_password: str):
    """Re-hash and store a new password for an existing account (fresh salt)."""
    salt = secrets.token_hex(16)
    ph = _ph()
    conn = get_conn()
    try:
        _run(conn, f"UPDATE users SET password_hash = {ph}, salt = {ph} WHERE id = {ph}",
             (_hash_password(new_password, salt), salt, user_id))
        _commit(conn)
    finally:
        _close(conn)


# ── Topics ─────────────────────────────────────────────────────────────────────

def get_topics(subject_id=None, high_yield_only=False):
    ph = _ph()
    sql = "SELECT t.*, s.name AS subject_name, s.color FROM topics t JOIN subjects s ON t.subject_id = s.id WHERE 1=1"
    params: list = []
    if subject_id:
        sql += f" AND t.subject_id = {ph}"
        params.append(subject_id)
    if high_yield_only:
        sql += " AND t.high_yield = 1"
    sql += " ORDER BY s.sort_order, t.name"
    conn = get_conn()
    try:
        return _q(conn, sql, tuple(params))
    finally:
        _close(conn)


def get_topic(topic_id):
    ph = _ph()
    conn = get_conn()
    try:
        return _q1(conn, f"SELECT * FROM topics WHERE id = {ph}", (topic_id,))
    finally:
        _close(conn)


def upsert_topic(data: dict):
    now = datetime.now().isoformat()
    data = dict(data)
    data.setdefault("high_yield", 0)
    data.setdefault("summary", "")
    data.setdefault("content", "")
    conn = get_conn()
    try:
        if data.get("id"):
            _run(conn, _n("""
                UPDATE topics SET subject_id=:subject_id, name=:name, high_yield=:high_yield,
                    summary=:summary, content=:content WHERE id=:id
            """), data)
        else:
            data["created_at"] = now
            data["id"] = _run(conn, _n("""
                INSERT INTO topics (subject_id, name, high_yield, summary, content, created_at)
                VALUES (:subject_id, :name, :high_yield, :summary, :content, :created_at)
            """), data)
        _commit(conn)
        return data["id"]
    finally:
        _close(conn)


def delete_topic(topic_id):
    ph = _ph()
    conn = get_conn()
    try:
        _run(conn, f"DELETE FROM topics WHERE id = {ph}", (topic_id,))
        _commit(conn)
    finally:
        _close(conn)


# ── Questions ──────────────────────────────────────────────────────────────────

def get_questions(subject_id=None, topic_id=None, difficulty=None, limit=None, include_inactive=False):
    ph = _ph()
    sql = """SELECT q.*, s.name AS subject_name, s.color, t.name AS topic_name,
                    p.title AS passage_title, p.body AS passage_body
             FROM questions q JOIN subjects s ON q.subject_id = s.id
             LEFT JOIN topics t ON q.topic_id = t.id
             LEFT JOIN passages p ON q.passage_id = p.id WHERE 1=1"""
    params: list = []
    if not include_inactive:
        sql += " AND (q.active = 1 OR q.active IS NULL)"
    if subject_id:
        sql += f" AND q.subject_id = {ph}"
        params.append(subject_id)
    if topic_id:
        sql += f" AND q.topic_id = {ph}"
        params.append(topic_id)
    if difficulty and difficulty != "All":
        sql += f" AND q.difficulty = {ph}"
        params.append(difficulty)
    sql += " ORDER BY q.id"
    if limit:
        sql += f" LIMIT {ph}"
        params.append(limit)
    conn = get_conn()
    try:
        return _q(conn, sql, tuple(params))
    finally:
        _close(conn)


def get_question_counts_by_subject():
    """Question bank size per subject in a single grouped query, instead of
    fetching every question for each subject separately just to count them."""
    conn = get_conn()
    try:
        return _q(conn, """
            SELECT s.id AS subject_id, s.name AS subject_name, s.color, COUNT(q.id) AS questions
            FROM subjects s LEFT JOIN questions q
                ON q.subject_id = s.id AND (q.active = 1 OR q.active IS NULL)
            GROUP BY s.id, s.name, s.color
            ORDER BY s.sort_order, s.name
        """)
    finally:
        _close(conn)


def upsert_question(data: dict):
    now = datetime.now().isoformat()
    data = dict(data)
    data.setdefault("topic_id", None)
    data.setdefault("explanation", "")
    data.setdefault("difficulty", "Medium")
    data.setdefault("option_e", None)
    conn = get_conn()
    try:
        if data.get("id"):
            _run(conn, _n("""
                UPDATE questions SET subject_id=:subject_id, topic_id=:topic_id, stem=:stem,
                    option_a=:option_a, option_b=:option_b, option_c=:option_c, option_d=:option_d,
                    option_e=:option_e, correct=:correct, explanation=:explanation,
                    difficulty=:difficulty WHERE id=:id
            """), data)
        else:
            data["created_at"] = now
            data["id"] = _run(conn, _n("""
                INSERT INTO questions (subject_id, topic_id, stem, option_a, option_b, option_c,
                    option_d, option_e, correct, explanation, difficulty, created_at)
                VALUES (:subject_id, :topic_id, :stem, :option_a, :option_b, :option_c,
                    :option_d, :option_e, :correct, :explanation, :difficulty, :created_at)
            """), data)
        _commit(conn)
        return data["id"]
    finally:
        _close(conn)


def delete_question(qid):
    ph = _ph()
    conn = get_conn()
    try:
        _run(conn, f"DELETE FROM questions WHERE id = {ph}", (qid,))
        _commit(conn)
    finally:
        _close(conn)


def record_attempt(user_id, question_id, subject_id, chosen, is_correct, seconds=0):
    conn = get_conn()
    try:
        _run(conn, _n("""
            INSERT INTO attempts (user_id, question_id, subject_id, chosen, is_correct, seconds, created_at)
            VALUES (:user_id, :question_id, :subject_id, :chosen, :is_correct, :seconds, :created_at)
        """), {"user_id": user_id, "question_id": question_id, "subject_id": subject_id, "chosen": chosen,
               "is_correct": 1 if is_correct else 0, "seconds": seconds,
               "created_at": datetime.now().isoformat()})
        _commit(conn)
    finally:
        _close(conn)


def record_mock_result(user_id, correct, total, cog_total=None):
    """Persist one completed Mock Exam so leaderboards can rank best scores.

    Individual attempts don't carry a session/exam id, so a mock's overall
    result has nowhere else to live once the results screen is left."""
    conn = get_conn()
    try:
        _run(conn, _n("""
            INSERT INTO mock_results (user_id, correct, total, cog_total, created_at)
            VALUES (:user_id, :correct, :total, :cog_total, :created_at)
        """), {"user_id": user_id, "correct": correct, "total": total, "cog_total": cog_total,
               "created_at": datetime.now().isoformat()})
        _commit(conn)
    finally:
        _close(conn)


# ── Flashcards (SM-2 lite spaced repetition) ───────────────────────────────────

def get_flashcard_bank():
    """List all flashcards (content only, no per-user progress) — for the Manage page."""
    conn = get_conn()
    try:
        return _q(conn, """
            SELECT f.id, f.subject_id, f.topic_id, f.front, f.back, f.created_at,
                   s.name AS subject_name, s.color, t.name AS topic_name
            FROM flashcards f JOIN subjects s ON f.subject_id = s.id
            LEFT JOIN topics t ON f.topic_id = t.id
            ORDER BY s.sort_order, f.id
        """)
    finally:
        _close(conn)


def get_flashcards(user_id, subject_id=None, due_only=False):
    """List flashcards along with this user's own spaced-repetition progress."""
    ph = _ph()
    sql = f"""SELECT f.id, f.subject_id, f.topic_id, f.front, f.back, f.created_at,
                     s.name AS subject_name, s.color, t.name AS topic_name,
                     COALESCE(p.ease, 2.5) AS ease, COALESCE(p.interval_days, 0) AS interval_days,
                     COALESCE(p.reps, 0) AS reps, p.due_date AS due_date, p.last_reviewed AS last_reviewed
              FROM flashcards f
              JOIN subjects s ON f.subject_id = s.id
              LEFT JOIN topics t ON f.topic_id = t.id
              LEFT JOIN flashcard_progress p ON p.flashcard_id = f.id AND p.user_id = {ph}
              WHERE 1=1"""
    params: list = [user_id]
    if subject_id:
        sql += f" AND f.subject_id = {ph}"
        params.append(subject_id)
    if due_only:
        today = date.today().isoformat()
        sql += f" AND (p.due_date IS NULL OR p.due_date <= {ph})"
        params.append(today)
    sql += " ORDER BY p.due_date NULLS FIRST, f.id" if _setup() else " ORDER BY p.due_date IS NOT NULL, p.due_date, f.id"
    conn = get_conn()
    try:
        return _q(conn, sql, tuple(params))
    finally:
        _close(conn)


def upsert_flashcard(data: dict):
    now = datetime.now().isoformat()
    data = dict(data)
    data.setdefault("topic_id", None)
    conn = get_conn()
    try:
        if data.get("id"):
            _run(conn, _n("""
                UPDATE flashcards SET subject_id=:subject_id, topic_id=:topic_id,
                    front=:front, back=:back WHERE id=:id
            """), data)
        else:
            data["created_at"] = now
            data["due_date"] = date.today().isoformat()
            data["id"] = _run(conn, _n("""
                INSERT INTO flashcards (subject_id, topic_id, front, back, due_date, created_at)
                VALUES (:subject_id, :topic_id, :front, :back, :due_date, :created_at)
            """), data)
        _commit(conn)
        return data["id"]
    finally:
        _close(conn)


def delete_flashcard(fid):
    ph = _ph()
    conn = get_conn()
    try:
        _run(conn, f"DELETE FROM flashcards WHERE id = {ph}", (fid,))
        _commit(conn)
    finally:
        _close(conn)


def review_flashcard(user_id, fid, quality: int):
    """Update this user's schedule for a card with SM-2-lite. quality 0=Again,3=Hard,4=Good,5=Easy."""
    ph = _ph()
    conn = get_conn()
    try:
        prog = _q1(conn, f"SELECT * FROM flashcard_progress WHERE user_id = {ph} AND flashcard_id = {ph}",
                   (user_id, fid)) or {}
        ease = prog.get("ease") or 2.5
        reps = prog.get("reps") or 0
        interval = prog.get("interval_days") or 0
        if quality < 3:
            reps = 0
            interval = 1
        else:
            reps += 1
            if reps == 1:
                interval = 1
            elif reps == 2:
                interval = 6
            else:
                interval = round(interval * ease)
            ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        interval = max(1, int(interval))
        due = (date.today() + timedelta(days=interval)).isoformat()
        params = {"user_id": user_id, "flashcard_id": fid, "ease": round(ease, 2), "reps": reps,
                  "interval": interval, "due": due, "now": datetime.now().isoformat()}
        upsert_sql = """
            INSERT INTO flashcard_progress (user_id, flashcard_id, ease, interval_days, reps, due_date, last_reviewed)
            VALUES (:user_id, :flashcard_id, :ease, :interval, :reps, :due, :now)
            ON CONFLICT (user_id, flashcard_id) DO UPDATE SET
                ease = excluded.ease, interval_days = excluded.interval_days,
                reps = excluded.reps, due_date = excluded.due_date, last_reviewed = excluded.last_reviewed
        """
        if _setup():
            with conn.cursor() as cur:
                cur.execute(_n(upsert_sql), params)
        else:
            conn.execute(upsert_sql, params)
        _commit(conn)
    finally:
        _close(conn)


# ── Study tasks (scheduler) ────────────────────────────────────────────────────

def get_study_tasks(user_id, status=None):
    ph = _ph()
    sql = f"""SELECT st.*, s.name AS subject_name, s.color
             FROM study_tasks st LEFT JOIN subjects s ON st.subject_id = s.id
             WHERE st.user_id = {ph}"""
    params: list = [user_id]
    if status and status != "All":
        sql += f" AND st.status = {ph}"
        params.append(status)
    sql += " ORDER BY st.due_date IS NULL, st.due_date, st.id"
    conn = get_conn()
    try:
        return _q(conn, sql, tuple(params))
    finally:
        _close(conn)


def upsert_study_task(user_id, data: dict):
    now = datetime.now().isoformat()
    data = dict(data)
    data["user_id"] = user_id
    data.setdefault("subject_id", None)
    data.setdefault("task_type", "Review")
    data.setdefault("duration_min", 60)
    data.setdefault("status", "Todo")
    data.setdefault("notes", "")
    conn = get_conn()
    try:
        if data.get("id"):
            _run(conn, _n("""
                UPDATE study_tasks SET title=:title, subject_id=:subject_id, task_type=:task_type,
                    due_date=:due_date, duration_min=:duration_min, status=:status, notes=:notes
                WHERE id=:id AND user_id=:user_id
            """), data)
        else:
            data["created_at"] = now
            data["id"] = _run(conn, _n("""
                INSERT INTO study_tasks (user_id, title, subject_id, task_type, due_date, duration_min, status, notes, created_at)
                VALUES (:user_id, :title, :subject_id, :task_type, :due_date, :duration_min, :status, :notes, :created_at)
            """), data)
        _commit(conn)
        return data["id"]
    finally:
        _close(conn)


def set_task_status(user_id, task_id, status):
    ph = _ph()
    conn = get_conn()
    try:
        _run(conn, f"UPDATE study_tasks SET status = {ph} WHERE id = {ph} AND user_id = {ph}",
             (status, task_id, user_id))
        _commit(conn)
    finally:
        _close(conn)


def delete_study_task(user_id, task_id):
    ph = _ph()
    conn = get_conn()
    try:
        _run(conn, f"DELETE FROM study_tasks WHERE id = {ph} AND user_id = {ph}", (task_id, user_id))
        _commit(conn)
    finally:
        _close(conn)


# ── Chat history (AI tutor) ────────────────────────────────────────────────────

def save_message(user_id, role: str, content: str):
    ph = _ph()
    conn = get_conn()
    try:
        _run(conn, f"INSERT INTO chat_history (user_id, role, content, created_at) VALUES ({ph}, {ph}, {ph}, {ph})",
             (user_id, role, content, datetime.now().isoformat()))
        _commit(conn)
    finally:
        _close(conn)


def get_chat_history(user_id, limit=50):
    ph = _ph()
    conn = get_conn()
    try:
        rows = _q(conn, f"SELECT role, content FROM chat_history WHERE user_id = {ph} ORDER BY id DESC LIMIT {ph}",
                  (user_id, limit))
        return list(reversed(rows))
    finally:
        _close(conn)


def clear_chat_history(user_id):
    ph = _ph()
    conn = get_conn()
    try:
        _run(conn, f"DELETE FROM chat_history WHERE user_id = {ph}", (user_id,))
        _commit(conn)
    finally:
        _close(conn)


# ── Per-user context (exam date etc.) ───────────────────────────────────────────

def set_context(user_id, key: str, value: str):
    now = datetime.now().isoformat()
    conn = get_conn()
    try:
        if _setup():
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO user_context (user_id, key, value, updated_at) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (user_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at",
                    (user_id, key, value, now))
        else:
            conn.execute("INSERT OR REPLACE INTO user_context (user_id, key, value, updated_at) VALUES (?, ?, ?, ?)",
                         (user_id, key, value, now))
        _commit(conn)
    finally:
        _close(conn)


def get_context(user_id, key: str, default=None):
    ph = _ph()
    conn = get_conn()
    try:
        row = _q1(conn, f"SELECT value FROM user_context WHERE user_id = {ph} AND key = {ph}", (user_id, key))
        return row["value"] if row else default
    finally:
        _close(conn)


# ── Analytics ──────────────────────────────────────────────────────────────────

def get_accuracy_by_subject(user_id):
    ph = _ph()
    conn = get_conn()
    try:
        return _q(conn, f"""
            SELECT s.id AS subject_id, s.name AS subject_name, s.color,
                   COUNT(a.id) AS attempts,
                   SUM(a.is_correct) AS correct,
                   AVG(a.seconds) AS avg_seconds
            FROM subjects s LEFT JOIN attempts a ON a.subject_id = s.id AND a.user_id = {ph}
            GROUP BY s.id, s.name, s.color
            ORDER BY s.sort_order, s.name
        """, (user_id,))
    finally:
        _close(conn)


def get_attempts_over_time(user_id, days=30):
    ph = _ph()
    start = (date.today() - timedelta(days=days)).isoformat()
    conn = get_conn()
    try:
        return _q(conn, f"""
            SELECT substr(created_at, 1, 10) AS day,
                   COUNT(*) AS attempts,
                   SUM(is_correct) AS correct
            FROM attempts WHERE user_id = {ph} AND created_at >= {ph}
            GROUP BY substr(created_at, 1, 10)
            ORDER BY day
        """, (user_id, start))
    finally:
        _close(conn)


def get_daily_pace(user_id, days=30):
    """Per day, per subject: attempts and total time spent, timed answers only.

    Zero-second entries (e.g. answers recorded before per-question timing was
    tracked) are excluded so they can't drag a historic average down to 0."""
    ph = _ph()
    start = (date.today() - timedelta(days=days)).isoformat()
    conn = get_conn()
    try:
        return _q(conn, f"""
            SELECT substr(a.created_at, 1, 10) AS day, s.code AS code,
                   COUNT(*) AS attempts, SUM(a.seconds) AS total_seconds
            FROM attempts a JOIN subjects s ON s.id = a.subject_id
            WHERE a.user_id = {ph} AND a.created_at >= {ph} AND a.seconds > 0
            GROUP BY substr(a.created_at, 1, 10), s.code
            ORDER BY day
        """, (user_id, start))
    finally:
        _close(conn)


# ── Leaderboards ─────────────────────────────────────────────────────────────
# Each returns every qualifying user ranked best-first (no LIMIT — the app
# layer slices the top N and separately locates the current user's own row,
# since the two aren't always the same slice).

def get_leaderboard_questions_answered():
    conn = get_conn()
    try:
        return _q(conn, """
            SELECT u.id AS user_id, u.username AS username, COUNT(*) AS value
            FROM attempts a JOIN users u ON u.id = a.user_id
            GROUP BY u.id, u.username
            ORDER BY value DESC
        """)
    finally:
        _close(conn)


def get_leaderboard_pace(min_attempts=50):
    """Fastest average seconds/question, restricted to users with enough timed
    attempts that a low average reflects real pace rather than a lucky handful
    of quick questions."""
    ph = _ph()
    conn = get_conn()
    try:
        return _q(conn, f"""
            SELECT u.id AS user_id, u.username AS username,
                   COUNT(*) AS attempts, AVG(a.seconds) AS value
            FROM attempts a JOIN users u ON u.id = a.user_id
            WHERE a.seconds > 0
            GROUP BY u.id, u.username
            HAVING COUNT(*) >= {ph}
            ORDER BY value ASC
        """, (min_attempts,))
    finally:
        _close(conn)


def get_leaderboard_mock_scores():
    """Best indicative cognitive total (out of 2700) each user has achieved
    across all their completed Mock Exams."""
    conn = get_conn()
    try:
        return _q(conn, """
            SELECT u.id AS user_id, u.username AS username, MAX(m.cog_total) AS value
            FROM mock_results m JOIN users u ON u.id = m.user_id
            WHERE m.cog_total IS NOT NULL
            GROUP BY u.id, u.username
            ORDER BY value DESC
        """)
    finally:
        _close(conn)


def get_overall_stats(user_id):
    ph = _ph()
    conn = get_conn()
    try:
        att = _q1(conn, f"SELECT COUNT(*) AS n, SUM(is_correct) AS correct FROM attempts WHERE user_id = {ph}",
                  (user_id,)) or {}
        cards = _q1(conn, "SELECT COUNT(*) AS n FROM flashcards") or {}
        today = date.today().isoformat()
        due = _q1(conn, f"""
            SELECT COUNT(*) AS n FROM flashcards f
            LEFT JOIN flashcard_progress p ON p.flashcard_id = f.id AND p.user_id = {ph}
            WHERE p.due_date IS NULL OR p.due_date <= {ph}
        """, (user_id, today)) or {}
        mastered = _q1(conn, f"SELECT COUNT(*) AS n FROM flashcard_progress WHERE user_id = {ph} AND reps >= 3",
                       (user_id,)) or {}
        tasks_done = _q1(conn, f"SELECT COUNT(*) AS n FROM study_tasks WHERE status = 'Done' AND user_id = {ph}",
                         (user_id,)) or {}
        tasks_total = _q1(conn, f"SELECT COUNT(*) AS n FROM study_tasks WHERE user_id = {ph}", (user_id,)) or {}
        qs = _q1(conn, "SELECT COUNT(*) AS n FROM questions") or {}
        return {
            "attempts": att.get("n") or 0,
            "correct": att.get("correct") or 0,
            "cards": cards.get("n") or 0,
            "cards_due": due.get("n") or 0,
            "cards_mastered": mastered.get("n") or 0,
            "tasks_done": tasks_done.get("n") or 0,
            "tasks_total": tasks_total.get("n") or 0,
            "questions": qs.get("n") or 0,
        }
    finally:
        _close(conn)


# ── Seed content ───────────────────────────────────────────────────────────────

_SUBJECTS = [
    ("VR",  "Verbal Reasoning",       "#3B6488", 1),
    ("DM",  "Decision Making",        "#6E5299", 2),
    ("QR",  "Quantitative Reasoning", "#12795C", 3),
    ("SJT", "Situational Judgement",  "#B06A2C", 4),
]

# topics: (subject_code, name, high_yield, summary, content)
_TOPICS = [
    ("VR", "Reading for the Main Idea", 1,
     "Skim efficiently — you have only seconds per question.",
     "Verbal Reasoning gives **~44 questions in ~21 minutes**, so you cannot read every passage in full.\n\n- **Scan for keywords** from the question, then read only the sentence(s) around them.\n- Decide each item from the **passage alone** — never from outside knowledge.\n- The credited answer is the one the text best supports, not the most interesting one."),
    ("VR", "True / False / Can't Tell", 1,
     "The classic VR judgement: is the statement supported, contradicted, or neither?",
     "- **True** — the passage directly states or clearly implies it.\n- **False** — the passage contradicts it.\n- **Can't Tell** — there isn't enough information to decide. Use this whenever the passage is silent.\n\n**Trap:** absolute words ('all', 'never', 'always') make a statement easy to falsify — a single exception in the text makes it false."),
    ("VR", "Inference & Author Tone", 0,
     "Reading between the lines without over-reaching.",
     "Inference questions ask what *follows* from the passage. Stay close to the text:\n\n- A valid inference needs no extra assumptions.\n- Watch the author's **tone** (critical, neutral, enthusiastic) and **purpose**.\n- Eliminate options that are too strong, out of scope, or the opposite of the author's view."),
    ("DM", "Syllogisms & Logical Deduction", 1,
     "Decide what necessarily follows from the premises.",
     "A conclusion is **valid only if it must be true** given the premises.\n\n- 'All A are B' + 'Some B are C' does **not** prove anything about A and C → *no valid conclusion*.\n- Test options by looking for a **counterexample**; if one exists, the option is invalid.\n- Beware switching 'some' ↔ 'all' and reversing direction ('all A are B' ≠ 'all B are A')."),
    ("DM", "Venn Diagrams & Sets", 1,
     "Counting with overlapping groups.",
     "For two sets: **|A ∪ B| = |A| + |B| − |A ∩ B|**.\n\n- 'Neither' = Total − |A ∪ B|.\n- 'Only A' = |A| − |A ∩ B|.\n- Draw the circles, fill the **overlap first**, then work outward. For three sets, start from the central triple-overlap."),
    ("DM", "Probability & Statistics", 1,
     "Basic probability and expected value under time pressure.",
     "- **Probability** = favourable outcomes ÷ total outcomes (equally likely).\n- Independent events: multiply (AND); mutually exclusive: add (OR).\n- 'At least one' = 1 − P(none).\n- Know how to read **odds** ('2 to 3') and convert to a probability (2/5)."),
    ("DM", "Logic Puzzles & Arrangements", 0,
     "Ordering, matching, and conditional clues.",
     "Decision Making often gives a set of clues and asks who/what fits.\n\n- Translate clues into a quick **grid or ordering**.\n- Process the **most restrictive clue first**.\n- Eliminate options that violate any single clue rather than fully solving every case."),
    ("QR", "Percentages & Percentage Change", 1,
     "The most common QR skill — increases, decreases, and reverse percentages.",
     "- **Increase by x%:** multiply by (1 + x/100). A 25% rise on 80 → 80 × 1.25 = 100.\n- **Percentage change:** (change ÷ original) × 100.\n- **Reverse percentage:** if a price after +20% is 120, original = 120 ÷ 1.2 = 100.\n- Use the on-screen calculator sparingly — many can be done mentally."),
    ("QR", "Ratios & Proportion", 1,
     "Sharing quantities and scaling recipes/doses.",
     "- Split a total in ratio a:b → fractions a/(a+b) and b/(a+b).\n- Keep units consistent before dividing.\n- Direct proportion: y = kx. Inverse proportion: xy = k.\n- Dose/recipe scaling is just multiplying every part by the same factor."),
    ("QR", "Speed, Distance & Time", 0,
     "The classic rate triangle.",
     "**Speed = Distance ÷ Time** (and rearrangements). 150 km in 2.5 h → 60 km/h.\n\n- Convert units first (km↔m, hours↔minutes).\n- Average speed = total distance ÷ total time, *not* the mean of the speeds.\n- The same triangle works for any rate (flow, dosage per hour, etc.)."),
    ("QR", "Tables, Charts & Data", 1,
     "Extracting the right number quickly from a stimulus.",
     "Most QR items hang off a shared table or chart.\n\n- Read the **question first**, then hunt for only the figures you need.\n- Watch **units and footnotes** ('figures in thousands', '% of total').\n- Don't recompute the whole table — target the single cell or row required."),
    ("SJT", "Appropriateness Ratings", 1,
     "Rate how appropriate a response is on the UCAT 4-point scale.",
     "The scale is: **Very appropriate · Appropriate, but not ideal · Inappropriate, but not awful · Very inappropriate.**\n\n- Judge the response **as written**, in isolation — not against other options.\n- Anything that risks **patient safety**, breaches confidentiality, or is dishonest tends toward *very inappropriate*.\n- A reasonable action that is incomplete or slightly out of order is usually *appropriate, but not ideal*."),
    ("SJT", "Importance Ratings", 1,
     "Rate how important a consideration is when deciding what to do.",
     "Scale: **Very important · Important · Of minor importance · Not important at all.**\n\n- Considerations tied to **patient safety, professional duty, and the people directly affected** are usually very important.\n- Irrelevant, self-serving, or speculative considerations are *not important*.\n- Don't confuse 'true' with 'important' — a true but irrelevant fact can still be unimportant."),
    ("SJT", "Medical Ethics & Professionalism", 1,
     "The values the SJT rewards, anchored in GMC Good Medical Practice.",
     "Default to the **GMC 'Good Medical Practice'** principles:\n\n- **Patient safety first**, always.\n- **Confidentiality, honesty and integrity** (probity).\n- **Work within your competence** and seek senior help when unsure.\n- Raise concerns about colleagues **supportively but without delay** when patients could be at risk. SJT is scored in **Bands 1–4** (Band 1 = strongest), separately from the cognitive subtests."),
]

# Legacy standalone questions: (subject_code, topic_name, stem, A, B, C, D, correct,
# explanation, difficulty). Decision Making only — its single-best-answer,
# four-option format is a genuine real-UCAT format, so these are seeded as-is.
# VR, QR and SJT legacy questions in this format were removed: VR and QR needed
# formats this shape can't represent (a shared passage, five options), and SJT
# needed multi-question scenario grouping — see _PASSAGE_SETS and
# _DM_YESNO_QUESTIONS for the exactly-formatted replacements.
_QUESTIONS = [
    ("DM", "Syllogisms & Logical Deduction",
     "\"All cardiologists are doctors. Some doctors work night shifts.\" Which conclusion necessarily follows?",
     "All cardiologists work night shifts",
     "Some cardiologists work night shifts",
     "No valid conclusion can be drawn about cardiologists and night shifts",
     "All doctors are cardiologists", "C",
     "The night-shift doctors might be entirely non-cardiologists, so nothing is guaranteed about cardiologists. With a possible counterexample, no valid conclusion follows.", "Hard"),
    ("DM", "Venn Diagrams & Sets",
     "In a group of 100 students, 60 study biology, 45 study chemistry, and 30 study both. How many study neither subject?",
     "15", "25", "30", "40", "B",
     "Students studying at least one = 60 + 45 − 30 = 75. Neither = 100 − 75 = 25.", "Medium"),
    ("DM", "Probability & Statistics",
     "A bag contains 3 red and 2 blue counters. One counter is drawn at random. What is the probability it is blue?",
     "2/5", "3/5", "1/2", "2/3", "A",
     "Probability = favourable ÷ total = 2 blue ÷ 5 counters = 2/5.", "Easy"),

    # ── Additional seeded questions ─────────────────────────────────────────

    ("DM", "Syllogisms & Logical Deduction",
     "\"No reptiles are mammals. All snakes are reptiles.\" Which conclusion necessarily follows?",
     "All snakes are mammals",
     "No snakes are mammals",
     "Some snakes are mammals",
     "Some mammals are snakes", "B",
     "If no reptiles are mammals and all snakes are reptiles, then snakes (being reptiles) cannot be mammals. So no snakes are mammals.", "Medium"),
    ("DM", "Venn Diagrams & Sets",
     "In a class of 40 students, 25 play football, 18 play tennis, and 5 play neither sport. How many play both?",
     "6", "7", "8", "9", "C",
     "Students playing at least one sport = 40 − 5 = 35. Using |F ∪ T| = |F| + |T| − both: 35 = 25 + 18 − both, so both = 8.", "Medium"),
    ("DM", "Probability & Statistics",
     "A fair six-sided die is rolled once. What is the probability of rolling a number greater than 4?",
     "1/6", "1/3", "1/2", "2/3", "B",
     "The outcomes greater than 4 are 5 and 6 — that is 2 of the 6 equally likely outcomes, giving 2/6 = 1/3.", "Easy"),
    ("DM", "Probability & Statistics",
     "A diagnostic test gives a positive result with probability 0.2. Two independent tests are run on different samples. What is the probability that both are positive?",
     "0.4", "0.2", "0.04", "0.004", "C",
     "For independent events you multiply: 0.2 × 0.2 = 0.04.", "Medium"),
    ("DM", "Logic Puzzles & Arrangements",
     "Four runners finish a race. Aki finishes before Ben, Ben finishes before Cara, and Dia finishes after Cara. Who finishes last?",
     "Aki", "Ben", "Cara", "Dia", "D",
     "The clues chain together as Aki → Ben → Cara → Dia, so Dia finishes last.", "Easy"),
    ("DM", "Logic Puzzles & Arrangements",
     "Three colleagues — X, Y and Z — sit in a row of three seats. X is not at either end, and Y sits immediately to the left of X. Who sits at the right-hand end?",
     "X", "Y", "Z", "It cannot be determined", "C",
     "X must be in the middle seat; Y is immediately to X's left, so Y takes the left end, leaving Z at the right-hand end.", "Medium"),

    # ── Extended bank: higher-difficulty, exam-realistic questions ───────────
    ("DM", "Syllogisms & Logical Deduction",
     "\"All vaccines require refrigeration. Some medicines do not require refrigeration.\" Which conclusion necessarily follows?",
     "All medicines are vaccines",
     "Some medicines are not vaccines",
     "No vaccines are medicines",
     "All vaccines are medicines", "B",
     "Since all vaccines require refrigeration, anything that does not require refrigeration cannot be a vaccine. The medicines that don't require refrigeration are therefore not vaccines, so some medicines are not vaccines.", "Hard"),
    ("DM", "Syllogisms & Logical Deduction",
     "\"Every registrar has completed at least four years of training. Priya has completed three years of training.\" Which conclusion necessarily follows?",
     "Priya is not a registrar",
     "Priya will never become a registrar",
     "Priya is training to become a registrar",
     "All registrars have completed exactly four years", "A",
     "Since every registrar has completed at least four years and Priya has only completed three, Priya cannot currently be a registrar. The other options go beyond what the premises establish.", "Medium"),
    ("DM", "Syllogisms & Logical Deduction",
     "\"No first-year students may access the senior common room. Tom has access to the senior common room.\" Which conclusion necessarily follows?",
     "Tom is a first-year student",
     "Tom is not a first-year student",
     "Tom is a member of staff",
     "The senior common room has no rules", "B",
     "If first-year students cannot access the room and Tom does have access, Tom cannot be a first-year student.", "Easy"),
    ("DM", "Syllogisms & Logical Deduction",
     "\"Some surgeons are researchers. All researchers publish papers.\" Which conclusion necessarily follows?",
     "All surgeons publish papers",
     "Some surgeons publish papers",
     "No surgeons publish papers",
     "All people who publish papers are surgeons", "B",
     "The surgeons who are also researchers must publish papers, since all researchers do — so some surgeons publish papers. We cannot conclude ALL surgeons do, since only 'some' are researchers.", "Medium"),
    ("DM", "Venn Diagrams & Sets",
     "Of 80 clinic patients, 50 have high blood pressure, 35 have high cholesterol, and 20 have both. How many have neither condition?",
     "10", "15", "20", "25", "B",
     "At least one condition = 50 + 35 − 20 = 65. Neither = 80 − 65 = 15.", "Medium"),
    ("DM", "Venn Diagrams & Sets",
     "In a survey of 60 students, 42 study French, 10 study neither French nor German, and 8 study both languages. How many study German only?",
     "8", "10", "18", "26", "A",
     "At least one language = 60 − 10 = 50. Studying French only = 42 − 8 = 34. German only = 50 − 34 − 8 = 8.", "Hard"),
    ("DM", "Venn Diagrams & Sets",
     "A group of 25 people are asked if they like tea or coffee. 15 like tea, 12 like coffee, and 4 like neither. How many like both?",
     "4", "6", "8", "10", "B",
     "At least one = 25 − 4 = 21. Both = 15 + 12 − 21 = 6.", "Medium"),
    ("DM", "Venn Diagrams & Sets",
     "In a class of 30, everyone studies at least one of Biology or Chemistry. 22 study Biology and 19 study Chemistry. How many study both?",
     "9", "11", "13", "15", "B",
     "Since everyone studies at least one subject, at-least-one = 30. Both = 22 + 19 − 30 = 11.", "Easy"),
    ("DM", "Probability & Statistics",
     "A box contains 4 red, 3 green and 3 blue balls. One ball is drawn at random. What is the probability it is NOT green?",
     "3/10", "7/10", "4/10", "1/10", "B",
     "P(green) = 3/10, so P(not green) = 1 − 3/10 = 7/10.", "Easy"),
    ("DM", "Probability & Statistics",
     "Two fair coins are tossed. What is the probability that at least one lands heads?",
     "1/4", "1/2", "3/4", "1", "C",
     "P(no heads, i.e. tails-tails) = 1/4. P(at least one heads) = 1 − 1/4 = 3/4.", "Medium"),
    ("DM", "Probability & Statistics",
     "A screening test correctly identifies a disease in 90% of people who have it. Out of 200 people known to have the disease, how many would the test be expected to correctly identify?",
     "90", "160", "180", "190", "C",
     "90% of 200 = 180.", "Easy"),
    ("DM", "Probability & Statistics",
     "A drawer contains 5 pairs of socks (10 individual socks, all different pairs). If two socks are drawn at random without replacement, what is the probability they form a matching pair?",
     "1/10", "1/9", "2/10", "1/5", "B",
     "Whatever the first sock is, exactly one matching sock remains among the other 9 socks, so the probability of drawing its pair second is 1/9.", "Hard"),
    ("DM", "Logic Puzzles & Arrangements",
     "Five friends — P, Q, R, S, T — are seated in a row. P is at one end. Q is not next to P. R is exactly in the middle. Which of the following could sit next to P?",
     "Only Q",
     "S or T only",
     "Q or R",
     "It cannot be determined", "B",
     "P is at one end and R is fixed in the middle seat, which is two seats from either end, so R can never be next to P. Since Q is explicitly barred from sitting next to P, the seat beside P must be S or T.", "Hard"),
    ("DM", "Logic Puzzles & Arrangements",
     "Four colleagues — Amir, Beth, Cho and Dan — each work a different one of Monday, Tuesday, Wednesday and Thursday. Amir works earlier in the week than Beth. Cho works immediately after Amir. Dan works on Thursday. What day does Beth work?",
     "Monday", "Tuesday", "Wednesday", "Thursday", "C",
     "Dan takes Thursday, leaving Monday, Tuesday and Wednesday for Amir, Beth and Cho. Cho must immediately follow Amir, and Amir must precede Beth. The only fit is Amir = Monday, Cho = Tuesday, Beth = Wednesday.", "Hard"),
    ("DM", "Logic Puzzles & Arrangements",
     "In a queue of six people, Sam is third from the front. There are exactly two people between Sam and Priya, with Priya further back. How many people are behind Priya?",
     "0", "1", "2", "3", "A",
     "Sam is 3rd; with exactly two people between Sam and Priya (positions 4 and 5) and Priya further back, Priya must be 6th in a queue of six, leaving no one behind her.", "Medium"),

    # ── Extended bank, round 2: additional exam-realistic questions ─────────
    ("DM", "Syllogisms & Logical Deduction",
     "\"All qualified pharmacists have completed a registration exam. Jamie has not completed a registration exam.\" Which conclusion necessarily follows?",
     "Jamie is not a qualified pharmacist",
     "Jamie will never qualify as a pharmacist",
     "Jamie is training to be a pharmacist",
     "All registration exams are difficult", "A",
     "By the contrapositive of 'all qualified pharmacists completed the exam': not completing the exam means Jamie cannot currently be a qualified pharmacist.", "Easy"),
    ("DM", "Syllogisms & Logical Deduction",
     "\"No honorary members pay a subscription fee. All committee members pay a subscription fee.\" Which conclusion necessarily follows?",
     "No committee members are honorary members",
     "All honorary members are committee members",
     "Some committee members are honorary members",
     "All members pay a subscription fee", "A",
     "Honorary members never pay a fee, while committee members always do, so no one can be both — no committee members are honorary members.", "Medium"),
    ("DM", "Syllogisms & Logical Deduction",
     "\"Some clinical trials are funded by industry. No industry-funded trials are eligible for the independent research grant.\" Which conclusion necessarily follows?",
     "All clinical trials are eligible for the independent research grant",
     "Some clinical trials are not eligible for the independent research grant",
     "No clinical trials are eligible for the independent research grant",
     "All industry-funded trials receive the independent research grant", "B",
     "The industry-funded trials (some clinical trials) are not eligible, so some clinical trials are not eligible. We cannot conclude ALL are ineligible, since only 'some' are industry-funded.", "Medium"),
    ("DM", "Syllogisms & Logical Deduction",
     "\"Every applicant who fails the written test is not shortlisted. Kim was shortlisted.\" Which conclusion necessarily follows?",
     "Kim failed the written test",
     "Kim passed the written test",
     "Kim did not sit the written test",
     "Kim was not shortlisted", "B",
     "By the contrapositive: being shortlisted means Kim did not fail, so (assuming a pass/fail outcome) Kim passed.", "Medium"),
    ("DM", "Syllogisms & Logical Deduction",
     "\"All the volunteers who signed up before March received a welcome pack. Every volunteer who received a welcome pack attended the induction session.\" Which conclusion necessarily follows?",
     "All volunteers who signed up before March attended the induction session",
     "All volunteers attended the induction session",
     "No volunteers signed up after March",
     "All volunteers who attended the induction session signed up before March", "A",
     "Chaining the two conditionals: signing up before March leads to receiving a pack, which leads to attending induction. So all who signed up before March attended induction. B, C and D overreach beyond what's given.", "Easy"),
    ("DM", "Syllogisms & Logical Deduction",
     "\"Not all consultants supervise trainees. Every trainee is supervised by a consultant.\" Which conclusion necessarily follows?",
     "Some consultants do not supervise trainees",
     "All consultants supervise trainees",
     "No trainees are supervised",
     "All consultants are trainees", "A",
     "'Not all consultants supervise trainees' is logically equivalent to 'some consultants do not supervise trainees', so this follows directly from the first premise.", "Easy"),
    ("DM", "Venn Diagrams & Sets",
     "Of 120 attendees at a conference, 70 attended the morning session, 55 attended the afternoon session, and 15 attended neither. How many attended both sessions?",
     "15", "20", "25", "30", "B",
     "At least one session = 120 − 15 = 105. Both = 70 + 55 − 105 = 20.", "Medium"),
    ("DM", "Venn Diagrams & Sets",
     "In a group of 45 people, everyone owns a cat, a dog, or both. 30 own a cat and 25 own a dog. How many own both?",
     "5", "8", "10", "12", "C",
     "Since everyone owns at least one pet, at-least-one = 45. Both = 30 + 25 − 45 = 10.", "Easy"),
    ("DM", "Venn Diagrams & Sets",
     "A survey of 90 patients found 54 have a family history of diabetes, 38 have a family history of hypertension, and 20 have neither family history. How many have a family history of both conditions?",
     "12", "18", "20", "22", "D",
     "At least one = 90 − 20 = 70. Both = 54 + 38 − 70 = 22.", "Medium"),
    ("DM", "Venn Diagrams & Sets",
     "Of 200 students, 120 take Spanish, 90 take German, and 40 take neither language. How many take exactly one of the two languages?",
     "90", "100", "110", "120", "C",
     "At least one = 200 − 40 = 160. Both = 120 + 90 − 160 = 50. Exactly one = 160 − 50 = 110.", "Hard"),
    ("DM", "Venn Diagrams & Sets",
     "In a clinic of 60 staff, 35 can perform procedure A and 28 can perform procedure B. If 10 staff can perform neither procedure, how many can perform only procedure A?",
     "13", "15", "20", "22", "D",
     "At least one = 60 − 10 = 50. Both = 35 + 28 − 50 = 13. Only A = 35 − 13 = 22.", "Hard"),
    ("DM", "Venn Diagrams & Sets",
     "Every member of a 50-person choir sings either soprano or alto, or both. 32 sing soprano and 26 sing alto. How many sing both parts?",
     "6", "8", "10", "12", "B",
     "Since everyone sings at least one part, at-least-one = 50. Both = 32 + 26 − 50 = 8.", "Easy"),
    ("DM", "Probability & Statistics",
     "A jar contains 6 blue and 4 yellow marbles. One marble is drawn and not replaced, then a second is drawn. What is the probability both are blue?",
     "1/4", "3/10", "1/3", "3/5", "C",
     "P(first blue) = 6/10. P(second blue | first blue) = 5/9. Combined = 6/10 × 5/9 = 30/90 = 1/3.", "Medium"),
    ("DM", "Probability & Statistics",
     "A vaccine is 80% effective at preventing infection. In a group of 150 vaccinated people exposed to the virus, how many would be expected to become infected?",
     "20", "24", "30", "35", "C",
     "20% of 150 = 30 people not protected.", "Easy"),
    ("DM", "Probability & Statistics",
     "A fair six-sided die is rolled twice. What is the probability of rolling a total of 7?",
     "1/12", "1/9", "1/6", "1/4", "C",
     "Six of the 36 equally likely outcomes sum to 7: (1,6), (2,5), (3,4), (4,3), (5,2), (6,1). 6/36 = 1/6.", "Medium"),
    ("DM", "Probability & Statistics",
     "In a class, the probability a randomly chosen student studies medicine is 0.3, and the probability a randomly chosen student studies dentistry is 0.15. No student studies both. What is the probability a randomly chosen student studies neither?",
     "0.45", "0.5", "0.55", "0.65", "C",
     "Since the events are mutually exclusive, P(either) = 0.3 + 0.15 = 0.45. P(neither) = 1 − 0.45 = 0.55.", "Easy"),
    ("DM", "Probability & Statistics",
     "A test has a false positive rate of 5%. If 300 healthy people are tested, how many would be expected to test positive incorrectly?",
     "10", "15", "20", "25", "B",
     "5% of 300 = 15.", "Easy"),
    ("DM", "Probability & Statistics",
     "Three coins are tossed. What is the probability of getting exactly two heads?",
     "1/8", "1/4", "3/8", "1/2", "C",
     "There are 8 equally likely outcomes; exactly two heads occurs in 3 of them (HHT, HTH, THH). 3/8.", "Medium"),
    ("DM", "Probability & Statistics",
     "A hospital reports that 1 in 8 patients admitted with chest pain are later diagnosed with a cardiac event. Out of 640 such admissions, how many would be expected to receive that diagnosis?",
     "60", "70", "80", "90", "C",
     "640 ÷ 8 = 80.", "Easy"),
    ("DM", "Logic Puzzles & Arrangements",
     "Four patients — A, B, C, D — are seen in a clinic in some order. A is seen before C. B is seen immediately after A. D is seen last. What is the order in which they are seen?",
     "A, B, C, D", "A, C, B, D", "B, A, C, D", "A, B, D, C", "A",
     "D takes the last slot. B must immediately follow A, and A must come before C. The only arrangement of the remaining three slots that satisfies both is A, B, C.", "Medium"),
    ("DM", "Logic Puzzles & Arrangements",
     "Five books are stacked. The blue book is directly above the red book. The green book is at the very top. The yellow book is directly below the red book, and the black book is directly below the yellow book. What is the order from top to bottom?",
     "Green, blue, red, yellow, black",
     "Blue, green, red, yellow, black",
     "Green, red, blue, yellow, black",
     "Green, blue, yellow, red, black", "A",
     "The chain blue-above-red-above-yellow-above-black is fixed, with green sitting at the very top above that whole chain.", "Medium"),
    ("DM", "Logic Puzzles & Arrangements",
     "In a race with only four runners, Chen finishes ahead of Diaz, Diaz finishes ahead of Evans, and Farrow finishes ahead of Chen. What is the earliest possible finishing position for Evans?",
     "1st", "2nd", "3rd", "4th", "D",
     "The three constraints chain into a single strict order: Farrow, then Chen, then Diaz, then Evans. With only four runners, this fixes Evans in 4th place — there is no earlier possibility.", "Easy"),
    ("DM", "Logic Puzzles & Arrangements",
     "Six chairs are arranged in a row, numbered 1 to 6. Nia sits two seats to the right of Omar. If Nia sits in seat 5, which seat does Omar sit in?",
     "1", "2", "3", "4", "C",
     "Nia's seat number = Omar's seat number + 2, so Omar = 5 − 2 = seat 3.", "Easy"),
    ("DM", "Logic Puzzles & Arrangements",
     "Four interns rotate through four departments — Surgery, Medicine, Paediatrics and A&E — one each, over four weeks, one department per week. Intern 1 is in Surgery in week 2 and in Medicine the week immediately before Surgery. Which week is Intern 1 in Medicine?",
     "Week 1", "Week 2", "Week 3", "Week 4", "A",
     "Surgery is in week 2, and Medicine is the week immediately before Surgery — week 1.", "Easy"),
    ("DM", "Logic Puzzles & Arrangements",
     "A committee of three — Owen, Priya, Rana — must be seated in a row of three seats so that Owen is not adjacent to Priya. How many valid seating arrangements are there (treating left-to-right order as distinct)?",
     "1", "2", "3", "4", "B",
     "In a row of three, only seats 1 and 3 are non-adjacent. Owen and Priya must occupy those two seats (in either order), with Rana always in the middle — giving exactly 2 valid arrangements out of the 6 possible orderings.", "Hard"),
]

# ── Passage sets: a shared stimulus + a series of linked questions ────────────
# This mirrors real UCAT format — especially Verbal Reasoning, where one long
# passage is followed by four questions, and Quantitative Reasoning, where a
# table or scenario feeds several calculations.
# Shape: (subject_code, topic_name, title, body, [
#            (stem, A, B, C, D, correct, explanation, difficulty), ... ])
_PASSAGE_SETS = [
    ("VR", "True / False / Can't Tell",
     "The Pharos of Alexandria",
     "The Pharos of Alexandria, completed around 280 BCE on the orders of Ptolemy II, was for many "
     "centuries the tallest man-made structure in the world after the Great Pyramid of Giza. "
     "Contemporary accounts describe a three-tiered tower: a square base, an octagonal middle section, "
     "and a cylindrical top from which a fire burned at night to guide ships into the busy harbour. "
     "Estimates of its height vary widely among ancient writers, ranging from roughly 100 to 140 metres, "
     "and no consensus has been reached by modern scholars. Later legends — unsupported by any "
     "contemporary source — claimed that a great mirror at its summit could focus the sun's rays to burn "
     "enemy vessels far out at sea. A series of earthquakes between the tenth and fourteenth centuries "
     "progressively damaged the structure, and by 1480 its remaining stones had been used to build a "
     "fortress on the same site. In 1994, archaeologists diving in the harbour recovered hundreds of "
     "large masonry blocks and statue fragments believed to have fallen from the lighthouse, though "
     "exactly which pieces belonged to the tower itself remains disputed.",
     [
         ("Statement: The exact original height of the Pharos is known with certainty. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "B",
          "The passage says estimates range from about 100 to 140 metres with 'no consensus' among modern "
          "scholars, so the exact height is not known — the statement is contradicted, making it False.", "Medium"),
         ("Statement: The mirror said to sit at the summit could burn enemy ships far out at sea. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "C",
          "The passage reports this only as a later legend 'unsupported by any contemporary source'. It "
          "neither confirms nor denies the claim, so there isn't enough information to judge it — Can't tell. "
          "Note the trap: 'unsupported' is not the same as proven false.", "Hard"),
         ("Which statement is best supported by the passage on the Pharos of Alexandria?",
          "Stone from the ruined lighthouse was reused to build a fortress on the same site",
          "The Pharos was the tallest structure ever built by humans",
          "The 1994 dive proved that every recovered block came from the lighthouse",
          "A single earthquake destroyed the Pharos", "A",
          "The text states its remaining stones 'had been used to build a fortress on the same site'. B "
          "overreaches (only tallest after the Great Pyramid, and only for centuries); C is disputed; and "
          "the damage came from 'a series of earthquakes', progressively — not one event.", "Medium"),
         ("Statement: The Pharos was completed on the orders of Ptolemy II. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "A",
          "This is stated directly: 'completed around 280 BCE on the orders of Ptolemy II'.", "Easy"),
     ]),

    ("VR", "Inference & Author Tone",
     "Birdsong Dialects",
     "Many songbird species learn their songs rather than inheriting them fully formed, and this learning "
     "produces regional variations that ornithologists compare to human dialects. A young bird typically "
     "memorises the songs it hears during a sensitive period in its first months of life, then refines its "
     "own output to match that template. Because the template is local, birds in neighbouring valleys can "
     "develop recognisably different songs, and these differences can persist for generations. Researchers "
     "studying white-crowned sparrows in California documented dialect boundaries so sharp that birds a few "
     "kilometres apart sang distinctly different versions. The function of these dialects is debated. One "
     "hypothesis holds that females prefer males singing the local dialect, which would reinforce "
     "boundaries over time; another proposes that dialects are simply an incidental by-product of song "
     "learning with no adaptive purpose. Experiments in which young sparrows were played recordings of "
     "foreign dialects showed that the birds could learn them, indicating that the dialect a bird sings "
     "depends on what it hears, not on where its parents came from. Notably, a small number of birds sing "
     "'bilingual' songs at dialect boundaries, switching between versions depending on which neighbours "
     "they are addressing.",
     [
         ("Statement: The dialect a white-crowned sparrow sings is fixed by the region its parents came "
          "from. Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "B",
          "Playback experiments showed young birds learn whatever dialect they hear, so the dialect depends "
          "on what a bird hears, 'not on where its parents came from' — the statement is contradicted, "
          "making it False.", "Medium"),
         ("Which statement about birdsong dialects is best supported by the passage?",
          "Song dialects can persist across several generations",
          "All songbird species inherit their songs fully formed at birth",
          "Females have been proven to prefer males singing the local dialect",
          "Bilingual songs are typical across the whole sparrow population", "A",
          "The text says the differences 'can persist for generations'. B contradicts the opening ('many "
          "... learn'); C is only one debated, unproven hypothesis; and bilingual birds are 'a small "
          "number ... at dialect boundaries', not typical.", "Medium"),
         ("Statement: Scientists agree on the purpose that song dialects serve. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "B",
          "The passage says 'the function of these dialects is debated' and sets out two competing "
          "hypotheses, so there is no agreement — the statement is contradicted, making it False.", "Medium"),
         ("According to the passage, the 'bilingual' birds:",
          "switch song versions according to which neighbours they are addressing",
          "sing only at the centre of a dialect region",
          "are unable to learn either dialect properly",
          "prove that dialects serve no purpose", "A",
          "The passage says they occur at boundaries and switch versions 'depending on which neighbours "
          "they are addressing'. The other options are unsupported or contradicted.", "Hard"),
     ]),

    ("VR", "Reading for the Main Idea",
     "The Potato Comes to Europe",
     "The potato, native to the Andes, reached Europe in the second half of the sixteenth century, most "
     "likely carried back by Spanish ships. Its adoption was slow and uneven. In several regions the plant "
     "was regarded with suspicion: it belonged to the nightshade family, some of whose relatives are "
     "poisonous, and because it was not mentioned in the Bible a few communities distrusted it on "
     "principle. Botanists initially grew it as a curiosity in ornamental gardens rather than as a food "
     "crop. Attitudes shifted over the following two centuries. The potato yielded more calories per acre "
     "than the grain crops it competed with, tolerated poor soils, and could be left in the ground until "
     "needed, which made it harder for passing armies to seize or destroy. Governments came to see these "
     "traits as valuable. In France, the agronomist Antoine Parmentier promoted the crop energetically "
     "after eating potatoes as a prisoner of war, staging banquets and, according to a popular story, "
     "posting guards around a potato field by day so that peasants would assume the crop was valuable and "
     "steal it by night. By the nineteenth century the potato had become a staple across much of northern "
     "Europe. This dependence carried a risk that became tragically clear when a fungal blight destroyed "
     "successive harvests in the 1840s.",
     [
         ("Which of the following best expresses the main idea of the passage on the potato's journey to "
          "Europe?",
          "The potato's rise from a distrusted curiosity to a European staple was gradual and driven by "
          "its practical advantages",
          "The potato was accepted enthusiastically as soon as it arrived in Europe",
          "Antoine Parmentier single-handedly made the potato popular across Europe",
          "The potato was always considered poisonous by European botanists", "A",
          "The passage traces a slow, uneven adoption that grew as governments recognised the crop's yield, "
          "hardiness and military usefulness. B contradicts 'slow and uneven'; C overstates one figure's "
          "role; and botanists grew it as a curiosity, not as something always deemed poisonous.", "Medium"),
         ("Statement: Distrust of the potato was partly because it was not mentioned in the Bible. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "A",
          "This reason is stated directly in the passage.", "Easy"),
         ("Statement: The potato produced fewer calories per acre than the competing grain crops. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "B",
          "The passage says it 'yielded more calories per acre than the grain crops it competed with' — the "
          "statement is contradicted, making it False.", "Medium"),
         ("Statement: Parmentier really did post guards around his potato field to make the crop seem "
          "valuable. Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "C",
          "The passage attributes the guarding to 'a popular story' and does not vouch for whether it "
          "actually happened, so there isn't enough information to treat it as fact — Can't tell.", "Hard"),
     ]),

    ("VR", "True / False / Can't Tell",
     "The Standardisation of Time",
     "Before the nineteenth century, towns kept their own local time, set by the position of the sun, so "
     "that clocks in one city might differ by several minutes from those in a city to its east or west. "
     "For most purposes this caused no difficulty, because travel was slow. The spread of the railway "
     "changed matters. Trains ran to timetables, and a timetable is useless if every station measures time "
     "differently; a difference of a few minutes could mean a missed connection or, worse, two trains on "
     "the same track. British railway companies therefore adopted a single standard — the time kept at the "
     "Greenwich observatory — and by 1847 most had synchronised their clocks to it, sending the signal "
     "along the telegraph lines that ran beside the tracks. Some towns resisted, keeping a separate "
     "'local' time on a second minute hand for years, and it was not until 1880 that a single legal time "
     "for the whole of Great Britain was fixed by statute. The principle spread internationally later in "
     "the century, when delegates agreed to divide the world into standard time zones measured from "
     "Greenwich. The convenience of the railways, rather than any scientific argument about the nature of "
     "time, had driven the change.",
     [
         ("Statement: Before the nineteenth century, all British towns kept exactly the same time. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "B",
          "Towns kept their own local time, differing by several minutes — the statement is contradicted, "
          "making it False.", "Medium"),
         ("Statement: A single legal time for the whole of Great Britain was fixed by statute before 1850. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "B",
          "The railways synchronised to Greenwich by 1847, but the statute fixing a single legal time came "
          "in 1880 — so the statement is contradicted, making it False.", "Hard"),
         ("Which statement is best supported by the passage on the standardisation of time?",
          "The railways adopted standard time mainly to avoid missed connections and collisions",
          "Standard time was introduced because scientists proved local time was inaccurate",
          "Every town abandoned its local time immediately once the railways synchronised",
          "Time zones measured from Greenwich were agreed before the railways existed", "A",
          "The passage ties the change to timetables and safety ('a missed connection or ... two trains on "
          "the same track') and says convenience, 'rather than any scientific argument', drove it. B "
          "contradicts that; some towns resisted 'for years'; and the zones came later.", "Medium"),
         ("Statement: The standard time signal was distributed using telegraph lines running beside the "
          "railway tracks. Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "A",
          "This is stated directly: the signal was sent 'along the telegraph lines that ran beside the "
          "tracks'.", "Easy"),
     ]),

    ("VR", "Inference & Author Tone",
     "The London Coffee Houses",
     "When coffee houses first appeared in seventeenth-century London, they were greeted with both "
     "enthusiasm and alarm. For the price of a penny — the cost of a single cup — a man could enter, sit "
     "for hours, read the newspapers provided, and join the conversation, which earned the establishments "
     "the nickname 'penny universities'. Unlike taverns, coffee houses served a drink that sharpened "
     "rather than dulled the mind, and they became centres for the exchange of news, gossip, and "
     "commercial intelligence. Particular houses specialised: one near the docks became a place where "
     "ship-owners and underwriters met to arrange marine insurance, and in time that gathering grew into a "
     "famous insurance market. Others were frequented by poets, or by traders in stocks. The authorities "
     "were uneasy. Because men of different ranks mixed freely and spoke openly about politics, the "
     "government of the day suspected the houses of breeding sedition, and in 1675 a royal proclamation "
     "attempted to close them. The outcry was such that the order was withdrawn within days. The writer "
     "clearly regards the coffee houses as a lively and productive feature of the city, noting that "
     "several modern institutions can trace their origins to a table in one of them.",
     [
         ("Which statement is best supported by the passage on the London coffee houses?",
          "A famous insurance market grew out of meetings held in a coffee house",
          "Coffee houses were quieter and more orderly than taverns",
          "The 1675 proclamation succeeded in closing the coffee houses permanently",
          "Only poets were allowed into the coffee houses", "A",
          "The passage says a dockside house where ship-owners and underwriters met 'grew into a famous "
          "insurance market'. B is not supported; the proclamation was 'withdrawn within days'; and men of "
          "'different ranks mixed freely', so D is contradicted.", "Medium"),
         ("How would you best describe the author's attitude towards the coffee houses?",
          "Strongly hostile",
          "Broadly approving — the author sees them as lively and productive",
          "Indifferent and purely neutral",
          "Nostalgic regret that they were dangerous", "B",
          "The final sentence states the writer 'clearly regards the coffee houses as a lively and "
          "productive feature of the city'.", "Medium"),
         ("Statement: The government of the day welcomed the free political discussion in the coffee "
          "houses. Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "B",
          "The authorities were 'uneasy', suspected sedition, and even tried to close the houses — the "
          "statement is contradicted, making it False.", "Medium"),
         ("Statement: A single cup of coffee in these houses cost a penny. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "A",
          "Stated directly: 'the price of a penny — the cost of a single cup'.", "Easy"),
     ]),

    ("VR", "Reading for the Main Idea",
     "Sleep and Memory",
     "It has long been observed that people remember newly learned material better after a night's sleep "
     "than after an equal period awake, but only recently have researchers begun to explain why. During "
     "sleep the brain does not simply rest; certain stages are marked by patterns of electrical activity "
     "that appear to replay the neural sequences active during waking learning, as though rehearsing them. "
     "This replay is thought to strengthen the connections that encode a memory and to transfer "
     "information from short-term storage in the hippocampus to more durable storage in the cortex. "
     "Different stages of sleep may serve different functions: slow-wave sleep, which dominates the early "
     "part of the night, seems especially important for factual memories, while the rapid-eye-movement "
     "stage, more common towards morning, has been linked to emotional and procedural learning. Studies in "
     "which volunteers were deprived of sleep after learning a task, or woken selectively during "
     "particular stages, generally show impaired recall compared with those allowed to sleep normally. "
     "Researchers are careful to note, however, that most of this evidence is correlational, and that the "
     "precise mechanisms remain uncertain. What is not disputed is that cutting sleep short to cram for an "
     "examination is likely to be counter-productive.",
     [
         ("Which best captures the main idea of the passage?",
          "Sleep has no measurable effect on memory",
          "Sleep appears to help consolidate memories, though the exact mechanisms are still uncertain",
          "Only rapid-eye-movement sleep matters for memory of any kind",
          "Scientists have fully explained how sleep stores memories", "B",
          "The passage describes evidence that sleep aids consolidation while stressing the mechanisms "
          "'remain uncertain'. A contradicts the evidence; C ignores slow-wave sleep's role in factual "
          "memory; and D overstates what is known.", "Medium"),
         ("Statement: Slow-wave sleep is more common in the early part of the night. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "A",
          "Stated directly: 'slow-wave sleep, which dominates the early part of the night'.", "Easy"),
         ("Which statement about sleep and memory is best supported by the passage?",
          "Rapid-eye-movement sleep is most important for factual memories",
          "Sleeping less in order to cram is an effective exam strategy",
          "The evidence that sleep consolidates memory is largely correlational",
          "The hippocampus is where memories are stored permanently", "C",
          "The passage says 'most of this evidence is correlational'. A swaps the stages (REM is linked to "
          "emotional/procedural learning, slow-wave to factual); B is contradicted by the last sentence; "
          "and the hippocampus is described as short-term storage, the cortex as durable.", "Hard"),
         ("Which practical conclusion does the author draw?",
          "Students should avoid sleep before an exam",
          "Sleep is irrelevant to exam performance",
          "Only emotional memories benefit from sleep",
          "Cutting sleep short to cram for an exam is likely to backfire", "D",
          "The closing sentence states that cutting sleep short to cram 'is likely to be "
          "counter-productive'.", "Medium"),
     ]),

    ("QR", "Tables, Charts & Data",
     "Physiotherapy Clinic Referrals",
     "A physiotherapy clinic recorded the number of new patients referred each quarter during one year, "
     "together with the average number of sessions each patient attended:\n\n"
     "| Quarter | New patients | Avg. sessions per patient |\n"
     "|---|---|---|\n"
     "| Q1 | 120 | 6 |\n"
     "| Q2 | 150 | 5 |\n"
     "| Q3 | 90 | 8 |\n"
     "| Q4 | 140 | 5 |\n\n"
     "Each session is billed at a flat rate of £40. Use the table to answer the questions.",
     [
         ("How many new patients were referred to the clinic over the whole year?",
          "480", "400", "500", "520", "620", "C",
          "120 + 150 + 90 + 140 = 500 patients.", "Easy"),
         ("What was the total number of sessions delivered to Q3 patients?",
          "720", "450", "640", "900", "810", "A",
          "90 patients × 8 sessions each = 720 sessions.", "Medium"),
         ("What was the total billing revenue from Q1 patients, at £40 per session?",
          "£4,800", "£28,800", "£19,200", "£30,000", "£24,000", "B",
          "Q1 sessions = 120 × 6 = 720; revenue = 720 × £40 = £28,800.", "Medium"),
         ("Across the whole year, what was the mean number of sessions attended per patient, "
          "to one decimal place?",
          "6.0", "5.8", "5.5", "6.2", "5.9", "B",
          "Total sessions = 720 + 750 + 720 + 700 = 2,890; total patients = 500; "
          "2,890 ÷ 500 = 5.78 ≈ 5.8 sessions per patient. (Note: this is not the mean of the four "
          "quarterly averages, because the quarters have different patient numbers.)", "Hard"),
     ]),

    ("QR", "Ratios & Proportion",
     "Preparing an Intravenous Dose",
     "A hospital pharmacy prepares an intravenous drug. The stock solution has a standard concentration of "
     "5 milligrams of drug per millilitre (5 mg/mL). A patient weighing 70 kg is prescribed a single dose "
     "of 2 mg of the drug per kilogram of body weight. The prepared dose is then diluted and infused at a "
     "constant rate over 30 minutes.",
     [
         ("What total mass of the drug should the 70 kg patient receive?",
          "140 mg", "350 mg", "70 mg", "35 mg", "210 mg", "A",
          "70 kg × 2 mg/kg = 140 mg.", "Easy"),
         ("What volume of the 5 mg/mL stock solution contains this dose?",
          "14 mL", "28 mL", "700 mL", "2.8 mL", "35 mL", "B",
          "140 mg ÷ 5 mg/mL = 28 mL.", "Medium"),
         ("Infused over 30 minutes, what is the average rate of drug delivery in mg per minute?",
          "2.3 mg/min", "9.3 mg/min", "4.7 mg/min", "70 mg/min", "14 mg/min", "C",
          "140 mg ÷ 30 min ≈ 4.7 mg/min.", "Medium"),
         ("A second patient weighs 85 kg and is prescribed the same 2 mg/kg dose. What volume of the "
          "same stock solution is needed for this patient's dose?",
          "30 mL", "34 mL", "17 mL", "42.5 mL", "170 mL", "B",
          "85 kg × 2 mg/kg = 170 mg; 170 mg ÷ 5 mg/mL = 34 mL.", "Hard"),
     ]),

    ("VR", "Reading for the Main Idea",
     "The Antikythera Mechanism",
     "In 1901, sponge divers exploring a shipwreck off the Greek island of Antikythera recovered, among "
     "bronze and marble statues, a corroded lump of metal that would puzzle scholars for a century. X-ray "
     "and later CT imaging revealed that the lump contained at least thirty interlocking bronze "
     "gearwheels, some with teeth barely a millimetre apart. The device, now dated to roughly the second "
     "century BCE, is generally regarded as an astronomical calculator: by turning a handle, a user could "
     "model the motions of the Sun and Moon, predict eclipses, and track the four-year cycle of the "
     "ancient Olympic Games. Nothing of comparable mechanical complexity is known from the following "
     "thousand years; clockwork of similar sophistication does not reappear in the surviving record until "
     "medieval Europe. Precisely who built the mechanism, and whether it was a unique object or one of "
     "many, is unknown. Inscriptions on its surface, only partly legible, suggest it may have originated "
     "in the Greek scientific tradition associated with figures such as Archimedes, though no direct link "
     "has been proven. What is clear is that it overturns a once-common assumption that the ancient "
     "Greeks, for all their achievements in mathematics and astronomy, did not translate their "
     "theoretical knowledge into precision machinery.",
     [
         ("Which of the following best expresses the main point the author draws from the mechanism?",
          "The ancient Greeks could turn advanced theoretical knowledge into precision machinery, "
          "contrary to a former assumption",
          "The mechanism was certainly built by Archimedes",
          "Greek astronomy was more accurate than medieval astronomy",
          "Sponge divers frequently recovered complex machines from shipwrecks", "A",
          "The closing sentence states the mechanism 'overturns a once-common assumption' that the Greeks "
          "did not build precision machinery. B is unproven in the text; C is never claimed; D is "
          "unsupported.", "Medium"),
         ("According to the passage, the mechanism could be used to:",
          "predict eclipses and track the Olympic cycle",
          "measure the temperature of seawater",
          "calculate a ship's position at sea",
          "print astronomical tables", "A",
          "The passage says a user could 'predict eclipses, and track the four-year cycle of the ancient "
          "Olympic Games'. The other uses are never mentioned.", "Medium"),
         ("Which statement about the Antikythera mechanism is best supported by the passage?",
          "No device of comparable mechanical complexity is known from the thousand years after it",
          "The inscriptions on the mechanism have now been fully translated",
          "Many identical mechanisms have since been discovered",
          "The mechanism was manufactured in medieval Europe", "A",
          "The text says 'nothing of comparable mechanical complexity is known from the following thousand "
          "years'. The inscriptions are 'only partly legible'; whether it was 'one of many, is unknown'; "
          "and it is dated to the second century BCE.", "Hard"),
         ("The author's attitude towards the claim that Archimedes built the mechanism is best described "
          "as:",
          "cautious — it is offered as a possibility that has not been proven",
          "certain that Archimedes built it",
          "dismissive of any Greek origin",
          "convinced that it is medieval", "A",
          "The passage says it 'may have originated' in a tradition linked to Archimedes 'though no direct "
          "link has been proven' — a deliberately cautious framing.", "Medium"),
     ]),

    ("VR", "True / False / Can't Tell",
     "Urban Foxes",
     "Red foxes have colonised many British cities over the past century, and urban populations now live "
     "at higher densities than their rural counterparts. City foxes are not, as is sometimes assumed, a "
     "separate species; they are the same animal that lives in the countryside, exploiting a different set "
     "of resources. Studies fitting foxes with GPS collars have found that a typical urban fox holds a "
     "territory of well under a square kilometre, far smaller than a rural territory, because food — much "
     "of it discarded by people — is so concentrated. Contrary to popular belief, the animals are not "
     "primarily scavengers of bins: analyses of their diet show that earthworms, insects, fruit and small "
     "mammals still make up a large share of what they eat. Foxes are wary of humans and attacks on people "
     "are very rare, although foxes will investigate gardens and can be bold when food is left out for "
     "them. Numbers are thought to be limited less by human control efforts, which studies suggest have "
     "little lasting effect on population size, than by the availability of territory and outbreaks of "
     "disease such as mange. Councils that have tried to cull urban foxes have generally found that "
     "vacated territories are quickly reoccupied by foxes from surrounding areas.",
     [
         ("Statement: Urban foxes are a different species from rural foxes. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "B",
          "The passage states city foxes are 'not ... a separate species' — the statement is contradicted, "
          "making it False.", "Medium"),
         ("Statement: A typical urban fox's territory is smaller than a rural fox's. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "A",
          "Stated directly: an urban territory is 'far smaller than a rural territory'.", "Easy"),
         ("Statement: Culling has proven an effective long-term way of reducing urban fox numbers. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "B",
          "The passage says control efforts have 'little lasting effect' and vacated territories are "
          "'quickly reoccupied' — the statement is contradicted, making it False.", "Medium"),
         ("Statement: Urban foxes carry more diseases than rural foxes. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "C",
          "The passage mentions disease (mange) as one factor limiting numbers but never compares disease "
          "rates between urban and rural foxes, so there isn't enough information — Can't tell.", "Hard"),
     ]),

    ("QR", "Tables, Charts & Data",
     "Café Weekly Takings",
     "A café records its takings (in £) from three product lines over one week:\n\n"
     "| Day | Coffee | Pastries | Sandwiches |\n"
     "|---|---|---|---|\n"
     "| Mon | 180 | 90 | 120 |\n"
     "| Tue | 200 | 110 | 140 |\n"
     "| Wed | 160 | 80 | 130 |\n"
     "| Thu | 220 | 120 | 150 |\n"
     "| Fri | 300 | 160 | 210 |\n\n"
     "Use the table to answer the questions.",
     [
         ("What were the café's total takings from coffee over the week?",
          "£1,060", "£980", "£1,120", "£1,000", "£940", "A",
          "180 + 200 + 160 + 220 + 300 = £1,060.", "Easy"),
         ("On which day were the combined takings from all three lines highest?",
          "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "E",
          "Daily totals: Mon 390, Tue 450, Wed 370, Thu 490, Fri 670. Friday is highest.", "Medium"),
         ("Pastries made up what percentage of Friday's total takings, to the nearest whole number?",
          "24%", "20%", "27%", "16%", "30%", "A",
          "Friday pastries £160 out of a £670 total: 160 ÷ 670 = 23.9% ≈ 24%.", "Hard"),
         ("By what percentage did coffee takings rise from Wednesday to Friday?",
          "87.5%", "140%", "46.7%", "75%", "112.5%", "A",
          "Rise = 300 − 160 = 140 on a base of 160: 140 ÷ 160 = 0.875 = 87.5%. (46.7% wrongly divides by "
          "the new figure, 300.)", "Hard"),
     ]),

    ("QR", "Speed, Distance & Time",
     "A Week of Training Runs",
     "A runner preparing for a race trains on four days in one week. Her distances and times are:\n\n"
     "| Day | Distance (km) | Time |\n"
     "|---|---|---|\n"
     "| Tue | 8 | 48 min |\n"
     "| Thu | 10 | 55 min |\n"
     "| Sat | 21 | 2 h 6 min |\n"
     "| Sun | 6 | 33 min |\n\n"
     "Use the table to answer the questions.",
     [
         ("What total distance did she run during the week?",
          "45 km", "44 km", "46 km", "39 km", "51 km", "A",
          "8 + 10 + 21 + 6 = 45 km.", "Easy"),
         ("What was her average speed on Tuesday, in km/h?",
          "10", "9.6", "12", "8", "6.7", "A",
          "8 km in 48 min = 8 ÷ (48/60) = 8 ÷ 0.8 = 10 km/h.", "Medium"),
         ("On the Saturday run, what was her average pace in minutes per kilometre?",
          "6 min/km", "5 min/km", "6.3 min/km", "7 min/km", "5.5 min/km", "A",
          "2 h 6 min = 126 min over 21 km: 126 ÷ 21 = 6 minutes per kilometre.", "Medium"),
         ("If she held her Thursday speed for a full 42.2 km marathon, how long would it take, to the "
          "nearest minute?",
          "232 min", "220 min", "240 min", "210 min", "255 min", "A",
          "Thursday pace = 55 min ÷ 10 km = 5.5 min/km; 42.2 × 5.5 = 232.1 ≈ 232 min (about 3 h 52 min).",
          "Hard"),
     ]),

    ("SJT", "Appropriateness Ratings",
     "A Colleague Who Smells of Alcohol",
     "Rajiv, a first-year medical student, is on a ward placement, shadowing a junior doctor for the "
     "shift. He notices that the doctor smells strongly of alcohol and is slurring slightly as she "
     "prepares to review a patient's medication. Rate the appropriateness of each of the following "
     "responses by Rajiv, taking each in turn.",
     [
         ("How appropriate is it for Rajiv to raise his concern promptly and discreetly with the "
          "supervising senior doctor or the nurse in charge?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not ideal", "A very inappropriate thing to do", "A",
          "Patient safety comes first. Raising the concern promptly with someone senior, and doing so "
          "discreetly, is exactly the professional response the GMC expects.", "Medium"),
         ("How appropriate is it for Rajiv to say nothing and continue the placement as planned?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not ideal", "A very inappropriate thing to do", "D",
          "Staying silent leaves patients exposed to a foreseeable risk of harm. Failing to act on a clear "
          "patient-safety concern is very inappropriate.", "Medium"),
         ("How appropriate is it for Rajiv to confront the doctor loudly about being drunk in front of "
          "waiting patients?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not ideal", "A very inappropriate thing to do", "C",
          "Flagging the concern is right, but doing it publicly humiliates the colleague and breaches "
          "professionalism and patient dignity — the right instinct carried out in the wrong way.", "Hard"),
         ("How appropriate is it for Rajiv to offer to carry out the patient's medication review himself "
          "so the patient is not affected?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not ideal", "A very inappropriate thing to do", "D",
          "A first-year student is not competent to perform a medication review unsupervised; acting "
          "beyond his competence creates a new patient-safety risk. Very inappropriate.", "Hard"),
     ]),

    ("SJT", "Importance Ratings",
     "A Confidentiality Breach on Social Media",
     "A patient tells Sara, a medical student, that she has seen a photograph on social media, posted by a "
     "member of the clinical team, in which a patient's chart is visible. Sara is deciding how to respond. "
     "Rate how important each of the following considerations is in deciding what she should do.",
     [
         ("How important is it for Sara to consider whether the post breaches patient confidentiality?",
          "Very important", "Important", "Of minor importance", "Not important at all", "A",
          "Confidentiality is a core professional duty. Whether the post breaches it goes to the heart of "
          "the problem, so it is very important.", "Medium"),
         ("How important is it for Sara to consider whether the team member is a personal friend of hers?",
          "Very important", "Important", "Of minor importance", "Not important at all", "D",
          "A personal friendship should not affect a professional duty to protect patients. This "
          "consideration is not important at all.", "Medium"),
         ("How important is it for Sara to consider whether the patient in the photograph could be "
          "identified by others?",
          "Very important", "Important", "Of minor importance", "Not important at all", "B",
          "Identifiability affects how serious the breach is and how urgently it must be handled, so it is "
          "an important — though not the single decisive — consideration.", "Hard"),
         ("How important is it for Sara to consider whether she has a duty to raise the concern even "
          "though she is only a student?",
          "Very important", "Important", "Of minor importance", "Not important at all", "A",
          "The duty to protect patients and to raise concerns applies to students too; recognising that "
          "duty is very important to deciding she should act.", "Hard"),
     ]),

    ("VR", "True / False / Can't Tell",
     "The Domestication of the Horse",
     "Genetic and archaeological evidence increasingly points to the western Eurasian steppe, in the "
     "region of modern Kazakhstan, as the area where horses were first domesticated, sometime around "
     "3500 BCE. Early domestication is thought to have been for meat and milk rather than for riding, "
     "since the skeletal changes associated with sustained riding — wear patterns on the teeth from a "
     "bit, and changes to the spine from a rider's weight — appear later in the archaeological record "
     "than the earliest signs of human management. Genetic studies of modern horses show remarkably low "
     "diversity in the chromosome inherited only through the male line, suggesting that a small number of "
     "stallions, prized for particular traits, were used to sire the vast majority of domestic horses "
     "across many later populations, even as the mitochondrial DNA passed down the female line remains "
     "highly diverse. This pattern implies that many wild mares from different regions were incorporated "
     "into domestic herds over time, while stallions were far more tightly selected. The domestication of "
     "the horse transformed warfare, transport and agriculture across Eurasia, allowing armies, traders "
     "and herders to travel distances and speeds that would previously have been impossible. Some "
     "researchers caution, however, that a single steppe origin does not preclude horses being "
     "independently tamed, on a smaller and less lasting scale, in other regions before or after the "
     "steppe domestication took hold.",
     [
         ("Statement: The earliest domesticated horses were used mainly for riding. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "B",
          "The passage says early domestication 'was for meat and milk rather than for riding' — the "
          "statement is contradicted, making it False.", "Easy"),
         ("Statement: The chromosome inherited only through the male line shows low genetic diversity in "
          "modern domestic horses. Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "A",
          "This is stated directly: 'remarkably low diversity in the chromosome inherited only through "
          "the male line'.", "Easy"),
         ("Which statement is best supported by the passage on horse domestication?",
          "All domestic horses today are directly descended from wild herds independently tamed on every "
          "continent",
          "Riding-related skeletal changes appear earlier in the record than the earliest signs of human "
          "management",
          "A relatively small number of stallions contributed disproportionately to later domestic horse "
          "populations",
          "Mitochondrial DNA passed down the female line shows very low diversity", "C",
          "The passage says a small number of prized stallions sired 'the vast majority of domestic "
          "horses'. A overreaches; B reverses the stated order (riding changes appear later); and D "
          "contradicts the passage, which says female-line DNA 'remains highly diverse'.", "Medium"),
         ("Statement: Horses were definitely tamed independently, outside the steppe region, at some "
          "point before or after 3500 BCE. Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "C",
          "The passage says this possibility is not 'precluded' by the single-origin evidence — a caution "
          "about interpretation, not a confirmed fact. Whether it actually happened is never stated, so "
          "there isn't enough information to judge — Can't tell.", "Hard"),
     ]),

    ("VR", "Inference & Author Tone",
     "Confirmation Bias in Clinical Diagnosis",
     "Confirmation bias — the tendency to notice and weigh evidence that supports a belief already held, "
     "while discounting evidence that contradicts it — has been repeatedly identified as a contributor to "
     "diagnostic error in medicine. A clinician who forms an early impression of a patient's condition may "
     "unconsciously seek out findings consistent with that impression and interpret ambiguous signs in its "
     "favour, while overlooking details that would point elsewhere. This tendency is thought to be "
     "reinforced by time pressure, since a fuller, more even-handed review of every possible diagnosis "
     "takes longer than confirming a hypothesis that already feels plausible. Studies asking clinicians to "
     "diagnose written case vignettes have found that providing an initial, plausible-but-wrong suggestion "
     "— for instance, a preceding clinician's tentative diagnosis — measurably reduces the rate at which "
     "the correct diagnosis is subsequently reached, even though participants were free to disregard the "
     "suggestion entirely. Proposed remedies include structured checklists that prompt a clinician to "
     "actively consider alternative diagnoses before settling on one, and deliberately seeking a "
     "colleague's independent opinion before it can be anchored by an existing suggestion. Critics of "
     "these remedies note that checklists and second opinions take time that busy clinical services often "
     "do not have, and that experienced clinicians perform this checking intuitively without a formal "
     "tool — though evidence for this claim of automatic self-correction is described in the literature "
     "as mixed at best.",
     [
         ("Which of the following best expresses the main idea of the passage on confirmation bias in "
          "clinical diagnosis?",
          "Confirmation bias is entirely eliminated by clinical experience",
          "Confirmation bias contributes to diagnostic error, and while structured remedies exist, they "
          "carry real practical costs",
          "Checklists have been proven to have no effect on diagnostic accuracy",
          "Time pressure has no relationship to diagnostic error", "B",
          "The passage links confirmation bias to diagnostic error and describes remedies (checklists, "
          "second opinions) alongside their practical costs (time). A and D are directly contradicted; C "
          "is never claimed.", "Medium"),
         ("Statement: Time pressure has been shown to have no effect on diagnostic error. "
          "Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "B",
          "The passage says confirmation bias's contribution to error 'is thought to be reinforced by "
          "time pressure' — the statement is contradicted, making it False.", "Easy"),
         ("How does the author characterise the evidence that experienced clinicians correct for "
          "confirmation bias automatically, without a formal tool?",
          "Overwhelmingly strong", "Completely absent", "Universally accepted by researchers",
          "Mixed at best — not strongly supported", "D",
          "The passage states this evidence 'is described in the literature as mixed at best'.", "Medium"),
         ("Which conclusion is best supported by the passage?",
          "Time pressure may discourage clinicians from fully reviewing alternative diagnoses",
          "Checklists are always faster than intuitive judgement",
          "All diagnostic errors stem from confirmation bias",
          "Second opinions are never influenced by a prior suggestion", "A",
          "The passage says a fuller review 'takes longer' than confirming a plausible hypothesis under "
          "time pressure. B is contradicted (checklists take time); C and D overreach beyond what the "
          "passage supports.", "Hard"),
     ]),

    ("VR", "Reading for the Main Idea",
     "The Discovery of Penicillin",
     "In 1928, Alexander Fleming returned to his London laboratory after a summer holiday to find that "
     "one of the culture plates he had left out, intended to grow the bacterium Staphylococcus, had "
     "become contaminated with a mould. Around the mould, the bacteria had failed to grow, leaving a "
     "clear ring in an otherwise cloudy plate. Fleming identified the mould as a Penicillium species and "
     "published his observation, noting the antibacterial substance's potential, which he termed "
     "penicillin. He struggled, however, to purify or produce the substance in usable quantities, and for "
     "over a decade the discovery remained a laboratory curiosity rather than a treatment. It was not "
     "until the late 1930s that a team at Oxford, led by Howard Florey and Ernst Chain, developed methods "
     "to extract and concentrate penicillin and to test it systematically in animals and then in a small "
     "number of human patients. Wartime demand accelerated the search for mass-production methods, and "
     "pharmaceutical manufacturing techniques developed largely in the United States allowed penicillin "
     "to be produced at a scale sufficient to treat large numbers of Allied soldiers by the mid-1940s. "
     "Fleming, Florey and Chain shared the 1945 Nobel Prize in Physiology or Medicine for the discovery. "
     "Popular accounts sometimes credit Fleming alone with penicillin's success as a medicine, but the "
     "passage's evidence suggests that his initial observation, though essential, was only the first of "
     "several steps — each requiring different expertise — that were necessary before penicillin could "
     "save lives.",
     [
         ("Which of the following best expresses the main idea of the passage on the discovery of "
          "penicillin?",
          "Fleming alone was responsible for penicillin becoming a usable medicine",
          "Penicillin was never successfully mass-produced",
          "Turning Fleming's initial observation into a usable medicine required further, separate "
          "contributions from other researchers",
          "Florey and Chain discovered penicillin independently of Fleming, before his 1928 observation",
          "C",
          "The closing sentence states Fleming's observation 'was only the first of several steps ... "
          "necessary before penicillin could save lives'. A is contradicted; B is contradicted by the "
          "account of wartime mass production; D reverses the actual chronology.", "Medium"),
         ("Statement: Fleming was the first person anywhere to notice that a mould could inhibit "
          "bacterial growth. Based only on the passage, this statement is:",
          "True", "False", "Can't tell", "", "C",
          "The passage describes Fleming's own observation and its consequences but never claims he was "
          "the first person ever, anywhere, to notice such an effect — there isn't enough information to "
          "judge that broader claim. Can't tell.", "Hard"),
         ("According to the passage, what accelerated the development of methods to mass-produce "
          "penicillin?",
          "Wartime demand", "A shortage of Penicillium mould", "Fleming's personal request",
          "A decline in bacterial infections", "A",
          "Stated directly: 'wartime demand accelerated the search for mass-production methods'.",
          "Easy"),
         ("The author's attitude towards the popular account crediting Fleming alone is best described "
          "as:",
          "Fully in agreement", "Indifferent", "Unaware such accounts exist",
          "Sceptical — the passage's evidence suggests this account is incomplete", "D",
          "The final sentence explicitly frames the 'Fleming alone' account against evidence that further, "
          "separate contributions were 'necessary' — a sceptical framing of the popular version.",
          "Medium"),
     ]),

    ("QR", "Tables, Charts & Data",
     "Hospital Bed Occupancy",
     "A hospital records the total and occupied beds on four wards:\n\n"
     "| Ward | Total beds | Occupied beds |\n"
     "|---|---|---|\n"
     "| A | 40 | 34 |\n"
     "| B | 25 | 20 |\n"
     "| C | 60 | 51 |\n"
     "| D | 30 | 18 |\n\n"
     "Use the table to answer the questions.",
     [
         ("What percentage of Ward C's beds are occupied?",
          "80%", "90%", "85%", "75%", "82%", "C",
          "51 ÷ 60 = 0.85 = 85%.", "Easy"),
         ("How many beds in total are unoccupied across all four wards?",
          "32", "30", "28", "35", "26", "A",
          "Total beds = 40+25+60+30 = 155; occupied = 34+20+51+18 = 123; unoccupied = 155 − 123 = 32.",
          "Medium"),
         ("Which ward has the lowest occupancy rate (occupied ÷ total)?",
          "Ward A", "Ward B", "Ward C", "Ward D", "They are all equal", "D",
          "Rates: A 34/40=85%, B 20/25=80%, C 51/60=85%, D 18/30=60%. Ward D is lowest.", "Medium"),
         ("If Ward D's occupied beds increase by 50%, how many beds will be occupied, and will this "
          "exceed Ward D's total capacity of 30?",
          "24 beds; within capacity", "27 beds; still within capacity", "27 beds; exceeds capacity",
          "30 beds; exactly at capacity", "9 beds; within capacity", "B",
          "18 × 1.5 = 27 beds, which is still below Ward D's 30-bed capacity.", "Hard"),
     ]),

    ("QR", "Ratios & Proportion",
     "A Pharmacy Stock Take",
     "A pharmacy dilutes a 20% stock saline solution with water in the ratio 3:2 (stock:water) to produce "
     "its standard working solution.",
     [
         ("What is the concentration of the working solution?",
          "15%", "12%", "10%", "8%", "6%", "B",
          "The stock makes up 3/5 of the mixture, so concentration = 20% × 3/5 = 12%.", "Medium"),
         ("To produce 20 litres of the working solution, how many litres of the 20% stock solution are "
          "needed?",
          "15", "10", "8", "12", "6", "D",
          "Stock is 3/5 of the mixture: 3/5 × 20 = 12 litres.", "Medium"),
         ("The pharmacy has only 9 litres of stock solution left. What is the maximum volume of working "
          "solution it can produce, keeping the 3:2 ratio?",
          "15", "18", "12", "9", "21", "A",
          "9 litres of stock is 3 parts, so 1 part = 3 litres; water = 2 × 3 = 6 litres; "
          "total = 9 + 6 = 15 litres.", "Hard"),
         ("If the ratio were changed to 2:3 (stock:water) instead, what would the new concentration be?",
          "10%", "12%", "8%", "6%", "5%", "C",
          "Stock is now 2/5 of the mixture: 20% × 2/5 = 8%.", "Medium"),
     ]),

    ("QR", "Speed, Distance & Time",
     "Marathon Split Times",
     "A runner completes a 42.2 km marathon with the following splits:\n\n"
     "| Segment | Distance | Time |\n"
     "|---|---|---|\n"
     "| 0–10 km | 10.0 km | 42 min |\n"
     "| 10–21.1 km | 11.1 km | 48 min |\n"
     "| 21.1–32 km | 10.9 km | 50 min |\n"
     "| 32–42.2 km | 10.1 km | 55 min |\n\n"
     "Use the table to answer the questions.",
     [
         ("What was the runner's total marathon time?",
          "3 h 15 min", "3 h 05 min", "3 h 25 min", "3 h 10 min", "3 h 20 min", "A",
          "42 + 48 + 50 + 55 = 195 minutes = 3 h 15 min.", "Easy"),
         ("What was the average pace, in minutes per kilometre, for the 10–21.1 km segment?",
          "~4.0 min/km", "~3.9 min/km", "~4.3 min/km", "~4.8 min/km", "~5.0 min/km", "C",
          "48 min ÷ 11.1 km ≈ 4.3 min/km.", "Medium"),
         ("What was the runner's average speed, in km/h, over the whole marathon?",
          "12.0", "11.5", "14.0", "13.5", "13.0", "E",
          "195 min = 3.25 h; 42.2 ÷ 3.25 ≈ 13.0 km/h.", "Hard"),
         ("Which segment had the fastest average pace (lowest minutes per kilometre)?",
          "32–42.2 km", "0–10 km", "21.1–32 km", "10–21.1 km", "All segments were equally fast", "B",
          "Paces: 0–10 km = 4.2 min/km, 10–21.1 km ≈ 4.3, 21.1–32 km ≈ 4.6, 32–42.2 km ≈ 5.4. The first "
          "segment is fastest.", "Medium"),
     ]),

    ("QR", "Tables, Charts & Data",
     "University Applications",
     "A university records applications, offers made, and places filled over four admissions cycles:\n\n"
     "| Year | Applications | Offers made | Places filled |\n"
     "|---|---|---|---|\n"
     "| 2021 | 800 | 200 | 180 |\n"
     "| 2022 | 900 | 220 | 200 |\n"
     "| 2023 | 1000 | 250 | 210 |\n"
     "| 2024 | 1100 | 260 | 230 |\n\n"
     "Use the table to answer the questions.",
     [
         ("What was the offer rate (offers ÷ applications) in 2023?",
          "20%", "22%", "28%", "25%", "24%", "D",
          "250 ÷ 1000 = 25%.", "Easy"),
         ("In which year was the ratio of places filled to offers made highest?",
          "2021", "2022", "2023", "2024", "Equal in all years", "B",
          "Ratios: 2021 180/200=0.900, 2022 200/220≈0.909, 2023 210/250=0.840, 2024 230/260≈0.885. "
          "2022 is highest.", "Hard"),
         ("Between 2021 and 2024, by what percentage did the number of applications increase?",
          "37.5%", "30%", "35%", "40%", "33.3%", "A",
          "(1100 − 800) ÷ 800 = 300 ÷ 800 = 37.5%.", "Medium"),
         ("What was the mean number of offers made per year across all four years?",
          "230", "225", "232.5", "235", "240", "C",
          "(200+220+250+260) ÷ 4 = 930 ÷ 4 = 232.5.", "Medium"),
     ]),

    ("QR", "Ratios & Proportion",
     "Currency Conversion for a Medical Elective",
     "A student budgets for a medical elective abroad. The exchange rate is £1 = $1.25. A hotel costs "
     "$150 per night; a flight costs £600.",
     [
         ("What is the cost of one night's hotel stay in £?",
          "£125.00", "£115.00", "£135.00", "£120.00", "£187.50", "D",
          "$150 ÷ 1.25 = £120.00.", "Easy"),
         ("What is the total cost in £ of a 7-night hotel stay plus the flight?",
          "£1,440", "£1,410", "£1,470", "£1,350", "£1,500", "A",
          "7 × £120 = £840; £840 + £600 = £1,440.", "Medium"),
         ("If the exchange rate changes to £1 = $1.20, how much more in £ would the same $150-per-night "
          "hotel cost, compared with the original rate?",
          "£3.75", "£5.00", "£6.25", "£2.50", "£4.50", "B",
          "At the new rate: $150 ÷ 1.20 = £125.00; £125.00 − £120.00 = £5.00 more.", "Hard"),
         ("The student has a total budget of £2,000 for the hotel and flight only. At the original "
          "exchange rate, what is the maximum number of full nights they can afford after paying for the "
          "flight?",
          "10", "12", "9", "13", "11", "E",
          "£2,000 − £600 (flight) = £1,400 remaining; £1,400 ÷ £120 ≈ 11.67, so 11 full nights.", "Hard"),
     ]),

    ("SJT", "Appropriateness Ratings",
     "A Missed Consent Discussion",
     "Tom, a medical student, is observing a surgical consent conversation. He notices that the surgeon "
     "does not mention a recognised, moderately common risk of the procedure before the patient signs the "
     "consent form. The patient later asks Tom, privately, whether there are any risks the surgeon didn't "
     "mention. Rate the appropriateness of each of the following responses by Tom.",
     [
         ("How appropriate is it for Tom to tell the patient he cannot discuss the risks himself, and to "
          "suggest she ask the surgeon or another member of the clinical team directly?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "This keeps Tom within his competence as a student while making sure the patient's question "
          "reaches someone able to answer it accurately — a very appropriate response.", "Medium"),
         ("How appropriate is it for Tom to tell the patient the specific risk he noticed was omitted, "
          "based on his own knowledge?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "C",
          "Disclosing risks is not a student's role, and a better channel exists (the clinical team); but "
          "sharing a genuine, relevant concern is not itself dishonest or unsafe, so this is inappropriate "
          "without being the worst response.", "Hard"),
         ("How appropriate is it for Tom to raise the omission promptly and privately with the surgeon or "
          "another senior member of the team after the conversation?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "Raising a patient-safety and informed-consent concern promptly and discreetly with someone "
          "senior is exactly the professional response expected.", "Medium"),
         ("How appropriate is it for Tom to say nothing to anyone, assuming the surgeon must have had a "
          "good reason to omit the risk?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "D",
          "Assuming a good reason without checking leaves a possible informed-consent gap unaddressed — a "
          "very inappropriate response given patient safety is at stake.", "Hard"),
     ]),

    ("SJT", "Importance Ratings",
     "A Struggling Colleague",
     "Amara, a final-year medical student, notices that a fellow student on her placement, Chidi, has "
     "seemed exhausted and has made two small but noticeable errors in patient notes over the past week. "
     "Chidi confides that he has been struggling to sleep because of a family bereavement, and asks Amara "
     "to keep it private. Amara is deciding whether and how to raise this. Rate how important each of the "
     "following considerations is to her decision.",
     [
         ("How important is it for Amara to consider whether Chidi's errors could affect patient safety "
          "if they continue unaddressed?",
          "Very important", "Important", "Of minor importance", "Not important at all", "A",
          "Patient safety is paramount and directly at stake if tired-related errors continue.", "Medium"),
         ("How important is it for Amara to consider that Chidi asked her, as a friend, to keep the "
          "bereavement private?",
          "Very important", "Important", "Of minor importance", "Not important at all", "B",
          "Respecting a colleague's trust and privacy matters, but it cannot override a genuine patient "
          "safety concern — important, though not the overriding factor.", "Hard"),
         ("How important is it for Amara to consider encouraging Chidi to speak to a supervisor or "
          "student support service himself, rather than her reporting on his behalf?",
          "Very important", "Important", "Of minor importance", "Not important at all", "A",
          "Supporting a colleague to seek help himself respects his autonomy while still addressing the "
          "safety concern — a strongly preferred first step.", "Medium"),
         ("How important is it for Amara to consider whether she personally likes Chidi?",
          "Very important", "Important", "Of minor importance", "Not important at all", "D",
          "Personal feelings toward a colleague are irrelevant to a professional judgement about patient "
          "safety and support.", "Easy"),
     ]),

    ("SJT", "Appropriateness Ratings",
     "Overheard Ward Gossip",
     "Priya, a medical student, overhears two healthcare assistants discussing a patient's HIV status by "
     "name in the hospital canteen, within earshot of other diners. Priya does not know either assistant "
     "well. Rate the appropriateness of each of the following responses by Priya.",
     [
         ("How appropriate is it for Priya to politely point out, in the moment, that the conversation "
          "risks breaching the patient's confidentiality?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "A prompt, polite reminder addresses the breach immediately and is well within any student's "
          "responsibility to protect patient confidentiality.", "Medium"),
         ("How appropriate is it for Priya to say nothing at the time, but later mention it to her "
          "supervisor so the assistants' team can be made aware of the confidentiality concern?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "B",
          "Raising it afterwards still addresses the concern, but a prompt in-the-moment reminder would "
          "have been more effective at limiting the breach as it happened.", "Medium"),
         ("How appropriate is it for Priya to repeat what she heard to a friend later that day, as an "
          "interesting story?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "D",
          "Repeating identifiable patient information further breaches confidentiality with no "
          "professional justification — very inappropriate.", "Medium"),
         ("How appropriate is it for Priya to ignore the conversation, reasoning that it is not her "
          "patient and not her responsibility?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "C",
          "Every member of a healthcare team shares responsibility for protecting patient confidentiality; "
          "ignoring a clear breach is inappropriate, though it does not itself cause further harm the way "
          "actively repeating the information would.", "Hard"),
     ]),

    ("SJT", "Appropriateness Ratings",
     "A Senior's Error Left Uncorrected",
     "James, a final-year student, witnesses a consultant prescribe a medication at a dose well above the "
     "safe maximum. A senior nurse notices too, but is told by the consultant, dismissively, to \"just give "
     "it, I know what I'm doing.\" The nurse administers the dose without further comment. Rate the "
     "appropriateness of each of the following responses by James.",
     [
         ("How appropriate is it for James to raise the concern directly and immediately with the "
          "consultant, clearly stating the dose appears to exceed the safe maximum?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "Patient safety is at immediate risk; raising the specific, factual concern right away is "
          "exactly the expected response, regardless of the consultant's seniority.", "Medium"),
         ("How appropriate is it for James to say nothing, assuming that since the nurse also noticed and "
          "administered it anyway, the dose must actually be safe?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "D",
          "Deferring silently to authority despite a clear, specific safety concern — especially when the "
          "nurse's compliance may reflect the same pressure James is feeling — leaves the patient at risk. "
          "Very inappropriate.", "Hard"),
         ("How appropriate is it for James to check the dose against a reliable reference (e.g. the "
          "British National Formulary) before deciding whether to raise it further?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "Verifying the concern against a trusted reference is a sensible, proportionate step that "
          "supports raising it credibly and does not delay meaningfully.", "Medium"),
         ("How appropriate is it for James, if dismissed again, to escalate the concern to another senior "
          "clinician or the ward's clinical lead promptly?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "When an immediate safety concern is dismissed, escalating to another senior without delay is "
          "the correct next step — patient safety overrides usual hierarchy.", "Medium"),
         ("How appropriate is it for James to publicly confront the consultant in front of the patient and "
          "other staff, insisting the dose be changed before he will let it be given?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "C",
          "Raising the concern is right, but a public confrontation in front of the patient risks "
          "undermining the patient's confidence in their care team and is not the most constructive way "
          "to resolve it — better handled promptly but privately or through escalation.", "Hard"),
     ]),

    ("SJT", "Importance Ratings",
     "Disagreeing With the Plan",
     "Elin, a junior doctor, believes a senior colleague's proposed discharge plan for a patient is too "
     "early given the patient's ongoing symptoms, but the senior colleague is confident and under time "
     "pressure to free up the bed. Elin is deciding whether and how to raise her concern. Rate how "
     "important each of the following considerations is to her decision.",
     [
         ("How important is it for Elin to consider whether the patient's ongoing symptoms could indicate "
          "a genuine risk if discharged now?",
          "Very important", "Important", "Of minor importance", "Not important at all", "A",
          "Patient safety is the central issue here and must be weighed above all else.", "Medium"),
         ("How important is it for Elin to consider that the senior colleague is under pressure to free "
          "up the bed?",
          "Very important", "Important", "Of minor importance", "Not important at all", "C",
          "Bed pressure is a real operational factor but should not be allowed to override a genuine "
          "safety concern — it is only of minor importance to Elin's decision.", "Medium"),
         ("How important is it for Elin to raise her clinical concern with the senior colleague clearly, "
          "even though it means disagreeing with someone more experienced?",
          "Very important", "Important", "Of minor importance", "Not important at all", "A",
          "Raising a genuine patient-safety concern is essential, regardless of the seniority gap — "
          "silence in the face of a real risk is not acceptable.", "Medium"),
     ]),

    ("SJT", "Appropriateness Ratings",
     "Pressure to Adjust the Data",
     "Marcus, a medical student on a research placement, is helping analyse data for a supervisor's study. "
     "He notices that one data point looks like it may have been altered to better fit the expected "
     "result. When he mentions it, the supervisor tells him not to worry about it and to move on. Rate the "
     "appropriateness of each of the following responses by Marcus.",
     [
         ("How appropriate is it for Marcus to ask the supervisor directly for an explanation of how that "
          "specific data point was obtained?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "Asking a direct, specific question about the data's origin is a reasonable and proportionate "
          "first step before assuming wrongdoing.", "Medium"),
         ("How appropriate is it for Marcus to drop the issue entirely, since the supervisor is more "
          "senior and told him not to worry about it?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "D",
          "Research integrity is a serious matter; dropping a genuine concern about altered data simply "
          "because a supervisor dismissed it is very inappropriate.", "Hard"),
         ("How appropriate is it for Marcus to raise the concern with the institution's research "
          "integrity or ethics office if he remains unsatisfied after speaking with the supervisor?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "Escalating a genuine, unresolved research-integrity concern through the proper institutional "
          "channel is exactly the correct next step.", "Medium"),
         ("How appropriate is it for Marcus to publicly accuse the supervisor of fraud on social media?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "D",
          "A public accusation without established proof, made outside any proper process, is unfair, "
          "reckless, and very inappropriate — concerns should be raised through legitimate channels.",
          "Medium"),
     ]),

    ("SJT", "Appropriateness Ratings",
     "A Safeguarding Concern",
     "During a paediatric placement, Fatima, a medical student, notices a child has several bruises in "
     "unusual locations that don't match the explanation given by the accompanying parent. The supervising "
     "doctor seems rushed and has not mentioned it. Rate the appropriateness of each of the following "
     "responses by Fatima.",
     [
         ("How appropriate is it for Fatima to mention her observation to the supervising doctor promptly, "
          "in a way that does not accuse the parent in front of the child?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "Raising a possible safeguarding concern promptly and discreetly with the responsible clinician "
          "is exactly the right response — child safety takes priority.", "Medium"),
         ("How appropriate is it for Fatima to say nothing, assuming the doctor must have already noticed "
          "and decided it was nothing?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "D",
          "Assuming safety has been handled, without confirming it, risks a genuine safeguarding issue "
          "going unaddressed — very inappropriate given a child may be at risk.", "Hard"),
         ("How appropriate is it for Fatima to directly question the parent about the bruises herself, on "
          "the spot?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "C",
          "As a student, directly interrogating a parent about a suspected safeguarding issue is outside "
          "her role and could compromise a proper, sensitive assessment — better raised with the clinical "
          "team first.", "Hard"),
         ("How appropriate is it for Fatima to document exactly what she observed, factually and without "
          "assumptions, for the clinical team's reference?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "Factual, non-judgemental documentation supports the clinical team's assessment and is good "
          "practice when a safeguarding concern arises.", "Medium"),
     ]),

    ("SJT", "Importance Ratings",
     "Overwhelmed and Behind",
     "Daniel, a medical student, is juggling coursework deadlines with ward responsibilities and has "
     "started to fall behind, missing a follow-up task he was asked to complete for a patient's care. He "
     "is deciding how to handle the situation. Rate how important each of the following considerations is "
     "to his decision.",
     [
         ("How important is it for Daniel to tell his supervisor promptly that the follow-up task was "
          "missed, so it can still be completed or reassigned?",
          "Very important", "Important", "Of minor importance", "Not important at all", "A",
          "Prompt disclosure ensures the patient-care gap is closed quickly — this is the priority.",
          "Medium"),
         ("How important is it for Daniel to consider that admitting the mistake might make him look "
          "less capable in front of his supervisor?",
          "Very important", "Important", "Of minor importance", "Not important at all", "D",
          "Concern for his own reputation is not a legitimate reason to delay disclosing a patient-care "
          "gap — it is not important at all to the decision.", "Medium"),
         ("How important is it for Daniel to reflect on how he is managing his overall workload, so "
          "similar gaps are less likely in future?",
          "Very important", "Important", "Of minor importance", "Not important at all", "B",
          "Reflecting on workload management is a sensible, important step for preventing recurrence, "
          "though it is secondary to fixing the immediate gap.", "Medium"),
     ]),

    ("SJT", "Appropriateness Ratings",
     "A Patient's Request for a Different Doctor",
     "A patient asks to be seen by a different doctor because of the current doctor's ethnicity, stating "
     "they would feel more comfortable with someone else. The current doctor is competent and has no "
     "clinical reason to hand over care. Rate the appropriateness of each of the following responses from "
     "the clinical team.",
     [
         ("How appropriate is it for the team to calmly explain that the request cannot be accommodated on "
          "the stated grounds, while checking whether there is a genuine clinical or communication reason "
          "behind the request?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "This addresses the discriminatory basis directly while remaining open to a legitimate "
          "underlying concern — a balanced, professional response.", "Hard"),
         ("How appropriate is it for the team to simply reassign the patient to a different doctor to "
          "avoid conflict, without addressing the reason given?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "C",
          "Accommodating a discriminatory request without comment avoids immediate friction but "
          "implicitly endorses discrimination against a colleague — inappropriate, though not the most "
          "harmful option available.", "Hard"),
         ("How appropriate is it for the team to refuse the request and directly criticise the patient for "
          "being discriminatory?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "D",
          "Confronting a patient with direct personal criticism is unprofessional and could damage the "
          "therapeutic relationship — very inappropriate, even though the underlying request is "
          "unacceptable.", "Hard"),
         ("How appropriate is it for the team to support the current doctor by making clear that patient "
          "care decisions are not made on the basis of a clinician's ethnicity, while managing the "
          "immediate situation professionally?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "Upholding the principle clearly, without discriminating against the treating doctor, while "
          "still handling the immediate encounter professionally, is exactly right.", "Medium"),
         ("How appropriate is it for the team to ignore the request entirely and proceed as though it was "
          "never made?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "C",
          "Ignoring the request avoids confrontation but leaves both the patient's underlying concern and "
          "the discriminatory basis unaddressed — inappropriate, though not actively harmful.", "Hard"),
     ]),

    ("SJT", "Appropriateness Ratings",
     "A Grateful Patient's Gift",
     "After a successful course of treatment, a patient tries to give Aisha, her student doctor, an "
     "expensive bottle of whisky as a personal thank-you gift. Rate the appropriateness of each of the "
     "following responses by Aisha.",
     [
         ("How appropriate is it for Aisha to politely decline the gift, explaining that she isn't able to "
          "accept gifts of significant value, while thanking the patient warmly for the gesture?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "This respects the patient's kind intentions while maintaining an appropriate professional "
          "boundary around gifts of significant value.", "Medium"),
         ("How appropriate is it for Aisha to accept the gift privately and not mention it to anyone?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "C",
          "Accepting a gift of significant value without transparency risks perceptions of undue "
          "influence, even where none was intended — inappropriate, though not itself dishonest or unsafe.",
          "Hard"),
         ("How appropriate is it for Aisha to accept the gift but declare it to her supervisor or through "
          "her institution's gifts policy?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "B",
          "Declaring the gift maintains transparency, though many institutions' policies would still "
          "prefer such a gift be declined rather than accepted and logged.", "Medium"),
     ]),

    ("SJT", "Importance Ratings",
     "A Regrettable Social Media Post",
     "Yusuf, a medical student, posted a photo from a night out that shows him visibly intoxicated, "
     "tagged with the name of his hospital placement. A friend points out that the post is public and "
     "could be seen by patients or supervisors. Rate how important each of the following considerations "
     "is to Yusuf's decision about what to do next.",
     [
         ("How important is it for Yusuf to consider that the post links his behaviour to his hospital "
          "placement and the medical profession?",
          "Very important", "Important", "Of minor importance", "Not important at all", "A",
          "Public association between personal conduct and a professional placement is the central "
          "concern — it can affect trust in the profession, not just Yusuf personally.", "Medium"),
         ("How important is it for Yusuf to consider removing or restricting the post promptly?",
          "Very important", "Important", "Of minor importance", "Not important at all", "A",
          "Prompt action limits any reputational or professional impact — this is a very important, "
          "practical first step.", "Easy"),
         ("How important is it for Yusuf to consider how many 'likes' the post received?",
          "Very important", "Important", "Of minor importance", "Not important at all", "D",
          "Engagement metrics are irrelevant to the professionalism concern at hand.", "Easy"),
         ("How important is it for Yusuf to consider being more mindful of what he posts publicly while "
          "he is a student on placement?",
          "Very important", "Important", "Of minor importance", "Not important at all", "B",
          "Building better judgement about public posting is a sensible, important habit going forward, "
          "though secondary to addressing this specific post.", "Medium"),
     ]),

    ("SJT", "Appropriateness Ratings",
     "Copied Coursework Data",
     "Leah, a medical student, discovers that a coursemate's submitted lab report contains data that "
     "appears identical to her own, down to identical incidental errors, suggesting it was copied rather "
     "than independently collected. Rate the appropriateness of each of the following responses by Leah.",
     [
         ("How appropriate is it for Leah to speak to the coursemate directly first, explaining what she "
          "noticed and asking for an explanation?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "Raising it directly first gives the coursemate a fair chance to explain before any formal "
          "process, which is a reasonable and proportionate first step.", "Medium"),
         ("How appropriate is it for Leah to report the concern to the course convenor if the "
          "conversation does not resolve it, or if she is not comfortable raising it directly?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "Academic integrity concerns that can't be resolved informally should be raised through the "
          "proper institutional channel — this is the correct next step.", "Medium"),
         ("How appropriate is it for Leah to say nothing at all, reasoning that it isn't her responsibility "
          "to police other students' work?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "C",
          "Academic integrity underpins trust in professional training; ignoring a clear concern is "
          "inappropriate, though it doesn't itself cause direct harm the way covering it up would.",
          "Hard"),
         ("How appropriate is it for Leah to post about the incident anonymously in a student group chat "
          "to warn others?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "D",
          "Airing an unresolved, unproven allegation publicly — even anonymously — is unfair to the "
          "coursemate and bypasses the proper process entirely. Very inappropriate.", "Hard"),
         ("How appropriate is it for Leah to keep a factual note of what she noticed and when, in case it "
          "is needed later?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "A",
          "Keeping a simple, factual record is sensible and supports a fair process if the matter is "
          "escalated.", "Medium"),
         ("How appropriate is it for Leah to change her own report's answers so they no longer match, to "
          "avoid being drawn into the situation?",
          "A very appropriate thing to do", "Appropriate, but not ideal",
          "Inappropriate, but not awful", "A very inappropriate thing to do", "D",
          "Altering her own genuine data to avoid scrutiny is itself a serious act of academic dishonesty "
          "— very inappropriate.", "Medium"),
     ]),

    ("SJT", "Importance Ratings",
     "Challenging a Senior's Behaviour",
     "Ben, a medical student, notices that a senior doctor repeatedly speaks over and dismisses a "
     "particular nurse's clinical suggestions during ward rounds, in a way Ben feels is disrespectful and "
     "may be discouraging the nurse from raising valid safety concerns in future. Rate how important each "
     "of the following considerations is to Ben's decision about what to do.",
     [
         ("How important is it for Ben to consider that discouraging the nurse from speaking up could "
          "affect future patient safety if genuine concerns go unraised?",
          "Very important", "Important", "Of minor importance", "Not important at all", "A",
          "A team culture that discourages staff from raising concerns is a direct patient-safety risk — "
          "this is the central issue.", "Medium"),
         ("How important is it for Ben to consider that the senior doctor is much more experienced than "
          "him?",
          "Very important", "Important", "Of minor importance", "Not important at all", "C",
          "Seniority affects how carefully Ben might raise the issue, but it doesn't change whether the "
          "underlying concern matters — only of minor importance to the substance of the decision.",
          "Medium"),
         ("How important is it for Ben to consider raising his observation with the senior doctor "
          "privately and respectfully, rather than during the ward round itself?",
          "Very important", "Important", "Of minor importance", "Not important at all", "A",
          "Raising a sensitive concern about a colleague's behaviour privately and respectfully is far "
          "more likely to be heard and is very important to handling this constructively.", "Medium"),
         ("How important is it for Ben to consider mentioning his observation to an educational "
          "supervisor if he doesn't feel able to raise it with the senior doctor directly?",
          "Very important", "Important", "Of minor importance", "Not important at all", "B",
          "This is a reasonable, important alternative route to ensure the concern is heard, though "
          "raising it directly first is generally preferable.", "Medium"),
     ]),
]

# standalone questions (no shared passage): (subject_code, topic_name, stem,
#   A, B, C, D, E, correct, explanation, difficulty). E may be "" when the format
#   uses four options. Used for Decision Making, which the real UCAT presents as
#   individual four-option items across several reasoning types.
_STANDALONE_QUESTIONS = [
    ("DM", "Syllogisms & Logical Deduction",
     "All members of the surgical team scrubbed in before the operation. Nurse Bello scrubbed in before "
     "the operation. Which conclusion necessarily follows?",
     "Nurse Bello is a member of the surgical team",
     "Nurse Bello is not a member of the surgical team",
     "It cannot be determined whether Nurse Bello is a member of the surgical team",
     "No members of the surgical team scrubbed in", "", "C",
     "Scrubbing in does not imply team membership — others (anaesthetists, students) also scrub in. Bello "
     "meeting the condition tells us nothing about membership, so no conclusion can be drawn. Concluding "
     "otherwise is the classic error of affirming the consequent.", "Hard"),
    ("DM", "Syllogisms & Logical Deduction",
     "No viruses are affected by antibiotics. The common cold is caused by a virus. Which conclusion "
     "necessarily follows?",
     "Antibiotics are the best treatment for the common cold",
     "The common cold is not affected by antibiotics",
     "All illnesses caused by viruses are colds",
     "Antibiotics affect some viruses", "", "B",
     "If no virus is affected by antibiotics and the cold is viral, it follows necessarily that the cold "
     "is not affected by antibiotics. The other options either contradict the premises or add unstated "
     "information.", "Medium"),
    ("DM", "Logic Puzzles & Arrangements",
     "Four doctors — P, Q, R and S — are each on call on exactly one of four consecutive nights, Monday "
     "to Thursday. P is on call the night immediately before Q. R is on call on neither Monday nor "
     "Thursday. Which one of the following must be true?",
     "P is on call on Monday",
     "R is on call on Wednesday",
     "Q is on call on either Tuesday or Thursday",
     "S is on call on Monday", "", "C",
     "Only two arrangements satisfy the clues: (Mon P, Tue Q, Wed R, Thu S) and (Mon S, Tue R, Wed P, "
     "Thu Q). Across both, Q is on Tuesday or Thursday — the only statement that must hold. Each other "
     "option is true in just one of the two arrangements.", "Hard"),
    ("DM", "Venn Diagrams & Sets",
     "In a cohort of 200 patients, 130 received drug X, 90 received drug Y, and 50 received both. How "
     "many received neither drug?",
     "30", "20", "50", "40", "", "A",
     "Received at least one = 130 + 90 − 50 = 170. Neither = 200 − 170 = 30.", "Medium"),
    ("DM", "Venn Diagrams & Sets",
     "A survey of 80 staff found that 45 cycle to work and 30 walk, with 12 doing both on different days. "
     "What fraction of the staff neither cycle nor walk to work?",
     "17/80", "13/80", "1/4", "21/80", "", "A",
     "Cycle or walk = 45 + 30 − 12 = 63. Neither = 80 − 63 = 17, i.e. 17/80 of the staff.", "Hard"),
    ("DM", "Probability & Statistics",
     "A bag contains 4 red and 6 blue counters. Two counters are drawn at random without replacement. "
     "Which one of the following statements is correct?",
     "The probability that both counters are red is 2/15",
     "The probability that both counters are red is 4/25",
     "The probability that both counters are blue is 3/5",
     "The probability of one red then one blue is 4/10 × 6/10", "", "A",
     "Without replacement, P(both red) = 4/10 × 3/9 = 12/90 = 2/15. Option B uses 'with replacement' "
     "(0.4²); C and D also ignore that the counter is not replaced, so the second draw is out of 9.",
     "Hard"),
    ("DM", "Syllogisms & Logical Deduction",
     "Should hospitals routinely offer every patient over 50 a whole-body MRI scan as a screening test? "
     "Select the strongest argument.",
     "No — whole-body scans frequently reveal harmless abnormalities that trigger unnecessary invasive "
     "follow-up and anxiety, with no evidence of improved survival",
     "Yes — MRI machines are expensive, so they should be used as much as possible",
     "No — some patients dislike being inside an enclosed scanner",
     "Yes — detecting any abnormality early is always beneficial", "", "A",
     "The strongest argument is relevant, evidence-based and weighs real harms against benefits — exactly "
     "what A does. B is a sunk-cost fallacy, C is minor, and D is an unsupported overgeneralisation.",
     "Hard"),
    ("DM", "Syllogisms & Logical Deduction",
     "Should medical students be allowed to view patients' full electronic records during placements? "
     "Select the strongest argument.",
     "Yes — reviewing complete records under supervision develops clinical reasoning, and existing access "
     "rules already protect confidentiality",
     "Yes — students are the doctors of the future",
     "No — patient records contain a great deal of information",
     "No — students might simply find the records interesting", "", "A",
     "A is strongest: it links access to a concrete educational benefit while addressing the main "
     "objection (confidentiality). B is a slogan, C is vague, and D raises a trivial concern.", "Medium"),
]

# Decision Making's second real format: a set of premises followed by five
# independent statements, each judged Yes (necessarily follows) or No (does not
# necessarily follow) — more than one 'Yes' is often correct. Shape:
# (subject_code, topic_name, stem, A, B, C, D, E, correct_csv, explanation, difficulty)
# correct_csv is a sorted, comma-separated set of the letters that are 'Yes'.
_DM_YESNO_QUESTIONS = [
    ("DM", "Syllogisms & Logical Deduction",
     "All cardiac patients in the clinic take Drug A. Some patients who take Drug A also take Drug B. "
     "No patient taking Drug B experiences side effect X. For each statement below, answer Yes if it "
     "necessarily follows from the information above, or No if it does not necessarily follow. More than "
     "one statement may follow.",
     "All cardiac patients take Drug B.",
     "Some patients who take Drug A do not experience side effect X.",
     "No cardiac patients experience side effect X.",
     "All patients who experience side effect X are non-cardiac patients.",
     "If a patient takes Drug A and does not take Drug B, it cannot be determined whether they "
     "experience side effect X.",
     "B,E",
     "A: No — only 'some' Drug A patients also take Drug B, not all. B: Yes — the patients who take both "
     "A and B are a nonempty subset who, by the third premise, don't experience X. C: No — nothing is "
     "said about Drug A patients who don't take Drug B. D: No — too strong; nothing rules out other "
     "cardiac patients experiencing X. E: Yes — the premises are silent on that subgroup, so it genuinely "
     "cannot be determined.", "Hard"),

    ("DM", "Syllogisms & Logical Deduction",
     "Every nurse on the ward has completed infection-control training. Some nurses on the ward also "
     "hold a mentoring qualification. No nurse who holds a mentoring qualification works night shifts. "
     "For each statement below, answer Yes if it necessarily follows, or No if it does not. More than one "
     "statement may follow.",
     "All nurses on the ward work night shifts.",
     "Some nurses with infection-control training do not work night shifts.",
     "Every nurse who works night shifts lacks a mentoring qualification.",
     "No nurse on the ward works night shifts.",
     "All ward nurses who hold a mentoring qualification have completed infection-control training.",
     "B,C,E",
     "A: No — nothing supports this, and it's contradicted for the mentoring-qualified subset. B: Yes — "
     "mentoring-qualified ward nurses are a nonempty subset with training who don't work nights. C: Yes "
     "— this is the contrapositive of the third premise. D: No — only mentoring-qualified nurses are "
     "guaranteed not to work nights, not every ward nurse. E: Yes — every ward nurse has training, and "
     "mentoring-qualified ward nurses are still ward nurses.", "Hard"),

    ("DM", "Venn Diagrams & Sets",
     "A survey of 150 patients found that 70 drink coffee daily, 50 drink tea daily, and 24 drink both "
     "coffee and tea daily. For each statement below, answer Yes if it necessarily follows from these "
     "figures, or No if it does not. More than one statement may follow.",
     "More patients drink only coffee daily than drink only tea daily.",
     "Exactly 54 patients drink neither coffee nor tea daily.",
     "The majority of surveyed patients drink both coffee and tea daily.",
     "More than half of the surveyed patients drink at least one of coffee or tea daily.",
     "It is impossible for a patient to drink neither coffee nor tea daily.",
     "A,B,D",
     "Only coffee = 70−24 = 46; only tea = 50−24 = 26; at least one = 70+50−24 = 96; neither = 150−96 = "
     "54. A: Yes (46 > 26). B: Yes (matches 54). C: No (24/150 = 16%). D: Yes (96/150 = 64%). E: No — 54 "
     "patients do drink neither.", "Medium"),

    ("DM", "Syllogisms & Logical Deduction",
     "All patients on Ward 7 are post-operative. Some post-operative patients require daily wound checks. "
     "No patient requiring daily wound checks has been discharged. For each statement below, answer Yes "
     "if it necessarily follows, or No if it does not. More than one statement may follow.",
     "All patients on Ward 7 require daily wound checks.",
     "No patient on Ward 7 has been discharged.",
     "Some post-operative patients have not been discharged.",
     "If a patient has been discharged, they do not require daily wound checks.",
     "All patients on Ward 7 have been discharged.",
     "C,D",
     "A: No — only 'some' post-operative patients need wound checks, and Ward 7 patients are only known "
     "to be post-operative. B: No — nothing ties Ward 7 specifically to the wound-check subgroup. C: Yes "
     "— the post-operative patients needing wound checks (a nonempty subset) haven't been discharged. D: "
     "Yes — this is the contrapositive of the third premise. E: No — unsupported, and contradicted in "
     "spirit by C.", "Hard"),

    ("DM", "Probability & Statistics",
     "A trial enrolled 200 patients: 120 received a new treatment and the rest received a placebo. Of "
     "those given the new treatment, 90 showed improvement. Of those given the placebo, 40 showed "
     "improvement. For each statement below, answer Yes if it necessarily follows from these figures, or "
     "No if it does not. More than one statement may follow.",
     "More than half of all patients in the trial showed improvement.",
     "Patients given the new treatment were more likely to improve than those given the placebo.",
     "Exactly half of the patients received the placebo.",
     "Fewer than 100 patients improved on the new treatment.",
     "The placebo was completely ineffective.",
     "A,B,D",
     "Placebo group = 200−120 = 80. A: Yes — (90+40)/200 = 65%. B: Yes — 90/120 = 75% vs 40/80 = 50%. C: "
     "No — 80/200 = 40%, not half. D: Yes — 90 < 100. E: No — 40 placebo patients did improve.", "Medium"),

    ("DM", "Syllogisms & Logical Deduction",
     "Every member of the ethics committee has at least five years of clinical experience. Some members "
     "of the ethics committee are also on the research board. No one on the research board has fewer than "
     "ten years of clinical experience. For each statement below, answer Yes if it necessarily follows, or "
     "No if it does not. More than one statement may follow.",
     "All members of the ethics committee have at least ten years of clinical experience.",
     "Some members of the ethics committee have at least ten years of clinical experience.",
     "Everyone with fewer than ten years of clinical experience is not on the research board.",
     "No member of the ethics committee has fewer than five years of clinical experience.",
     "Everyone on the research board is a member of the ethics committee.",
     "B,C,D",
     "A: No — only the research-board subset is guaranteed ten years, not every committee member. B: Yes "
     "— the (nonempty) research-board members are ethics committee members with at least ten years. C: "
     "Yes — this is the contrapositive of the third premise. D: Yes — this directly restates the first "
     "premise. E: No — the premises only say some ethics-committee members are also on the research "
     "board, not that the research board is limited to them.", "Hard"),
]

# flashcards: (subject_code, topic_name, front, back)
_FLASHCARDS = [
    ("VR", "True / False / Can't Tell", "When should you choose 'Can't Tell' in Verbal Reasoning?", "When the passage doesn't give enough information to judge the statement true or false. Never use outside knowledge."),
    ("VR", "Reading for the Main Idea", "What's the recommended VR reading approach given the tight timing?", "Scan for keywords from the question and read only the relevant sentence(s) — you have roughly 20–30 seconds per question."),
    ("VR", "True / False / Can't Tell", "How do absolute words (all, never, always) affect a VR statement?", "They make it easy to disprove — a single exception in the passage makes the statement false."),
    ("DM", "Venn Diagrams & Sets", "How do you find 'neither' in a two-set Venn problem?", "Neither = Total − (|A| + |B| − |A∩B|). Add the two sets, subtract the overlap, subtract from the total."),
    ("DM", "Syllogisms & Logical Deduction", "When is a syllogism's conclusion valid?", "Only if it must be true given the premises. If a counterexample exists, choose 'no valid conclusion'."),
    ("DM", "Probability & Statistics", "Probability of an equally-likely event =", "Favourable outcomes ÷ total outcomes. 'At least one' = 1 − P(none)."),
    ("QR", "Percentages & Percentage Change", "How do you increase a value by x%?", "Multiply by (1 + x/100). A 25% rise on £80 → 80 × 1.25 = £100."),
    ("QR", "Percentages & Percentage Change", "Percentage change formula?", "(change ÷ original) × 100."),
    ("QR", "Speed, Distance & Time", "State the speed equation.", "Speed = distance ÷ time. Keep the units consistent first."),
    ("SJT", "Appropriateness Ratings", "Name the UCAT SJT appropriateness scale.", "Very appropriate · Appropriate but not ideal · Inappropriate but not awful · Very inappropriate."),
    ("SJT", "Medical Ethics & Professionalism", "What framework guides SJT answers?", "The GMC 'Good Medical Practice': patient safety, confidentiality, honesty/integrity, and working within your competence come first."),
    ("SJT", "Medical Ethics & Professionalism", "How is the SJT scored?", "In Bands 1–4 (Band 1 is strongest), reported separately from the cognitive scaled scores."),
    ("VR", "Inference & Author Tone", "What makes a valid inference in Verbal Reasoning?", "It follows from the passage with no extra assumptions. Reject options that are too strong, out of scope, or opposite to the author's view."),
    ("DM", "Logic Puzzles & Arrangements", "How should you start a logic puzzle with several clues?", "Translate the clues into a quick grid or ordering and process the most restrictive clue first, eliminating any option that breaks a single clue."),
    ("DM", "Probability & Statistics", "How do you combine independent events (AND)?", "Multiply their probabilities. For mutually exclusive events (OR), add them; and 'at least one' = 1 − P(none)."),
    ("QR", "Ratios & Proportion", "How do you split a total in the ratio a:b?", "Take fractions a/(a+b) and b/(a+b) of the total. Make sure the units are consistent first."),
    ("QR", "Tables, Charts & Data", "Best approach to a data or table question?", "Read the question first, then extract only the figures you need. Watch units and footnotes such as 'in thousands' or '% of total'."),
    ("SJT", "Importance Ratings", "Which considerations are usually 'very important' in the SJT?", "Those tied to patient safety, professional duty, and the people directly affected. Remember a fact can be true yet unimportant."),
]


def _sync_subject_colors():
    """Keep each subject's color in sync with _SUBJECTS, so a palette change here
    reaches every deployment's existing rows, not just freshly-seeded databases."""
    conn = get_conn()
    try:
        for code, _name, color, _order in _SUBJECTS:
            _run(conn, _n("UPDATE subjects SET color = :col WHERE code = :c"), {"col": color, "c": code})
        _commit(conn)
    finally:
        _close(conn)


def _unpack_question(qt):
    """Accept either an 8-field question tuple (no option E) or a 9-field one
    (with option E), returning a uniform 9-tuple with an empty string for a
    missing fifth option."""
    if len(qt) == 9:
        return qt
    stem, a, b, c, d, correct, expl, diff = qt
    return (stem, a, b, c, d, "", correct, expl, diff)


def _sync_content(conn, code_to_id, topic_key_to_id):
    """Insert or refresh all exactly-UCAT-formatted content — passage sets and
    standalone questions — keyed by stem. Existing seeded questions are updated
    in place so format fixes (e.g. three-option True/False/Can't Tell, five-option
    QR) reach already-seeded rows, while user-created questions (whose stems don't
    match the seed) are left untouched. Returns the number of new questions added."""
    now = datetime.now().isoformat()
    title_to_id = {r["title"]: r["id"] for r in _q(conn, "SELECT id, title FROM passages")}
    existing = {r["stem"]: r["id"] for r in _q(conn, "SELECT id, stem FROM questions")}
    added = 0

    def upsert_q(code, tname, pid, qt, fmt="single"):
        nonlocal added
        stem, a, b, c, d, e, correct, expl, diff = _unpack_question(qt)
        params = {"s": code_to_id[code], "t": topic_key_to_id.get((code, tname)), "p": pid,
                  "stem": stem, "a": a, "b": b, "c": c, "d": d, "e": (e or None),
                  "cor": correct, "ex": expl, "diff": diff, "fmt": fmt, "ca": now}
        if stem in existing:
            params["id"] = existing[stem]
            _run(conn, _n("""UPDATE questions SET subject_id=:s, topic_id=:t, passage_id=:p,
                       option_a=:a, option_b=:b, option_c=:c, option_d=:d, option_e=:e,
                       correct=:cor, explanation=:ex, difficulty=:diff, question_format=:fmt,
                       active=1 WHERE id=:id"""), params)
        else:
            existing[stem] = _run(conn, _n("""INSERT INTO questions (subject_id, topic_id, passage_id,
                       stem, option_a, option_b, option_c, option_d, option_e, correct, explanation,
                       difficulty, question_format, active, created_at)
                       VALUES (:s,:t,:p,:stem,:a,:b,:c,:d,:e,:cor,:ex,:diff,:fmt,1,:ca)"""), params)
            added += 1

    for code, tname, title, body, questions in _PASSAGE_SETS:
        if code not in code_to_id:
            continue
        pid = title_to_id.get(title)
        if pid is None:
            pid = _run(conn, _n("""INSERT INTO passages (subject_id, topic_id, title, body, created_at)
                       VALUES (:s,:t,:ti,:b,:ca)"""),
                       {"s": code_to_id[code], "t": topic_key_to_id.get((code, tname)),
                        "ti": title, "b": body, "ca": now})
            title_to_id[title] = pid
        keep = []
        for qt in questions:
            keep.append(_unpack_question(qt)[0])
            upsert_q(code, tname, pid, qt)
        # Retire any stale questions still attached to this passage whose stem is
        # no longer in the current set (e.g. a question that was reworded), so an
        # existing deployment stops serving the superseded version.
        ph = _ph()
        marks = ",".join([ph] * len(keep))
        _run(conn, f"UPDATE questions SET active = 0 WHERE passage_id = {ph} "
                   f"AND stem NOT IN ({marks})", tuple([pid] + keep))

    for row in _STANDALONE_QUESTIONS:
        code, tname = row[0], row[1]
        if code not in code_to_id:
            continue
        upsert_q(code, tname, None, row[2:])

    # Decision Making's real "Yes/No statements" format: one premise, five
    # statements each judged Yes/No independently, with more than one 'Yes'
    # often correct — stored as a sorted comma-separated set of letters.
    for code, tname, stem, a, b, c, d, e, correct_csv, expl, diff in _DM_YESNO_QUESTIONS:
        if code not in code_to_id:
            continue
        upsert_q(code, tname, None, (stem, a, b, c, d, e, correct_csv, expl, diff), fmt="multi")

    _commit(conn)
    return added


def seed_content():
    """Idempotently load the starter MCAT content the first time the app runs."""
    existing = get_subjects()
    if existing:
        _sync_subject_colors()
        return  # already seeded
    conn = get_conn()
    try:
        # Subjects
        code_to_id = {}
        for code, name, color, order in _SUBJECTS:
            sid = _run(conn, _n("INSERT INTO subjects (code, name, color, sort_order) VALUES (:c,:n,:col,:o)"),
                       {"c": code, "n": name, "col": color, "o": order})
            code_to_id[code] = sid
        _commit(conn)
        # Topics
        now = datetime.now().isoformat()
        topic_key_to_id = {}
        for code, name, hy, summary, content in _TOPICS:
            tid = _run(conn, _n("""INSERT INTO topics (subject_id, name, high_yield, summary, content, created_at)
                       VALUES (:s,:n,:hy,:sum,:c,:ca)"""),
                       {"s": code_to_id[code], "n": name, "hy": hy, "sum": summary, "c": content, "ca": now})
            topic_key_to_id[(code, name)] = tid
        _commit(conn)
        # Questions — legacy Decision Making starter items (its single-best-answer
        # four-option format is valid real UCAT format). The exactly-formatted
        # content for every subtest, DM included, is loaded by _sync_content below.
        for code, tname, stem, a, b, c, d, correct, expl, diff in _QUESTIONS:
            _run(conn, _n("""INSERT INTO questions (subject_id, topic_id, stem, option_a, option_b,
                       option_c, option_d, correct, explanation, difficulty, created_at)
                       VALUES (:s,:t,:stem,:a,:b,:c,:d,:cor,:e,:diff,:ca)"""),
                 {"s": code_to_id[code], "t": topic_key_to_id.get((code, tname)), "stem": stem,
                  "a": a, "b": b, "c": c, "d": d, "cor": correct, "e": expl, "diff": diff, "ca": now})
        # Flashcards
        today = date.today().isoformat()
        for code, tname, front, back in _FLASHCARDS:
            _run(conn, _n("""INSERT INTO flashcards (subject_id, topic_id, front, back, due_date, created_at)
                       VALUES (:s,:t,:f,:b,:due,:ca)"""),
                 {"s": code_to_id[code], "t": topic_key_to_id.get((code, tname)),
                  "f": front, "b": back, "due": today, "ca": now})
        _commit(conn)
        # Exactly-UCAT-formatted content (passage sets + standalone questions)
        _sync_content(conn, code_to_id, topic_key_to_id)
    finally:
        _close(conn)


def backfill_content():
    """Idempotently add any seed topics/questions/flashcards that are missing.

    Unlike seed_content(), this runs even on an already-populated database, so
    expanded starter content reaches an existing deployment (e.g. Neon) without
    a manual reload. It only *adds* rows that are absent — matching questions by
    stem and flashcards by (front, back) — and never updates or deletes, so any
    user-edited or user-created content is left untouched.
    """
    subs = get_subjects()
    if not subs:
        return  # fresh database: seed_content() handles the initial load
    code_to_id = {s["code"]: s["id"] for s in subs}
    id_to_code = {v: k for k, v in code_to_id.items()}
    added_t = added_q = added_f = 0
    conn = get_conn()
    try:
        now = datetime.now().isoformat()
        today = date.today().isoformat()

        # Topics — map existing (code, name) → id, inserting any that are missing
        topic_key_to_id = {}
        for r in _q(conn, "SELECT id, subject_id, name FROM topics"):
            code = id_to_code.get(r["subject_id"])
            if code:
                topic_key_to_id[(code, r["name"])] = r["id"]
        for code, name, hy, summary, content in _TOPICS:
            if code not in code_to_id or (code, name) in topic_key_to_id:
                continue
            tid = _run(conn, _n("""INSERT INTO topics (subject_id, name, high_yield, summary, content, created_at)
                       VALUES (:s,:n,:hy,:sum,:c,:ca)"""),
                       {"s": code_to_id[code], "n": name, "hy": hy, "sum": summary, "c": content, "ca": now})
            topic_key_to_id[(code, name)] = tid
            added_t += 1
        _commit(conn)

        # Questions — insert any legacy Decision Making starter whose stem is absent.
        existing_stems = {r["stem"] for r in _q(conn, "SELECT stem FROM questions")}
        for code, tname, stem, a, b, c, d, correct, expl, diff in _QUESTIONS:
            if code not in code_to_id or stem in existing_stems:
                continue
            _run(conn, _n("""INSERT INTO questions (subject_id, topic_id, stem, option_a, option_b,
                       option_c, option_d, correct, explanation, difficulty, created_at)
                       VALUES (:s,:t,:stem,:a,:b,:c,:d,:cor,:e,:diff,:ca)"""),
                 {"s": code_to_id[code], "t": topic_key_to_id.get((code, tname)), "stem": stem,
                  "a": a, "b": b, "c": c, "d": d, "cor": correct, "e": expl, "diff": diff, "ca": now})
            existing_stems.add(stem)
            added_q += 1

        # Flashcards — insert any whose (front, back) pair is not already present
        existing_cards = {(r["front"], r["back"]) for r in _q(conn, "SELECT front, back FROM flashcards")}
        for code, tname, front, back in _FLASHCARDS:
            if code not in code_to_id or (front, back) in existing_cards:
                continue
            _run(conn, _n("""INSERT INTO flashcards (subject_id, topic_id, front, back, due_date, created_at)
                       VALUES (:s,:t,:f,:b,:due,:ca)"""),
                 {"s": code_to_id[code], "t": topic_key_to_id.get((code, tname)),
                  "f": front, "b": back, "due": today, "ca": now})
            existing_cards.add((front, back))
            added_f += 1
        _commit(conn)

        # Exactly-UCAT-formatted content — inserts new passage/standalone questions
        # and refreshes already-seeded ones (e.g. 3-option TFC, 5-option QR) in
        # place, so an existing deployment updates without a manual reload.
        added_q += _sync_content(conn, code_to_id, topic_key_to_id)
    finally:
        _close(conn)
    return {"topics_added": added_t, "questions_added": added_q, "flashcards_added": added_f}
