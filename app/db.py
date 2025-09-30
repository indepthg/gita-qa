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

def search_fts(conn: sqlite3.Connection, q: str, limit: int = 10) -> List[sqlite3.Row]:
    q2 = _fts_sanitize(q)
    if not q2:
        return []

    # If the user didn't specify operators, convert the sentence to a keyword OR query.
    has_ops = bool(re.search(r'(?:"|\\bOR\\b|\\bAND\\b|\\bNOT\\b|\\bNEAR/\\d+\\b|\\bNEAR\\b)', q2))
    if not has_ops:
        # very small English stoplist to drop unhelpful terms
        STOP = {
            "the","a","an","and","or","of","to","in","on","for","with","by","about",
            "what","which","who","whom","is","are","was","were","be","been","being",
            "that","this","these","those","do","does","did","from","as","at","it",
            "verse", "verses", "mention", "mentions", "talk", "talks", "about", "on",
            "into","over","under","between","among","how","why","when","where","vs","versus","talk","talks"
        }
        toks = re.findall(r'\\w+', q2, flags=re.UNICODE)
        keywords = [t for t in toks if len(t) >= 4 and t.lower() not in STOP]
        # If nothing survives, fall back to the original
        if keywords:
            q2 = " OR ".join(dict.fromkeys(keywords))

    # Safely inline as SQL literal (escape single quotes)
    q_lit = "'" + q2.replace("'", "''") + "'"

    sql = f"""
        SELECT v.*
        FROM verses_fts
        JOIN verses AS v ON v.rowid = verses_fts.rowid
        WHERE verses_fts MATCH {q_lit}
        LIMIT ?
    """
    cur = conn.execute(sql, (limit,))
    return cur.fetchall()


def stats(conn: sqlite3.Connection) -> Dict[str, int]:
    v = conn.execute("SELECT COUNT(1) AS c FROM verses").fetchone()["c"]
    return {"verses": v}
