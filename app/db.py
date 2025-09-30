import os
import re
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

# ---------- FTS helpers ----------

import re

# allow ALL unicode letters/digits (via \w), spaces, and common FTS operators/symbols
# keeps diacritics like ñ, ā, ī, ṇ, etc. because \w is unicode-aware
_FTS_SAFE = re.compile(r"[^\w\s:\"'\-\(\)\/\.\*\+\|]", flags=re.UNICODE)

def _fts_sanitize(q: str) -> str:
    q = (q or "").strip()
    if not q:
        return ""
    # Uppercase boolean operators so FTS recognizes them
    q = re.sub(r"\b(or|and|not|near)\b", lambda m: m.group(1).upper(), q, flags=re.IGNORECASE)
    # Remove only disallowed characters (preserves diacritics)
    q = _FTS_SAFE.sub(" ", q)
    # Collapse whitespace
    q = re.sub(r"\s+", " ", q).strip()
    return q


def ensure_fts(conn: sqlite3.Connection) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(verses)").fetchall()]
    fts_cols = ["title", "translation", "word_meanings", "roman", "colloquial"]
    for c in ("commentary1", "commentary2", "commentary3"):
        if c in cols:
            fts_cols.append(c)

    conn.execute("DROP TABLE IF EXISTS verses_fts")
    col_defs = ",\n  ".join(fts_cols)
    conn.execute(f"CREATE VIRTUAL TABLE verses_fts USING fts5(\n  {col_defs},\n  content='',\n  tokenize='unicode61 remove_diacritics 2'\n)")

    col_csv = ",".join(fts_cols)
    conn.execute(f"INSERT INTO verses_fts(rowid,{col_csv}) SELECT rowid,{col_csv} FROM verses")
    conn.commit()

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

STOP = {
    "the","a","an","and","or","of","to","in","on","for","with","by","about",
    "what","which","who","whom","is","are","was","were","be","been","being",
    "that","this","these","those","do","does","did","from","as","at","it",
    "verse","verses","mention","mentions","talk","talks",
    "into","over","under","between","among","how","why","when","where",
    "vs","versus"
}

def search_fts(conn: sqlite3.Connection, q: str, limit: int = 10) -> List[sqlite3.Row]:
    """
    Run a sanitized full-text search against verses_fts.
    Removes common stop words, but preserves important Sanskrit/English tokens.
    """
    tokens = [tok for tok in re.split(r"\W+", q.lower()) if tok and tok not in STOP]
    q2 = " ".join(tokens) if tokens else q.lower().strip()

    # Debug output to Railway logs
    print(f"[DEBUG search_fts] user={q!r} → fts_query={q2!r}, limit={limit}", flush=True)

    cur = conn.execute(
        "SELECT v.* FROM verses_fts f JOIN verses v ON v.rowid=f.rowid WHERE verses_fts MATCH ? LIMIT ?",
        (q2, limit),
    )
    return cur.fetchall()



def stats(conn: sqlite3.Connection) -> Dict[str, int]:
    v = conn.execute("SELECT COUNT(1) AS c FROM verses").fetchone()["c"]
    return {"verses": v}
