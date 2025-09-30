
import os
import sqlite3
from typing import Any, Dict, Iterable, List, Optional

# New DB path will be set via env var in Railway. Default stays under /data.
DB_PATH = os.getenv("DB_PATH", os.path.join(os.getenv("DATA_DIR", "/data"), "gita.db"))

def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Base schema: includes commentary1/2/3 so we can index them in FTS
SCHEMA_SQL = r"""
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS verses (
  id INTEGER PRIMARY KEY,              -- not required, but handy; rowid still used for FTS joins
  rownum INTEGER,
  audio_id TEXT,
  chapter INTEGER NOT NULL,
  verse INTEGER NOT NULL,
  sanskrit TEXT,
  roman TEXT,
  colloquial TEXT,
  translation TEXT,
  commentary1 TEXT,
  commentary2 TEXT,
  commentary3 TEXT,
  capsule_url TEXT,
  word_meanings TEXT,
  title TEXT,
  UNIQUE(chapter, verse)
);
"""

def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Create base table and ensure a fresh, contentless FTS index (no triggers).
    Safe to run on every boot. For old DBs with legacy triggers, switch to a new DB filename.
    """
    close_after = False
    if conn is None:
        conn = get_conn()
        close_after = True
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        ensure_fts(conn)
    finally:
        if close_after:
            conn.close()

import re

# allow letters/digits/space and common FTS operators/symbols
_FTS_SAFE = re.compile(r"[^A-Za-z0-9\s:\"'\-\(\)\/\.\*\+\|]")

def _fts_sanitize(q: str) -> str:
    q = (q or "").strip()
    if not q:
        return ""
    # Uppercase boolean operators (optional)
    q = re.sub(r"\b(or|and|not|near)\b", lambda m: m.group(1).upper(), q, flags=re.IGNORECASE)
    # Remove unsafe chars
    q = _FTS_SAFE.sub(" ", q)
    # Collapse whitespace
    q = re.sub(r"\s+", " ", q).strip()
    return q

def search_fts(conn: sqlite3.Connection, q: str, limit: int = 10) -> List[sqlite3.Row]:
    q2 = _fts_sanitize(q)
    if not q2:
        return []
    # IMPORTANT: inline sanitized query because this SQLite build rejects MATCH parameters
    sql = f"""
        SELECT v.*
        FROM verses_fts
        JOIN verses AS v ON v.rowid = verses_fts.rowid
        WHERE verses_fts MATCH {sqlite3.escape_string(q2).decode() if hasattr(sqlite3, 'escape_string') else "'" + q2.replace("'", "''") + "'"}
        LIMIT ?
    """
    cur = conn.execute(sql, (limit,))
    return cur.fetchall()


def upsert_verse(conn: sqlite3.Connection, row: Dict[str, Any]) -> None:
    sql = (
        "INSERT INTO verses (rownum,audio_id,chapter,verse,sanskrit,roman,colloquial,translation,commentary1,commentary2,commentary3,capsule_url,word_meanings,title) "
        "VALUES (:rownum,:audio_id,:chapter,:verse,:sanskrit,:roman,:colloquial,:translation,:commentary1,:commentary2,:commentary3,:capsule_url,:word_meanings,:title) "
        "ON CONFLICT(chapter,verse) DO UPDATE SET "
        "rownum=excluded.rownum,audio_id=excluded.audio_id,sanskrit=excluded.sanskrit,roman=excluded.roman,"
        "colloquial=excluded.colloquial,translation=excluded.translation,"
        "commentary1=excluded.commentary1,commentary2=excluded.commentary2,commentary3=excluded.commentary3,"
        "capsule_url=excluded.capsule_url,word_meanings=excluded.word_meanings,title=excluded.title;"
    )
    conn.execute(sql, row)

def bulk_upsert(conn: sqlite3.Connection, rows: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for r in rows:
        # ensure keys exist for commentary fields even if missing in CSV
        r.setdefault("commentary1", "")
        r.setdefault("commentary2", "")
        r.setdefault("commentary3", "")
        upsert_verse(conn, r)
        count += 1
    conn.commit()
    return count

def fetch_exact(conn: sqlite3.Connection, chap: int, ver: int) -> Optional[sqlite3.Row]:
    cur = conn.execute("SELECT * FROM verses WHERE chapter=? AND verse=?", (chap, ver))
    return cur.fetchone()

def fetch_neighbors(conn: sqlite3.Connection, chap: int, ver: int, k: int = 1) -> List[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM verses WHERE chapter=? AND verse BETWEEN ? AND ? ORDER BY verse ASC",
        (chap, max(1, ver - k), ver + k),
    )
    return [r for r in cur.fetchall() if int(r["verse"]) != ver]

def search_fts(conn: sqlite3.Connection, q: str, limit: int = 10) -> List[sqlite3.Row]:
    """
    Allow FTS operators while keeping a parameterized query.
    Trick: concatenate with an empty string so MATCH sees a literal string,
    but we don't force quotes (so OR/NEAR/NOT still work).
    """
    q = (q or "").strip()
    if not q:
        return []
    cur = conn.execute(
        """
        SELECT v.*
        FROM verses_fts
        JOIN verses AS v ON v.rowid = verses_fts.rowid
        WHERE verses_fts MATCH ('' || ?)
        LIMIT ?
        """,
        (q, limit),
    )
    return cur.fetchall()

def stats(conn: sqlite3.Connection) -> Dict[str, int]:
    v = conn.execute("SELECT COUNT(1) AS c FROM verses").fetchone()["c"]
    return {"verses": v}
