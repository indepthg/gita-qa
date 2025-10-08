# app/migrate.py
import os, sqlite3

DB_PATH = os.environ.get("DB_PATH", "/data/gita.db")

SCHEMA_SQL = r"""
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY,
  micro_topic_id INTEGER NOT NULL,
  intent TEXT DEFAULT 'general',
  priority INTEGER DEFAULT 5,
  source TEXT DEFAULT 'seed',
  question_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS answers (
  id INTEGER PRIMARY KEY,
  question_id INTEGER NOT NULL,
  length_tier TEXT CHECK(length_tier IN ('short','medium','long')) NOT NULL,
  answer_text TEXT NOT NULL,
  UNIQUE(question_id, length_tier),
  FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
);

/* Optional: simple keyword alias table to help matching (fallback) */
CREATE TABLE IF NOT EXISTS question_aliases (
  id INTEGER PRIMARY KEY,
  question_id INTEGER NOT NULL,
  alias TEXT NOT NULL,
  UNIQUE(question_id, alias),
  FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
);

/* FTS5 on questions: */
CREATE VIRTUAL TABLE IF NOT EXISTS questions_fts
USING fts5(
  question_text,
  intent UNINDEXED,
  source UNINDEXED,
  content='questions',
  content_rowid='id'
);

/* Triggers to keep FTS in sync */
CREATE TRIGGER IF NOT EXISTS questions_ai AFTER INSERT ON questions BEGIN
  INSERT INTO questions_fts(rowid, question_text, intent, source)
  VALUES (new.id, new.question_text, new.intent, new.source);
END;
CREATE TRIGGER IF NOT EXISTS questions_ad AFTER DELETE ON questions BEGIN
  INSERT INTO questions_fts(questions_fts, rowid, question_text, intent, source)
  VALUES('delete', old.id, old.question_text, old.intent, old.source);
END;
CREATE TRIGGER IF NOT EXISTS questions_au AFTER UPDATE ON questions BEGIN
  INSERT INTO questions_fts(questions_fts, rowid, question_text, intent, source)
  VALUES('delete', old.id, old.question_text, old.intent, old.source);
  INSERT INTO questions_fts(rowid, question_text, intent, source)
  VALUES (new.id, new.question_text, new.intent, new.source);
END;
"""

REBUILD_FTS = "INSERT INTO questions_fts(questions_fts) VALUES('rebuild');"

ALIASES = [
  # map common phrasings to the surrender canonical
  ("What does the Gītā mean by surrender to the Lord?", [
    "what is surrender in the gita",
    "what does the gita say about surrender",
    "surrender to krishna",
    "saranagati",
  ]),
  ("What is a sthita-prajña in the Bhagavad Gītā?", [
    "sthita prajna",
    "what is sthitaprajna",
    "marks of sthita prajna",
  ]),
]

def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript(SCHEMA_SQL)

    # Populate aliases for existing canonical questions (best-effort)
    for qtext, alias_list in ALIASES:
        row = cur.execute("SELECT id FROM questions WHERE question_text=?", (qtext,)).fetchone()
        if not row: 
            continue
        qid = row[0]
        for alias in alias_list:
            try:
                cur.execute("INSERT OR IGNORE INTO question_aliases(question_id, alias) VALUES(?, ?)", (qid, alias))
            except Exception:
                pass

    # Rebuild FTS to reflect current questions content
    try:
        cur.execute(REBUILD_FTS)
    except Exception:
        pass

    con.commit()
    con.close()
    print(f"[migrate] schema ensured at {DB_PATH}")

if __name__ == "__main__":
    main()
