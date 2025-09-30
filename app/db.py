
import os
import sqlite3
from typing import Any, Dict, Iterable, List, Optional

DB_PATH = os.getenv("DB_PATH", os.path.join(os.getenv("DATA_DIR", "/data"), "gita.db"))

def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

SCHEMA_SQL = r"""
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS verses (
  id INTEGER PRIMARY KEY,
  rownum INTEGER,
  audio_id TEXT,
  chapter INTEGER NOT NULL,
  verse INTEGER NOT NULL,
  sanskrit TEXT,
  roman TEXT,
  colloquial TEXT,
  translation TEXT,
  capsule_url TEXT,
  word_meanings TEXT,
  title TEXT,
  UNIQUE(chapter, verse)
);
"""

def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
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

def ensure_fts(conn: sqlite3.Connection) -> None:
    # Drop and rebuild FTS from current verses (no triggers used)
    conn.executescript("""
    DROP TABLE IF EXISTS verses_fts;
    CREATE VIRTUAL TABLE verses_fts USING fts5(
      title,
      translation,
      word_meanings,
      roman,
      colloquial,
      content='',
      tokenize='unicode61'
    );
    """)
    # Populate from verses (use rowid to be schema-agnostic)
    conn.execute("""
    INSERT INTO verses_fts(rowid,title,translation,word_meanings,roman,colloquial)
    SELECT rowid, title, translation, word_meanings, roman, colloquial FROM verses
    """)
    conn.commit()


def upsert_verse(conn: sqlite3.Connection, row: Dict[str, Any]) -> None:
    sql = (
        "INSERT INTO verses (rownum,audio_id,chapter,verse,sanskrit,roman,colloquial,translation,capsule_url,word_meanings,title) "
        "VALUES (:rownum,:audio_id,:chapter,:verse,:sanskrit,:roman,:colloquial,:translation,:capsule_url,:word_meanings,:title) "
        "ON CONFLICT(chapter,verse) DO UPDATE SET "
        "rownum=excluded.rownum,audio_id=excluded.audio_id,sanskrit=excluded.sanskrit,roman=excluded.roman,"
        "colloquial=excluded.colloquial,translation=excluded.translation,capsule_url=excluded.capsule_url,"
        "word_meanings=excluded.word_meanings,title=excluded.title;"
    )
    conn.execute(sql, row)

def bulk_upsert(conn: sqlite3.Connection, rows: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for r in rows:
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
    cur = conn.execute(
        "SELECT v.* FROM verses_fts f JOIN verses v ON v.id=f.rowid WHERE verses_fts MATCH ? LIMIT ?",
        (q, limit),
    )
    return cur.fetchall()

def stats(conn: sqlite3.Connection) -> Dict[str, int]:
    v = conn.execute("SELECT COUNT(1) AS c FROM verses").fetchone()["c"]
    return {"verses": v}
