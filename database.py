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
CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    topic_id    INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    stem        TEXT NOT NULL,
    option_a    TEXT NOT NULL,
    option_b    TEXT NOT NULL,
    option_c    TEXT NOT NULL,
    option_d    TEXT NOT NULL,
    correct     TEXT NOT NULL CHECK(correct IN ('A','B','C','D')),
    explanation TEXT,
    difficulty  TEXT DEFAULT 'Medium' CHECK(difficulty IN ('Easy','Medium','Hard')),
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
    """CREATE TABLE IF NOT EXISTS questions (
        id          SERIAL PRIMARY KEY,
        subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        topic_id    INTEGER REFERENCES topics(id) ON DELETE SET NULL,
        stem        TEXT NOT NULL,
        option_a    TEXT NOT NULL,
        option_b    TEXT NOT NULL,
        option_c    TEXT NOT NULL,
        option_d    TEXT NOT NULL,
        correct     TEXT NOT NULL CHECK(correct IN ('A','B','C','D')),
        explanation TEXT,
        difficulty  TEXT DEFAULT 'Medium' CHECK(difficulty IN ('Easy','Medium','Hard')),
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

def get_questions(subject_id=None, topic_id=None, difficulty=None, limit=None):
    ph = _ph()
    sql = """SELECT q.*, s.name AS subject_name, s.color, t.name AS topic_name
             FROM questions q JOIN subjects s ON q.subject_id = s.id
             LEFT JOIN topics t ON q.topic_id = t.id WHERE 1=1"""
    params: list = []
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
            FROM subjects s LEFT JOIN questions q ON q.subject_id = s.id
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
    conn = get_conn()
    try:
        if data.get("id"):
            _run(conn, _n("""
                UPDATE questions SET subject_id=:subject_id, topic_id=:topic_id, stem=:stem,
                    option_a=:option_a, option_b=:option_b, option_c=:option_c, option_d=:option_d,
                    correct=:correct, explanation=:explanation, difficulty=:difficulty WHERE id=:id
            """), data)
        else:
            data["created_at"] = now
            data["id"] = _run(conn, _n("""
                INSERT INTO questions (subject_id, topic_id, stem, option_a, option_b, option_c,
                    option_d, correct, explanation, difficulty, created_at)
                VALUES (:subject_id, :topic_id, :stem, :option_a, :option_b, :option_c,
                    :option_d, :correct, :explanation, :difficulty, :created_at)
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
    ("VR",  "Verbal Reasoning",       "#1f77b4", 1),
    ("DM",  "Decision Making",        "#2ca02c", 2),
    ("QR",  "Quantitative Reasoning", "#9467bd", 3),
    ("SJT", "Situational Judgement",  "#ff7f0e", 4),
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

# questions: (subject_code, topic_name, stem, A, B, C, D, correct, explanation, difficulty)
_QUESTIONS = [
    ("VR", "Reading for the Main Idea",
     "Passage: \"Although caffeine is widely consumed, recent studies suggest its effect on long-term memory is negligible. Its impact on short-term alertness, however, is reliably positive.\" Which statement is best supported by the passage?",
     "Caffeine improves long-term memory",
     "Caffeine reliably improves short-term alertness",
     "Caffeine has no measurable effect on the body",
     "Caffeine consumption is declining", "B",
     "Only B is directly stated. A contradicts the passage, while C and D are not supported by anything in the text.", "Easy"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"The clinic opens at 9 am on weekdays.\" Statement: \"The clinic opens at 9 am on Saturdays.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "C",
     "The passage only mentions weekdays and says nothing about Saturdays, so there isn't enough information to judge — the answer is 'Can't tell'.", "Medium"),
    ("VR", "Inference & Author Tone",
     "Passage: \"Every member of the debating society must pass an entry assessment. Priya is a member of the debating society.\" Which conclusion follows?",
     "Priya enjoys debating",
     "Priya must have passed (or must pass) the entry assessment",
     "Priya is the best debater",
     "Priya founded the society", "B",
     "If all members must pass the assessment and Priya is a member, it necessarily follows that the assessment applies to her. The others add information the passage never gives.", "Medium"),
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
    ("QR", "Percentages & Percentage Change",
     "A medication costs £80. Its price increases by 25%. What is the new price?",
     "£85", "£100", "£105", "£120", "B",
     "An increase of 25% multiplies the price by 1.25: 80 × 1.25 = £100.", "Easy"),
    ("QR", "Percentages & Percentage Change",
     "A patient's weight falls from 90 kg to 81 kg. What is the percentage decrease?",
     "9%", "10%", "11%", "90%", "B",
     "Change = 9 kg. Percentage change = (9 ÷ 90) × 100 = 10%.", "Medium"),
    ("QR", "Speed, Distance & Time",
     "A car travels 150 km in 2.5 hours. What is its average speed?",
     "50 km/h", "60 km/h", "75 km/h", "375 km/h", "B",
     "Speed = distance ÷ time = 150 ÷ 2.5 = 60 km/h.", "Easy"),
    ("SJT", "Appropriateness Ratings",
     "A medical student notices that a fellow student has posted identifiable patient details on social media. How appropriate is it for the student to ask the colleague to remove the post immediately?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "A",
     "Patient confidentiality is a core professional duty. Asking for the post to be taken down at once directly protects patients, so it is very appropriate (escalating to a senior may also be needed).", "Medium"),
    ("SJT", "Importance Ratings",
     "A junior colleague seems overwhelmed and has started making errors. When deciding how to respond, how important is it to consider patient safety?",
     "Very important", "Important", "Of minor importance", "Not important at all", "A",
     "Patient safety is the overriding concern in GMC Good Medical Practice, so it is a very important consideration in any clinical decision.", "Easy"),
    ("SJT", "Medical Ethics & Professionalism",
     "A patient asks a medical student whether they personally think the patient should refuse a treatment the doctor has recommended. What is the most appropriate response?",
     "Tell the patient to refuse the treatment",
     "Give the patient the student's own medical advice",
     "Encourage the patient to discuss their concerns with the responsible doctor",
     "Ignore the patient's question", "C",
     "A student should work within their competence and not give independent medical advice. Directing the patient back to the responsible doctor respects both patient autonomy and professional boundaries.", "Medium"),

    # ── Additional seeded questions ─────────────────────────────────────────
    ("VR", "Reading for the Main Idea",
     "Passage: \"Although many assume vaccination was a twentieth-century invention, deliberate inoculation against smallpox was practised in parts of Asia centuries earlier. What modern science added was not the idea but its safety and standardisation.\" Which statement is best supported?",
     "Vaccination was first invented in the twentieth century",
     "Inoculation against smallpox predates modern science",
     "Smallpox no longer exists anywhere in the world",
     "Modern medicine has made no real contribution to vaccines", "B",
     "The passage states inoculation was practised centuries before modern science, which is exactly option B. A is contradicted, and C and D go beyond anything in the text.", "Medium"),
    ("VR", "Reading for the Main Idea",
     "Passage: \"The report concludes that while remote consultations improve access for rural patients, they are no substitute for an in-person examination when physical signs must be assessed.\" Which statement is best supported?",
     "Remote consultations should replace all in-person visits",
     "Remote consultations can improve access but have clear limits",
     "Rural patients always prefer in-person appointments",
     "Physical examination is never necessary", "B",
     "The passage credits remote consultations with improving access while noting they cannot replace a physical examination — precisely option B. A and D are contradicted; C is never stated.", "Medium"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"The new hospital wing was completed in 2019 and opened to patients in 2020.\" Statement: \"The new wing treated patients before 2020.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "B",
     "The passage says the wing opened to patients in 2020, so it did not treat patients before then. The statement is contradicted, making it False.", "Easy"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"Dr Lee holds clinics on Mondays, Wednesdays and Fridays.\" Statement: \"Dr Lee never works at weekends.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "C",
     "The passage lists the weekdays Dr Lee holds clinics but says nothing about weekends, so there isn't enough information to judge the statement — the answer is 'Can't tell'.", "Medium"),
    ("VR", "Inference & Author Tone",
     "Passage: \"Yet another so-called breakthrough diet promises miracles while quietly ignoring the basic arithmetic of calories.\" The author's tone toward the diet is best described as:",
     "Enthusiastic", "Neutral and detached", "Sceptical", "Admiring", "C",
     "Phrases like 'so-called breakthrough' and 'promises miracles while ignoring the basic arithmetic' signal doubt and criticism, so the tone is sceptical.", "Medium"),

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

    ("QR", "Percentages & Percentage Change",
     "A jacket priced at £60 is reduced by 15% in a sale. What is the sale price?",
     "£45", "£51", "£54", "£55", "B",
     "A 15% reduction multiplies the price by 0.85: 60 × 0.85 = £51.", "Easy"),
    ("QR", "Percentages & Percentage Change",
     "After a 20% increase, a season ticket now costs £360. What was the original price?",
     "£288", "£300", "£320", "£340", "B",
     "Original × 1.2 = 360, so original = 360 ÷ 1.2 = £300. (Subtracting 20% of £360 is the classic trap.)", "Medium"),
    ("QR", "Ratios & Proportion",
     "A medicine is mixed with water in the ratio 2:5. To make 350 ml of the mixture, how much medicine is needed?",
     "70 ml", "100 ml", "140 ml", "175 ml", "B",
     "Medicine makes up 2 of every 7 parts, so 2/7 × 350 = 100 ml.", "Medium"),
    ("QR", "Ratios & Proportion",
     "A recipe for 4 people uses 600 g of flour. How much flour is needed to serve 6 people?",
     "750 g", "800 g", "900 g", "1000 g", "C",
     "Flour per person = 600 ÷ 4 = 150 g; for 6 people, 150 × 6 = 900 g.", "Easy"),
    ("QR", "Speed, Distance & Time",
     "A cyclist rides at a steady 18 km/h for 40 minutes. How far do they travel?",
     "7.2 km", "12 km", "13.5 km", "27 km", "B",
     "40 minutes is 2/3 of an hour, so distance = speed × time = 18 × 2/3 = 12 km.", "Medium"),
    ("QR", "Tables, Charts & Data",
     "A clinic saw 1,200 patients in total last year, of which 35% were seen during winter. How many patients were seen in winter?",
     "350", "420", "480", "600", "B",
     "35% of 1,200 = 0.35 × 1,200 = 420 patients.", "Easy"),

    ("SJT", "Appropriateness Ratings",
     "During a ward round a medical student realises they forgot to record a patient's drug allergy in the notes. How appropriate is it for the student to correct the notes and tell the supervising doctor straight away?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "A",
     "An unrecorded allergy is a direct patient-safety risk. Correcting the record promptly and informing the supervisor is exactly what professional duty requires, so it is very appropriate.", "Medium"),
    ("SJT", "Appropriateness Ratings",
     "A friend asks a medical student to share photos taken inside the operating theatre on a social-media group chat. How appropriate is it for the student to refuse?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "A",
     "Sharing theatre photos risks breaching patient confidentiality and professional standards. Refusing protects patients and is very appropriate.", "Easy"),
    ("SJT", "Importance Ratings",
     "A student doctor disagrees with a senior's management plan. When deciding how to act, how important is it to consider that the student's own view might be mistaken due to limited experience?",
     "Very important", "Important", "Of minor importance", "Not important at all", "A",
     "Recognising the limits of one's own competence is central to GMC guidance, so it is a very important consideration — while still raising any genuine safety concern through the proper channel.", "Medium"),
    ("SJT", "Importance Ratings",
     "A colleague offers to write up a procedure log entry for a clinical skill the student did not actually perform. When deciding how to respond, how important is honesty in record-keeping?",
     "Very important", "Important", "Of minor importance", "Not important at all", "A",
     "Probity — honesty and integrity — is a core GMC duty, and falsifying records is a serious breach. Honesty is therefore a very important consideration.", "Easy"),
    ("SJT", "Medical Ethics & Professionalism",
     "An adult patient with full capacity refuses a recommended blood transfusion on religious grounds. What is the most appropriate response from the team?",
     "Give the transfusion anyway to save their life",
     "Respect the patient's informed refusal while ensuring they understand the consequences",
     "Ask the patient's family to overrule the decision",
     "Discharge the patient immediately", "B",
     "A competent, informed adult has the right to refuse treatment. The team should respect the patient's autonomy while making sure the refusal is fully informed.", "Hard"),
    ("SJT", "Medical Ethics & Professionalism",
     "A junior doctor smells alcohol on a colleague who is about to start a clinical shift. What is the most appropriate first action?",
     "Ignore it and hope nothing goes wrong",
     "Announce it to all the other staff on the ward",
     "Raise the concern discreetly with a senior so patient safety is protected",
     "Post about it anonymously online", "C",
     "Patient safety comes first, and concerns about a colleague's fitness to practise must be raised promptly through the proper senior channel — discreetly, not publicly.", "Medium"),

    # ── Extended bank: higher-difficulty, exam-realistic questions ───────────
    # Verbal Reasoning
    ("VR", "Reading for the Main Idea",
     "Passage: \"A recent survey of hospital staff found that mandatory overtime, not patient volume, was the strongest predictor of reported burnout. Departments that reduced overtime saw burnout scores fall even when patient numbers rose.\" Which statement is best supported?",
     "Patient volume has no effect on burnout",
     "Reducing mandatory overtime is associated with lower burnout, independent of patient numbers",
     "Burnout scores always fall when overtime increases",
     "All hospital departments have reduced overtime", "B",
     "The passage states overtime was the strongest predictor, and reducing it lowered burnout even as patient numbers rose — directly supporting B. A overreaches, C contradicts, and D is not stated.", "Medium"),
    ("VR", "Reading for the Main Idea",
     "Passage: \"Antibiotic resistance arises when bacteria are exposed to antibiotics that kill only the most susceptible strains, leaving hardier variants to multiply. Overuse of antibiotics accelerates this selective pressure, not the drugs' chemical structure.\" Which statement is best supported?",
     "Antibiotic overuse speeds up the emergence of resistant bacteria",
     "Resistance is caused by the chemical structure of antibiotics",
     "Antibiotics kill all bacteria equally",
     "Resistant bacteria cannot multiply", "A",
     "The passage says overuse accelerates the selective pressure behind resistance, directly supporting A. B is explicitly contradicted; C and D are contradicted by the passage's description of selective survival.", "Easy"),
    ("VR", "Reading for the Main Idea",
     "Passage: \"Contrary to popular belief, the introduction of the printing press did not immediately increase literacy rates across Europe; contemporary records suggest widespread literacy gains took over a century to materialise.\" Which statement is best supported?",
     "The printing press had no long-term effect on literacy",
     "Literacy rose sharply within a decade of the printing press's invention",
     "The rise in literacy following the printing press was gradual, unfolding over a long period",
     "Literacy rates were higher before the printing press than after", "C",
     "The passage states literacy gains \"took over a century to materialise\", supporting a gradual long-term rise. A, B and D are all contradicted or unsupported.", "Medium"),
    ("VR", "Reading for the Main Idea",
     "Passage: \"Hospital A reports shorter average waiting times than Hospital B, but Hospital A also treats a narrower range of conditions and refers complex cases elsewhere.\" Which statement is best supported?",
     "Hospital A provides better overall care than Hospital B",
     "The shorter waiting times at Hospital A may partly reflect its narrower case mix rather than superior efficiency",
     "Hospital B refers no cases elsewhere",
     "Waiting times are unrelated to case complexity", "B",
     "The passage flags Hospital A's narrower case mix and referral practice as a caveat to the raw wait-time comparison, directly supporting B. A is an unsupported evaluative leap; C and D are not stated.", "Hard"),
    ("VR", "Reading for the Main Idea",
     "Passage: \"Regular exercise has been linked to improved mood, but researchers caution that people who already feel better may simply be more likely to exercise, making the direction of cause and effect unclear.\" Which statement is best supported?",
     "Exercise definitely improves mood",
     "The relationship between exercise and mood could run in either direction",
     "Mood has no relationship to exercise",
     "Only people who feel good are capable of exercising", "B",
     "The passage explicitly says the direction of cause and effect is unclear, supporting B. A overstates certainty, C contradicts the stated link, and D is too strong to be supported.", "Easy"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"The pharmacy on the ground floor is open from 8 am to 6 pm, Monday to Friday.\" Statement: \"The pharmacy is open on Saturdays.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "C",
     "The passage only covers Monday to Friday and says nothing about Saturdays, so there is not enough information to judge — the answer is 'Can't tell'.", "Easy"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"Every nurse on the night shift must complete a handover report before leaving the ward.\" Statement: \"A nurse who left the ward without completing a handover report broke ward policy.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "A",
     "The passage states the handover report must be completed before leaving; leaving without doing so directly breaks the stated policy, so the statement is True.", "Medium"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"The new MRI scanner was installed in March 2023 and became available for patient use in June 2023.\" Statement: \"The scanner was used on patients in April 2023.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "B",
     "The passage states the scanner only became available for patient use in June 2023, so it could not have been used on patients in April 2023 — the statement is False.", "Easy"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"Dr Adeyemi specialises in paediatric cardiology and consults at the regional hospital every Tuesday and Thursday.\" Statement: \"Dr Adeyemi never sees patients on Mondays.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "C",
     "The passage states which days Dr Adeyemi consults at this hospital but does not rule out other clinical activity elsewhere, so there isn't enough information to judge the statement — 'Can't tell'.", "Medium"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"The trial enrolled 500 participants, of whom 260 received the experimental treatment and the remainder received the standard treatment.\" Statement: \"More participants received the experimental treatment than the standard treatment.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "A",
     "260 received the experimental treatment, so 240 received the standard treatment (500 − 260). Since 260 is greater than 240, the statement is directly confirmed by the passage's numbers — True.", "Medium"),
    ("VR", "Inference & Author Tone",
     "Passage: \"It is, apparently, revolutionary: a supplement that promises to reverse aging, boost intelligence, and cure fatigue — all without a shred of peer-reviewed evidence.\" The author's tone is best described as:",
     "Enthusiastic", "Neutral and objective", "Sceptical", "Admiring", "C",
     "Words like 'apparently' and the pointed remark about the lack of peer-reviewed evidence signal doubt and mockery, so the tone is sceptical.", "Easy"),
    ("VR", "Inference & Author Tone",
     "Passage: \"The committee's report, though thorough, arrived eighteen months after the incident it was meant to investigate — by which point most of its recommendations were already overtaken by events.\" Which inference is best supported?",
     "The report's delay reduced its practical usefulness",
     "The report contained no useful recommendations",
     "The committee did not investigate thoroughly",
     "Eighteen months is an unusually short time for such investigations", "A",
     "The passage says the recommendations were 'overtaken by events' because of the delay, directly supporting A. B, C and D are not supported — the report is even described as thorough.", "Medium"),
    ("VR", "Inference & Author Tone",
     "Passage: \"Every patient in the trial reported at least mild improvement in symptoms; some reported complete resolution.\" Which conclusion follows?",
     "All patients in the trial experienced complete resolution",
     "All patients experienced at least some improvement",
     "The treatment cured the underlying disease",
     "No patients experienced side effects", "B",
     "The passage directly states every patient had at least mild improvement, supporting B without over-reaching into claims about complete resolution, a cure, or side effects that the passage never mentions.", "Easy"),
    ("VR", "Inference & Author Tone",
     "Passage: \"The junior doctor's proposal was, in the consultant's words, 'an interesting idea, certainly worth revisiting once the budget allows' — a response that, on reflection, meant nothing would happen for a very long time.\" The author's tone toward the consultant's response is best described as:",
     "Approving", "Wry and knowing", "Furious", "Confused", "B",
     "The aside that the polite phrasing 'meant nothing would happen for a very long time' shows the author sees through the diplomatic language — a wry, knowing observation rather than approval or anger.", "Hard"),
    ("VR", "Inference & Author Tone",
     "Passage: \"Only two of the twelve committee members voted against the proposal, yet the chair described the decision as 'contentious.'\" Which inference is best supported?",
     "The chair's description accurately reflects a near-even split",
     "The chair's characterisation may overstate the level of disagreement suggested by the vote",
     "The two dissenting members were removed from the committee",
     "The proposal failed to pass", "B",
     "A 10–2 vote is far from an even split, so calling the outcome 'contentious' appears to overstate the disagreement relative to the numbers, supporting B. A is contradicted by the vote count; C and D are not stated.", "Hard"),

    # Decision Making
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

    # Quantitative Reasoning
    ("QR", "Percentages & Percentage Change",
     "A vaccine batch had a 95% efficacy rate in a trial of 400 participants. How many participants were NOT protected by the vaccine?",
     "5", "20", "38", "95", "B",
     "5% of 400 = 20 participants not protected.", "Easy"),
    ("QR", "Percentages & Percentage Change",
     "A hospital's annual budget decreases from £2,400,000 to £2,160,000. What is the percentage decrease?",
     "8%", "10%", "12%", "15%", "B",
     "Change = £240,000. Percentage decrease = 240,000 ÷ 2,400,000 × 100 = 10%.", "Medium"),
    ("QR", "Percentages & Percentage Change",
     "After a 10% pay rise followed by a further 10% pay rise on the new amount, an employee's salary is £36,300. What was the original salary?",
     "£29,000", "£30,000", "£33,000", "£33,300", "B",
     "Original × 1.1 × 1.1 = original × 1.21 = £36,300, so original = 36,300 ÷ 1.21 = £30,000.", "Hard"),
    ("QR", "Percentages & Percentage Change",
     "A drug's dosage is reduced by 30%, and the reduced amount is then increased by 30%. If the original dose was 200 mg, what is the final dose?",
     "178 mg", "182 mg", "186 mg", "200 mg", "B",
     "200 × 0.7 = 140 mg after the reduction; 140 × 1.3 = 182 mg after the increase. A 30% cut followed by a 30% rise does not return to the original value.", "Medium"),
    ("QR", "Ratios & Proportion",
     "A saline solution is mixed in the ratio 3 parts salt to 47 parts water. How much salt is in 500 ml of solution?",
     "15 ml", "25 ml", "30 ml", "47 ml", "C",
     "Total parts = 50. Salt fraction = 3/50. 3/50 × 500 ml = 30 ml.", "Medium"),
    ("QR", "Ratios & Proportion",
     "Two nurses split a set of night shifts in the ratio 5:3. If the nurse with fewer shifts works 12 shifts, how many shifts does the other nurse work?",
     "15", "18", "20", "24", "C",
     "3 parts = 12 shifts, so 1 part = 4 shifts. 5 parts = 20 shifts.", "Easy"),
    ("QR", "Ratios & Proportion",
     "A recipe requires flour, sugar and butter in the ratio 5:2:1. If 320 g of the mixture is made in total, how much sugar is used?",
     "40 g", "64 g", "80 g", "160 g", "C",
     "Total parts = 8. Sugar = 2/8 × 320 g = 80 g.", "Medium"),
    ("QR", "Ratios & Proportion",
     "A map has a scale of 1:25,000. Two clinics are 8 cm apart on the map. What is the actual distance between them, in kilometres?",
     "0.2 km", "2 km", "20 km", "200 km", "B",
     "8 cm × 25,000 = 200,000 cm = 2,000 m = 2 km.", "Hard"),
    ("QR", "Speed, Distance & Time",
     "An ambulance travels the first 30 km of a journey at 60 km/h and the next 30 km at 40 km/h. What is its average speed for the whole journey?",
     "46 km/h", "48 km/h", "50 km/h", "52 km/h", "B",
     "Time for first leg = 30/60 = 0.5 h; second leg = 30/40 = 0.75 h; total time = 1.25 h; total distance = 60 km. Average speed = 60 ÷ 1.25 = 48 km/h — not the simple average of the two speeds.", "Hard"),
    ("QR", "Speed, Distance & Time",
     "A nurse walks to work at 5 km/h and it takes her 24 minutes. How far away is her workplace?",
     "1.5 km", "2 km", "2.5 km", "3 km", "B",
     "24 minutes = 0.4 hours. Distance = speed × time = 5 × 0.4 = 2 km.", "Easy"),
    ("QR", "Speed, Distance & Time",
     "Two trains 210 km apart travel toward each other, one at 50 km/h and the other at 55 km/h. How long until they meet?",
     "1.5 hours", "2 hours", "2.5 hours", "3 hours", "B",
     "Combined closing speed = 105 km/h. Time to meet = 210 ÷ 105 = 2 hours.", "Medium"),
    ("QR", "Tables, Charts & Data",
     "A clinic's records show 480 appointments last month, of which 30% were cancelled. Of the cancelled appointments, half were rebooked. How many appointments were cancelled and NOT rebooked?",
     "72", "96", "144", "168", "A",
     "Cancelled = 30% × 480 = 144. Not rebooked = half of 144 = 72.", "Medium"),
    ("QR", "Tables, Charts & Data",
     "A bar chart shows a department saw 120 patients in Q1, 150 in Q2, 90 in Q3 and 140 in Q4. What percentage of the year's patients were seen in Q2?",
     "25%", "28%", "30%", "33%", "C",
     "Total = 120 + 150 + 90 + 140 = 500. Q2 share = 150 ÷ 500 × 100 = 30%.", "Medium"),
    ("QR", "Tables, Charts & Data",
     "A table shows a drug's side-effect rate as 12 per 1,000 patients treated. If a hospital treats 4,250 patients with the drug in a year, how many would be expected to experience the side effect (to the nearest whole number)?",
     "42", "45", "48", "51", "D",
     "12 ÷ 1,000 × 4,250 = 51.", "Hard"),
    ("QR", "Tables, Charts & Data",
     "A pie chart shows that 45% of a survey's respondents rated a service 'Excellent', 35% rated it 'Good', and the remainder rated it 'Poor'. If 60 people rated it 'Poor', how many people took the survey in total?",
     "200", "240", "300", "320", "C",
     "'Poor' share = 100% − 45% − 35% = 20%. 20% of the total = 60, so the total = 60 ÷ 0.2 = 300.", "Medium"),

    # Situational Judgement
    ("SJT", "Appropriateness Ratings",
     "A medical student witnesses a senior doctor make a joke that could be seen as disrespectful toward a patient's cultural background, in front of the patient. How appropriate is it for the student to raise this with the doctor privately after the consultation?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "A",
     "Raising a professionalism concern privately and promptly protects patient dignity and gives the senior doctor a chance to reflect without public confrontation — very appropriate.", "Medium"),
    ("SJT", "Appropriateness Ratings",
     "A medical student is asked by a patient's relative for detailed information about the patient's diagnosis, but the patient has not consented to this being shared. How appropriate is it for the student to politely decline and direct the relative to the patient or the treating team?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "A",
     "Confidentiality must be maintained without patient consent; directing the relative to the proper channel is exactly the appropriate response.", "Easy"),
    ("SJT", "Appropriateness Ratings",
     "Running late for a placement, a medical student considers skipping hand hygiene between patients to save time. How appropriate is it to skip hand hygiene in this situation?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "D",
     "Skipping infection control procedures directly risks patient safety regardless of time pressure — very inappropriate.", "Easy"),
    ("SJT", "Appropriateness Ratings",
     "A student notices a peer appears to be copying another student's reflective portfolio entries. How appropriate is it for the student to raise this directly and privately with the peer before deciding whether further action is needed?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "B",
     "Speaking to the peer first is a reasonable, proportionate first step, though on its own it may not fully address an academic integrity concern that could still need escalation — appropriate, but not ideal as a complete response.", "Hard"),
    ("SJT", "Appropriateness Ratings",
     "A patient becomes visibly upset and starts crying while discussing their diagnosis with a medical student present. How appropriate is it for the student to pause, acknowledge the patient's distress, and ask if they would like a moment before continuing?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "A",
     "Responding to patient distress with a pause and compassion respects the patient and supports good communication — very appropriate.", "Easy"),
    ("SJT", "Importance Ratings",
     "A doctor is deciding whether to prescribe a new medication to a patient. How important is it to check the patient's known drug allergies before prescribing?",
     "Very important", "Important", "Of minor importance", "Not important at all", "A",
     "Checking allergies is a fundamental patient-safety step before any prescription — very important.", "Easy"),
    ("SJT", "Importance Ratings",
     "A medical student is deciding how to phrase feedback to a peer about a clinical skill they performed poorly during a simulated session. How important is it to consider the peer's feelings when giving the feedback?",
     "Very important", "Important", "Of minor importance", "Not important at all", "B",
     "Consideration for the peer's feelings should shape respectful, constructive delivery — important — but it should not override giving honest, accurate feedback, which is why it is 'important' rather than 'very important' here.", "Hard"),
    ("SJT", "Importance Ratings",
     "A team is deciding how to allocate a limited supply of a specialist medication among several patients who could benefit. How important is it to consider clinical need and likely benefit for each patient?",
     "Very important", "Important", "Of minor importance", "Not important at all", "A",
     "In resource allocation decisions, clinical need and expected benefit are the central, ethically appropriate considerations — very important.", "Medium"),
    ("SJT", "Importance Ratings",
     "When deciding whether to challenge a senior colleague's instruction that seems unusual, how important is it to consider whether you have all the relevant clinical information the senior may have?",
     "Very important", "Important", "Of minor importance", "Not important at all", "A",
     "Senior colleagues may have context a junior lacks, so checking this before assuming an error is very important — though genuine safety concerns should still always be raised.", "Medium"),
    ("SJT", "Importance Ratings",
     "A student is preparing a presentation for a small teaching group. How important is it that the slides use an aesthetically pleasing colour scheme?",
     "Very important", "Important", "Of minor importance", "Not important at all", "C",
     "Visual appeal has minor relevance to the educational value of a teaching session compared with the accuracy and clarity of the content — of minor importance.", "Easy"),
    ("SJT", "Medical Ethics & Professionalism",
     "A 16-year-old patient requests a confidential consultation about contraception and asks that their parents not be informed. What is the most appropriate approach?",
     "Refuse to see the patient without a parent present",
     "Assess the patient's competence to consent and proceed confidentially if appropriate",
     "Inform the parents regardless of the patient's wishes",
     "Provide advice only if the patient promises to tell their parents", "B",
     "UK practice allows assessment of a young person's competence to consent to treatment independently (Gillick competence); if competent, confidentiality should generally be respected.", "Hard"),
    ("SJT", "Medical Ethics & Professionalism",
     "A doctor discovers a dosing error was made by a colleague, but the patient suffered no harm as a result. What is the most appropriate action?",
     "Say nothing since no harm occurred",
     "Report the error through the appropriate clinical governance channel so it can be reviewed and learned from",
     "Confront the colleague publicly on the ward",
     "Alter the patient's records to remove any trace of the error", "B",
     "Even harmless or near-miss errors should be reported through proper channels to support learning and prevent future harm — this reflects both patient safety and honesty duties. Altering records is a serious ethical breach.", "Medium"),
    ("SJT", "Medical Ethics & Professionalism",
     "A patient with capacity declines to have their family involved in discussions about their care, but a family member repeatedly asks the team for updates. What is the most appropriate response from the team?",
     "Share updates with the family to keep them informed",
     "Respect the patient's wishes and decline to share information with the family without consent",
     "Ask the patient to reconsider until they agree to involve the family",
     "Share limited details only, without telling the patient", "B",
     "A competent patient's expressed wish for confidentiality must be respected, even when family members request information.", "Medium"),
    ("SJT", "Medical Ethics & Professionalism",
     "A student is asked by a supervisor to perform a clinical task that is beyond their current level of training and for which they have not been signed off as competent. What is the most appropriate response?",
     "Attempt the task carefully to gain experience",
     "Refuse and explain they have not yet been assessed as competent to perform it unsupervised",
     "Ask a fellow student to do it instead",
     "Perform the task but tell no one afterward", "B",
     "Working within one's competence is a core professional duty; the student should be honest about their limitations rather than risk patient safety.", "Easy"),
    ("SJT", "Medical Ethics & Professionalism",
     "During a busy shift, a doctor realises they will not have time to fully document every patient interaction in as much detail as usual. What is the most appropriate approach to record-keeping in this situation?",
     "Skip documentation entirely until time allows, days later",
     "Record the key clinical information accurately and concisely for each patient, even if brief",
     "Copy the previous entry for each similar patient to save time",
     "Ask a colleague to guess and fill in the notes later", "B",
     "Concise but accurate documentation of key information maintains patient safety and legal/professional standards even under time pressure; skipping or fabricating records is not acceptable.", "Medium"),

    # ── Extended bank, round 2: additional exam-realistic questions ─────────
    # Verbal Reasoning
    ("VR", "Reading for the Main Idea",
     "Passage: \"Early clinical trials for the new anticoagulant showed promising results in reducing stroke risk, but the trials excluded patients over 75, the group most commonly prescribed such medication in practice.\" Which statement is best supported?",
     "The anticoagulant is unsafe for patients over 75",
     "The trial's findings may not generalise well to the patients who would most often receive the drug",
     "Patients over 75 do not experience strokes",
     "The trial found no reduction in stroke risk", "B",
     "The passage flags a mismatch between the trial population (excluding over-75s) and the group who would actually receive the drug in practice, supporting a generalisability concern. A, C and D are unsupported or contradicted.", "Medium"),
    ("VR", "Reading for the Main Idea",
     "Passage: \"Telemedicine appointments rose sharply during the pandemic and have remained above pre-pandemic levels since, though growth has slowed each year.\" Which statement is best supported?",
     "Telemedicine use is now falling below pre-pandemic levels",
     "Telemedicine use remains elevated compared to before the pandemic, even as its year-on-year growth has decelerated",
     "Telemedicine appointments will keep rising at the same rate indefinitely",
     "The pandemic had no lasting effect on telemedicine use", "B",
     "The passage directly states use has remained above pre-pandemic levels while growth has slowed — exactly B. A, C and D are contradicted.", "Easy"),
    ("VR", "Reading for the Main Idea",
     "Passage: \"Museum attendance figures often undercount actual visitor engagement, since many visitors now access collections online without ever recording a physical visit.\" Which statement is best supported?",
     "Online access has replaced physical museum visits entirely",
     "Official attendance figures may understate true public engagement with museum collections",
     "Museums no longer track online access",
     "Physical visits have increased due to online access", "B",
     "The passage directly claims attendance figures undercount engagement because online access goes unrecorded, supporting B. A, C and D are not stated.", "Easy"),
    ("VR", "Reading for the Main Idea",
     "Passage: \"The council's proposal to close the local clinic cited falling patient numbers, but the same report noted that a nearby GP surgery had recently expanded its catchment area, absorbing many of the clinic's former patients.\" Which statement is best supported?",
     "The clinic's falling numbers were entirely due to patient dissatisfaction",
     "Some of the apparent decline in patient numbers may reflect patients being redirected elsewhere rather than reduced overall demand",
     "The nearby GP surgery is now over capacity",
     "The council's proposal was based on inaccurate data", "B",
     "The passage's note about the nearby surgery absorbing patients offers an alternative explanation for the decline, supporting the more cautious claim in B rather than the stronger, unsupported claims in A, C and D.", "Hard"),
    ("VR", "Reading for the Main Idea",
     "Passage: \"Studies of sleep deprivation consistently find impaired reaction times, but the size of the effect varies considerably between individuals, with some showing little measurable change.\" Which statement is best supported?",
     "Sleep deprivation affects everyone equally",
     "The impact of sleep deprivation on reaction time differs from person to person",
     "Sleep deprivation has no effect on reaction time",
     "Reaction time cannot be measured accurately", "B",
     "Directly supported by \"varies considerably between individuals\". A and C are contradicted; D is unsupported.", "Easy"),
    ("VR", "Reading for the Main Idea",
     "Passage: \"The hospital's new triage system reduced average waiting times in the emergency department, but complaints about communication during the wait increased over the same period.\" Which statement is best supported?",
     "The new triage system was an unqualified success",
     "Faster processing under the new system did not necessarily improve patients' experience of the wait",
     "Complaints are unrelated to waiting times",
     "The hospital abandoned the new triage system", "B",
     "The passage shows two outcomes moving in different directions (shorter waits, more communication complaints), supporting the more nuanced reading in B rather than the unqualified success claimed in A.", "Medium"),
    ("VR", "Reading for the Main Idea",
     "Passage: \"Although the study found a correlation between screen time and reported anxiety in teenagers, the authors were careful to note that correlation alone cannot establish which factor, if either, causes the other.\" Which statement is best supported?",
     "Screen time causes anxiety in teenagers",
     "The study demonstrates that anxiety has no link to screen time",
     "The study's authors caution against concluding that screen time causes anxiety based on their findings alone",
     "Reducing screen time is proven to reduce anxiety", "C",
     "This directly reflects the authors' stated caution about correlation versus causation. A and D over-claim causation; B contradicts the finding of a correlation.", "Medium"),
    ("VR", "Reading for the Main Idea",
     "Passage: \"The new curriculum was introduced in only a third of schools this year, with a full rollout planned within five years; early results from participating schools are not yet available.\" Which statement is best supported?",
     "The new curriculum has already been shown to improve outcomes",
     "Only some schools have adopted the new curriculum so far, and its effects have not yet been assessed",
     "The curriculum will never be rolled out nationally",
     "Most schools rejected the new curriculum", "B",
     "Directly matches \"only a third...this year\" and \"results...not yet available\". A over-claims, since no results exist yet; C and D are contradicted or unsupported.", "Easy"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"The outpatient clinic sees adult patients only; children are referred to the paediatric unit across the road.\" Statement: \"A child would not be treated at the outpatient clinic.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "A",
     "The passage directly states the clinic sees adults only and refers children elsewhere, so the statement follows directly — True.", "Easy"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"The consultant's research team published three papers in 2023, all on cardiovascular topics.\" Statement: \"The consultant's team has never published on any topic other than cardiovascular disease.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "C",
     "The passage only describes the team's 2023 output; it says nothing about other years, so there isn't enough information to judge the broader claim — Can't tell.", "Medium"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"Staff must badge in and out of the secure medicines cupboard, and every entry is logged automatically.\" Statement: \"There is a record of every time the medicines cupboard was accessed.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "A",
     "Automatic logging of every entry directly means a record exists for every access — True.", "Easy"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"The hospital's car park has 200 spaces reserved for staff and 150 for visitors.\" Statement: \"The hospital's car park has more staff spaces than visitor spaces.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "A",
     "200 is greater than 150, so the statement is directly confirmed by the passage's own figures — True.", "Easy"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"The trial's second phase will begin once the first phase's safety data has been reviewed by the ethics board.\" Statement: \"The ethics board has already reviewed the first phase's safety data.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "C",
     "The passage describes a condition for phase two to begin but does not state whether that review has already taken place — Can't tell.", "Medium"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"Of the 40 students in the cohort, 25 chose a surgical elective and the rest chose a medical elective.\" Statement: \"Fewer than half the cohort chose a medical elective.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "A",
     "The medical elective group is 40 − 25 = 15 students, which is fewer than half of 40 (20), so the statement is confirmed — True.", "Medium"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"The new drug was approved for use in adults in 2022.\" Statement: \"The new drug is approved for use in children as of 2022.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "C",
     "The passage only states approval for adults; it neither confirms nor rules out approval for children, so there isn't enough information to judge — Can't tell.", "Medium"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"The morning shift runs from 7am to 3pm, and the afternoon shift from 3pm to 11pm.\" Statement: \"There is a shift that covers the hours between 11pm and 7am.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "C",
     "The passage names two shifts but never states that these are the only shifts that exist, so whether an overnight shift covers 11pm–7am cannot be determined — Can't tell.", "Hard"),
    ("VR", "True / False / Can't Tell",
     "Passage: \"Every applicant who scored above 650 in the aptitude test was invited to interview. Maya was invited to interview.\" Statement: \"Maya scored above 650 in the aptitude test.\" Based only on the passage, this statement is:",
     "True", "False", "Can't tell", "Partly true", "C",
     "The passage tells us scoring above 650 guarantees an invitation, but not that invitation only happens this way. Maya being invited does not confirm she scored above 650 — this is a classic converse-error trap. Can't tell.", "Hard"),
    ("VR", "Inference & Author Tone",
     "Passage: \"The minister's statement that 'lessons will be learned' has, by now, become a familiar refrain after every public inquiry — reassuring in theory, but rarely followed by any account of what actually changed.\" The author's tone is best described as:",
     "Approving", "Cynical", "Neutral", "Celebratory", "B",
     "Describing the phrase as a \"familiar refrain\" that is \"rarely followed by any account of what actually changed\" signals cynicism about the sincerity of such statements.", "Medium"),
    ("VR", "Inference & Author Tone",
     "Passage: \"Two independent audits reached the same conclusion: the department's spending was within budget, and no irregularities were found.\" Which inference is best supported?",
     "The department is known for financial mismanagement",
     "Independent confirmation from two audits strengthens confidence in the department's reported spending",
     "The audits were conducted by the same team",
     "No department has ever been found to overspend", "B",
     "Two independent audits reaching the same conclusion is exactly the kind of corroboration that strengthens confidence, supporting B. A, C and D are unsupported or contradicted — 'independent' implies not the same team.", "Easy"),
    ("VR", "Inference & Author Tone",
     "Passage: \"The reviewer praised the novel's ambition while noting, almost as an aside, that its final third 'rather loses its way.'\" Which inference about the reviewer's overall assessment is best supported?",
     "The reviewer disliked the novel entirely",
     "The reviewer's assessment is mixed, with praise tempered by a specific reservation",
     "The reviewer did not finish reading the novel",
     "The reviewer considered the ending the novel's strongest part", "B",
     "The review combines praise for ambition with a specific criticism of the ending, supporting a mixed assessment rather than outright dislike or unqualified praise.", "Medium"),
    ("VR", "Inference & Author Tone",
     "Passage: \"The spokesperson insisted the delay was 'purely a matter of logistics,' a claim that sat awkwardly alongside the company's earlier admission of a funding shortfall.\" Which inference is best supported?",
     "The spokesperson's explanation may not be the full story",
     "The delay was definitely caused by a funding shortfall",
     "The company has never had funding problems",
     "The spokesperson lied deliberately", "A",
     "The juxtaposition (\"sat awkwardly alongside\") invites doubt about whether logistics is the complete explanation, supporting the cautious inference in A rather than the stronger, unproven claims in B and D. C is directly contradicted.", "Hard"),
    ("VR", "Inference & Author Tone",
     "Passage: \"It would be an exaggeration to call the new policy a failure, but 'success' seems equally generous a word for something that met barely half its stated targets.\" The author's tone toward the policy is best described as:",
     "Enthusiastic", "Measured but unimpressed", "Outraged", "Fully supportive", "B",
     "The author explicitly avoids both 'failure' and 'success', landing on a measured, unimpressed assessment given the policy met only half its targets.", "Medium"),
    ("VR", "Inference & Author Tone",
     "Passage: \"The panel's report acknowledged the scheme's good intentions before spending the following forty pages detailing exactly how it failed to achieve them.\" Which inference is best supported?",
     "The panel's overall assessment of the scheme was critical, despite an initial acknowledgement of its aims",
     "The panel fully endorsed the scheme",
     "The scheme achieved all of its aims",
     "The report was only one page long", "A",
     "A brief acknowledgement of good intentions followed by extensive critical detail indicates the panel's substantive assessment was critical overall.", "Easy"),
    ("VR", "Inference & Author Tone",
     "Passage: \"Every member of staff who completed the training passed the subsequent assessment. Several members of staff did not complete the training.\" Which conclusion follows?",
     "All staff who did not complete the training failed the assessment",
     "We cannot determine the assessment outcome for staff who did not complete the training, based on this passage alone",
     "All staff passed the assessment",
     "The training had no effect on assessment outcomes", "B",
     "The passage only tells us about those who did complete training (they passed); it says nothing about outcomes for those who didn't, so A is an unsupported converse-error inference. B correctly reflects the limits of what is stated.", "Hard"),
    ("VR", "Inference & Author Tone",
     "Passage: \"The editorial conceded that the policy had some merit, immediately followed by three paragraphs explaining why it should be scrapped regardless.\" The author's tone is best described as:",
     "Grudgingly critical", "Wholly supportive", "Indifferent", "Celebratory", "A",
     "A brief concession of merit followed by sustained argument for scrapping the policy reflects a grudging, ultimately critical stance.", "Medium"),

    # Decision Making
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

    # Quantitative Reasoning
    ("QR", "Percentages & Percentage Change",
     "A hospital reduces its agency staffing costs from £180,000 to £126,000 per quarter. What is the percentage reduction?",
     "20%", "25%", "30%", "35%", "C",
     "Change = £54,000. Percentage reduction = 54,000 ÷ 180,000 × 100 = 30%.", "Easy"),
    ("QR", "Percentages & Percentage Change",
     "A patient's cholesterol level falls from 6.5 mmol/L to 5.2 mmol/L. What is the percentage decrease, to the nearest whole percent?",
     "15%", "18%", "20%", "24%", "C",
     "Change = 1.3 mmol/L. Percentage decrease = 1.3 ÷ 6.5 × 100 = 20%.", "Medium"),
    ("QR", "Percentages & Percentage Change",
     "A charity's donations increased by 40% this year to £210,000. What were donations last year?",
     "£126,000", "£147,000", "£150,000", "£168,000", "C",
     "Original × 1.4 = £210,000, so original = 210,000 ÷ 1.4 = £150,000.", "Medium"),
    ("QR", "Percentages & Percentage Change",
     "A store offers 20% off, and then an additional 10% off the already-discounted price at the till. What is the overall percentage discount from the original price?",
     "28%", "30%", "32%", "72%", "A",
     "0.8 × 0.9 = 0.72, meaning the customer pays 72% of the original price — an overall discount of 28%, not the simple sum of 20% and 10%.", "Hard"),
    ("QR", "Percentages & Percentage Change",
     "A drug trial found a 15% improvement rate in the treatment group compared to a 6% improvement rate in the placebo group. By how many percentage points did the treatment group's improvement rate exceed the placebo group's?",
     "6", "9", "15", "21", "B",
     "15 − 6 = 9 percentage points.", "Easy"),
    ("QR", "Percentages & Percentage Change",
     "A clinic's patient list grows by 8% one year and then shrinks by 8% the following year. If it started with 2,500 patients, how many are on the list after the two years (to the nearest whole number)?",
     "2,484", "2,500", "2,516", "2,540", "A",
     "2,500 × 1.08 × 0.92 = 2,500 × 0.9936 = 2,484. A rise and an equal-percentage fall do not cancel out, since the fall applies to a larger base.", "Hard"),
    ("QR", "Ratios & Proportion",
     "A batch of 4,000 tablets weighing 500 mg each contains active ingredient and filler in the ratio 1:9 by weight. How much active ingredient is in the whole batch?",
     "100,000 mg", "150,000 mg", "200,000 mg", "250,000 mg", "C",
     "Total batch weight = 4,000 × 500 mg = 2,000,000 mg. Active ingredient = 1/10 of the total = 200,000 mg.", "Medium"),
    ("QR", "Ratios & Proportion",
     "Three clinics share a bulk order of masks in the ratio 4:5:6. If the smallest share is 800 masks, how many masks are in the total order?",
     "2,400", "2,800", "3,000", "3,200", "C",
     "The smallest ratio part (4) corresponds to 800, so 1 part = 200. Total parts = 4 + 5 + 6 = 15. Total = 200 × 15 = 3,000.", "Medium"),
    ("QR", "Ratios & Proportion",
     "A saline drip mixes concentrate and water in a ratio of 1:19. How many millilitres of concentrate are needed to make 2,000 ml of the mixture?",
     "50 ml", "100 ml", "105 ml", "200 ml", "B",
     "Total parts = 20. Concentrate = 1/20 × 2,000 ml = 100 ml.", "Easy"),
    ("QR", "Ratios & Proportion",
     "A recipe scaled for 10 people uses 1.5 kg of rice. How much rice is needed for 25 people, assuming direct proportion?",
     "3 kg", "3.5 kg", "3.75 kg", "4 kg", "C",
     "Rice per person = 1.5 ÷ 10 = 0.15 kg. For 25 people: 0.15 × 25 = 3.75 kg.", "Easy"),
    ("QR", "Ratios & Proportion",
     "Two investors put money into a project in the ratio 3:7 and share the £45,000 profit in the same ratio. How much more does the larger investor receive than the smaller one?",
     "£13,500", "£15,000", "£18,000", "£21,000", "C",
     "Total parts = 10, so each part = £4,500. The difference is (7 − 3) parts = 4 × £4,500 = £18,000.", "Hard"),
    ("QR", "Ratios & Proportion",
     "An alloy of 100 kg is made of copper and tin in the ratio 7:3. How much tin must be added to change the ratio of copper to tin to 7:5, assuming only tin is added?",
     "20 kg", "30 kg", "40 kg", "50 kg", "A",
     "The 100 kg alloy contains 70 kg copper and 30 kg tin. Copper stays fixed at 70 kg, so for copper:tin = 7:5, tin must become 70 × 5/7 = 50 kg. That requires adding 50 − 30 = 20 kg of tin.", "Hard"),
    ("QR", "Speed, Distance & Time",
     "A delivery van travels 84 km in 1 hour 45 minutes. What is its average speed in km/h?",
     "42 km/h", "46 km/h", "48 km/h", "52 km/h", "C",
     "1 hour 45 minutes = 1.75 hours. Speed = 84 ÷ 1.75 = 48 km/h.", "Medium"),
    ("QR", "Speed, Distance & Time",
     "A patient is driven to hospital, covering the first half of a 60 km journey at 30 km/h and the second half at 60 km/h. How long does the journey take in total?",
     "1 hour", "1.25 hours", "1.5 hours", "2 hours", "C",
     "Each half is 30 km. Time for the first half = 30 ÷ 30 = 1 hour; second half = 30 ÷ 60 = 0.5 hours. Total = 1.5 hours.", "Medium"),
    ("QR", "Speed, Distance & Time",
     "A cyclist covers 45 km at an average speed of 18 km/h. To complete the same distance in 2 hours instead, by how much must they increase their average speed?",
     "3 km/h", "4 km/h", "4.5 km/h", "5 km/h", "C",
     "Desired speed = 45 ÷ 2 = 22.5 km/h. Increase = 22.5 − 18 = 4.5 km/h.", "Hard"),
    ("QR", "Speed, Distance & Time",
     "Two runners start at the same point and run in opposite directions, one at 9 km/h and the other at 11 km/h. After how many minutes will they be 5 km apart?",
     "10 minutes", "12 minutes", "15 minutes", "20 minutes", "C",
     "Combined separating speed = 20 km/h. Time = 5 ÷ 20 hours = 0.25 hours = 15 minutes.", "Medium"),
    ("QR", "Speed, Distance & Time",
     "A train covers 300 km at a constant speed. If it had travelled 10 km/h faster, the journey would have taken 1 hour less. What is the train's actual speed?",
     "40 km/h", "45 km/h", "50 km/h", "60 km/h", "C",
     "Solving 300/s − 300/(s+10) = 1 gives s² + 10s − 3,000 = 0, so s = 50 km/h. Check: 300÷50 = 6 hours; 300÷60 = 5 hours — exactly 1 hour less.", "Hard"),
    ("QR", "Speed, Distance & Time",
     "A boat travels 24 km downstream in 2 hours and the same 24 km upstream in 3 hours. What is the speed of the boat in still water?",
     "8 km/h", "9 km/h", "10 km/h", "12 km/h", "C",
     "Downstream speed = 24 ÷ 2 = 12 km/h (boat + current). Upstream speed = 24 ÷ 3 = 8 km/h (boat − current). Adding the two equations: 2 × boat speed = 20, so boat speed = 10 km/h.", "Hard"),
    ("QR", "Tables, Charts & Data",
     "A table shows quarterly sales of a clinic's home-testing kits: Q1: 400, Q2: 550, Q3: 620, Q4: 480. What is the average quarterly sales figure for the year?",
     "500", "505", "512.5", "520", "C",
     "Sum = 400 + 550 + 620 + 480 = 2,050. Average = 2,050 ÷ 4 = 512.5.", "Easy"),
    ("QR", "Tables, Charts & Data",
     "A chart shows a hospital's bed occupancy rates: Medical ward 92%, Surgical ward 85%, Paediatric ward 78%. If the Medical ward has 150 beds, how many are occupied?",
     "128", "132", "135", "138", "D",
     "92% of 150 = 138.", "Easy"),
    ("QR", "Tables, Charts & Data",
     "A table of a clinical trial's dropout rates shows 12% of 250 participants withdrew in month 1, and a further 10% of the remaining participants withdrew in month 2. How many participants remained after month 2?",
     "190", "195", "198", "200", "C",
     "Month 1: 12% of 250 = 30 withdraw, leaving 220. Month 2: 10% of 220 = 22 withdraw, leaving 198.", "Hard"),
    ("QR", "Tables, Charts & Data",
     "A bar chart shows A&E attendances by hour: 8am: 20, 12pm: 35, 4pm: 50, 8pm: 45, 12am: 15. What percentage of the day's shown attendances occurred at 4pm, to the nearest whole percent?",
     "25%", "28%", "30%", "33%", "C",
     "Total = 20 + 35 + 50 + 45 + 15 = 165. 4pm share = 50 ÷ 165 × 100 ≈ 30.3%, which rounds to 30%.", "Medium"),
    ("QR", "Tables, Charts & Data",
     "A table shows a drug costs £45 per box of 30 tablets, or £80 per box of 60 tablets. Which option is cheaper per tablet, and by roughly how much?",
     "Box of 30, by £0.17", "Box of 60, by £0.17", "Box of 60, by £0.20", "They cost the same per tablet", "B",
     "Box of 30: £45 ÷ 30 = £1.50 per tablet. Box of 60: £80 ÷ 60 ≈ £1.33 per tablet — cheaper by about £0.17 per tablet.", "Medium"),
    ("QR", "Tables, Charts & Data",
     "A table shows the pass rates for a professional exam over three years: 2021: 68%, 2022: 74%, 2023: 71%. If 400 people sat the exam in 2023, how many passed?",
     "274", "280", "284", "290", "C",
     "71% of 400 = 284.", "Easy"),
    ("QR", "Tables, Charts & Data",
     "A pie chart shows a survey of 240 people's preferred appointment time: 25% morning, 45% afternoon, and the remainder evening. How many more people preferred the afternoon than the evening?",
     "24", "30", "36", "42", "C",
     "Afternoon = 45% of 240 = 108. Evening share = 100% − 25% − 45% = 30%, so evening = 72. Difference = 108 − 72 = 36.", "Medium"),

    # Situational Judgement
    ("SJT", "Appropriateness Ratings",
     "A medical student is asked by a patient to keep information from the rest of the clinical team, information the student believes is relevant to the patient's safe care. How appropriate is it for the student to explain to the patient why the information needs to be shared with the team, while respecting the patient's concerns?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "A",
     "Explaining the clinical need for sharing safety-relevant information, while acknowledging the patient's concerns, balances safety and respect for the patient — very appropriate.", "Medium"),
    ("SJT", "Appropriateness Ratings",
     "A student is unsure how to perform a task correctly during a placement and, rather than asking, decides to guess based on what they've seen others do. How appropriate is this approach?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "D",
     "Guessing at an unfamiliar clinical task instead of asking for guidance risks patient safety and fails to work within one's competence — very inappropriate.", "Easy"),
    ("SJT", "Appropriateness Ratings",
     "During a group project, one team member has contributed significantly less than the others. How appropriate is it for another team member to raise this directly and constructively with the underperforming colleague before the deadline?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "A",
     "Addressing the issue directly and constructively, early enough to allow change, is a reasonable and professional response — very appropriate.", "Easy"),
    ("SJT", "Appropriateness Ratings",
     "A student on placement is offered a small gift by a grateful patient after a successful treatment. How appropriate is it for the student to politely decline, in line with their institution's gifts policy?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "A",
     "Following institutional policy on gifts protects professional boundaries and is the appropriate response, even when the gesture is well-intentioned.", "Medium"),
    ("SJT", "Appropriateness Ratings",
     "A medical student disagrees with how a nurse is managing a non-urgent situation but decides to raise it privately with the nurse afterwards rather than in front of the patient. How appropriate is this approach?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "A",
     "Raising a non-urgent concern privately, rather than undermining a colleague in front of a patient, is respectful and professional — very appropriate.", "Medium"),
    ("SJT", "Appropriateness Ratings",
     "A student, feeling unwell themselves, decides to attend a placement anyway without informing anyone, worried about seeming unreliable. How appropriate is this decision?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "D",
     "Attending a clinical placement while unwell without informing anyone risks spreading illness to vulnerable patients and staff — very inappropriate.", "Easy"),
    ("SJT", "Appropriateness Ratings",
     "A student notices that clinical equipment has not been cleaned according to protocol between patients, but is unsure whether it is their place to say something as the most junior person present. How appropriate is it for the student to point this out to a senior staff member?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "A",
     "Infection control lapses are a direct patient-safety issue; raising this with a senior, regardless of seniority, is very appropriate.", "Medium"),
    ("SJT", "Appropriateness Ratings",
     "A student is asked to complete an online training module and, pressed for time, considers clicking through the content without actually reading it. How appropriate is this approach?",
     "A very appropriate thing to do",
     "Appropriate, but not ideal",
     "Inappropriate, but not awful",
     "A very inappropriate thing to do", "C",
     "While not a direct patient-safety breach, skipping mandatory training content undermines its purpose and reflects poorly on professionalism — inappropriate, but not awful given no immediate harm occurs.", "Hard"),
    ("SJT", "Importance Ratings",
     "A team is planning how to break bad news to a patient. How important is it to consider the patient's preferences for how much detail they want to receive?",
     "Very important", "Important", "Of minor importance", "Not important at all", "A",
     "Respecting individual patient preferences in communication, especially around difficult news, is central to patient-centred care — very important.", "Easy"),
    ("SJT", "Importance Ratings",
     "When deciding the order in which to see patients in a busy clinic, how important is it to consider clinical urgency over arrival time?",
     "Very important", "Important", "Of minor importance", "Not important at all", "A",
     "Prioritising by clinical urgency rather than arrival order directly protects patient safety — very important.", "Easy"),
    ("SJT", "Importance Ratings",
     "A student is choosing which elective placement to apply for. How important is it to consider which placement will look most impressive on their CV, compared with which will offer the most valuable learning experience?",
     "Very important", "Important", "Of minor importance", "Not important at all", "C",
     "While not irrelevant, CV impressiveness is a much less important consideration than the genuine educational value of a placement — of minor importance.", "Medium"),
    ("SJT", "Importance Ratings",
     "A doctor is deciding whether to involve a translator in a consultation with a patient who has limited English proficiency. How important is it to arrange appropriate translation support?",
     "Very important", "Important", "Of minor importance", "Not important at all", "A",
     "Effective communication is essential for informed consent and safe care; arranging proper translation support is very important.", "Easy"),
    ("SJT", "Importance Ratings",
     "A student is deciding whether to disclose a minor personal conflict of interest before taking part in a research project. How important is it to disclose this, even if the student believes it won't affect their objectivity?",
     "Very important", "Important", "Of minor importance", "Not important at all", "A",
     "Transparency about conflicts of interest is a core aspect of research integrity, regardless of the individual's own belief about their objectivity — very important.", "Medium"),
    ("SJT", "Importance Ratings",
     "When writing a discharge summary, how important is it to use language the patient's next healthcare provider will clearly understand, avoiding unnecessary abbreviations?",
     "Very important", "Important", "Of minor importance", "Not important at all", "A",
     "Clear, unambiguous communication in medical records directly supports continuity of safe care — very important.", "Medium"),
    ("SJT", "Importance Ratings",
     "A student is deciding how to spend a free hour during a placement. How important is it that they use the time productively rather than on their phone?",
     "Very important", "Important", "Of minor importance", "Not important at all", "C",
     "While good use of time is generally positive, how a student spends a single free hour is a relatively minor professionalism consideration compared with core clinical and ethical duties — of minor importance.", "Hard"),
    ("SJT", "Importance Ratings",
     "A consultant is deciding how to respond to a junior colleague who made a reasonable clinical decision that, in hindsight, did not lead to the best outcome. How important is it to distinguish between a reasonable decision with a poor outcome and an actual error in judgement?",
     "Very important", "Important", "Of minor importance", "Not important at all", "A",
     "Fairly distinguishing bad outcomes from bad decisions supports a just culture and appropriate learning, rather than unfairly blaming reasonable clinical judgement — very important.", "Hard"),
    ("SJT", "Importance Ratings",
     "A team is deciding whether to proceed with a planned but non-urgent procedure on a day when the department is significantly understaffed. How important is it to consider whether adequate staffing is in place to do the procedure safely?",
     "Very important", "Important", "Of minor importance", "Not important at all", "A",
     "Safe staffing levels are directly tied to patient safety during any procedure, making this a very important consideration before proceeding.", "Easy"),
    ("SJT", "Medical Ethics & Professionalism",
     "A patient lacking capacity to consent requires an urgent, life-saving procedure, and no family members can be reached in time. What is the most appropriate course of action?",
     "Delay the procedure until a family member can be contacted",
     "Proceed with the procedure in the patient's best interests, in line with capacity legislation",
     "Refuse to treat until formal consent is obtained",
     "Ask another patient's family to make the decision", "B",
     "When a patient lacks capacity and treatment is urgent, proceeding in their best interests under relevant capacity law is the appropriate approach, rather than risking harm through delay.", "Medium"),
    ("SJT", "Medical Ethics & Professionalism",
     "A doctor is asked by a patient to falsify a sick note for reasons unrelated to genuine illness. What is the most appropriate response?",
     "Comply with the request to maintain a good relationship with the patient",
     "Explain that they cannot issue a sick note that does not reflect a genuine medical assessment",
     "Issue the note but note privately that it was not genuine",
     "Refer the patient to another doctor to make the request instead", "B",
     "Issuing a false medical certificate is a serious breach of honesty and professional integrity; the appropriate response is to decline and explain why.", "Easy"),
    ("SJT", "Medical Ethics & Professionalism",
     "A trainee overhears a colleague making an inappropriate comment about a patient's weight within earshot of other patients. What is the most appropriate action?",
     "Ignore it, as it is a minor issue",
     "Address it directly and respectfully with the colleague, and consider raising it further if it recurs",
     "Report the colleague to hospital management immediately without speaking to them first",
     "Repeat the comment to others as a joke", "B",
     "A proportionate first response is to address unprofessional conduct directly and respectfully, escalating only if needed — this supports both patient dignity and fair treatment of the colleague.", "Medium"),
    ("SJT", "Medical Ethics & Professionalism",
     "A researcher finds that a small subset of their data does not support their hypothesis. What is the most appropriate approach to reporting their results?",
     "Exclude the inconvenient data without disclosure to strengthen the paper's conclusions",
     "Report all the data honestly, including findings that do not support the hypothesis",
     "Adjust the data slightly so it better fits the expected pattern",
     "Delay publication indefinitely to avoid reporting negative findings", "B",
     "Research integrity requires honest and complete reporting of findings, including results that do not support the researcher's hypothesis.", "Easy"),
    ("SJT", "Medical Ethics & Professionalism",
     "A patient asks a medical student to explain their diagnosis in more detail than the treating doctor has so far provided. What is the most appropriate response?",
     "Provide a full detailed explanation based on the student's own understanding",
     "Explain what they can within their competence, and encourage the patient to discuss further details with the treating doctor",
     "Tell the patient to look up the diagnosis online",
     "Refuse to engage with the patient's question at all", "B",
     "Students should support patients within the limits of their training while directing more detailed clinical explanation to the responsible doctor — balancing helpfulness with working within competence.", "Medium"),
    ("SJT", "Medical Ethics & Professionalism",
     "A doctor notices that a colleague from a different specialty appears to be practising outside their area of expertise on a complex case. What is the most appropriate first step?",
     "Say nothing, as it is not the doctor's specialty either",
     "Raise the concern directly and constructively with the colleague or, if appropriate, their supervisor",
     "Take over the case without discussion",
     "Discuss the concern with other colleagues informally, without involving the colleague concerned", "B",
     "Concerns about a colleague practising outside their competence should be raised directly and constructively through appropriate channels, prioritising patient safety.", "Medium"),
    ("SJT", "Medical Ethics & Professionalism",
     "A patient with capacity is considering a treatment option that a doctor believes is not in their best clinical interest. What is the most appropriate approach?",
     "Refuse to proceed unless the patient chooses the doctor's preferred option",
     "Provide balanced information about the risks and benefits of all options and respect the patient's final, informed decision",
     "Withhold information about alternative options to steer the patient toward the doctor's preferred choice",
     "Ask a family member to persuade the patient instead", "B",
     "Respecting patient autonomy means providing full, balanced information and respecting a competent patient's informed decision, even if it differs from the doctor's own recommendation.", "Medium"),
    ("SJT", "Medical Ethics & Professionalism",
     "A student is asked to assist with a procedure they have some training in but have never performed unsupervised. What is the most appropriate approach?",
     "Perform the procedure alone to build confidence",
     "Ask for appropriate supervision before performing the procedure, consistent with their training level",
     "Decline to have anything to do with the procedure at all",
     "Ask a friend outside the clinical team for advice on how to do it", "B",
     "Requesting appropriate supervision matches the level of the student's training and experience, balancing patient safety with legitimate learning — declining entirely would be an overreaction given some relevant training exists.", "Hard"),
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


def seed_content():
    """Idempotently load the starter MCAT content the first time the app runs."""
    existing = get_subjects()
    if existing:
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
        # Questions
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

        # Questions — insert any whose stem is not already present
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
    finally:
        _close(conn)
    return {"topics_added": added_t, "questions_added": added_q, "flashcards_added": added_f}
