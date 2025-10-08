# app/migrate.py
import os, sqlite3

DB_PATH = os.environ.get("DB_PATH", "/data/gita.db")

SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  micro_topic_id INTEGER NOT NULL,  -- use your IDs; e.g., 1001=Surrender, 1002=Sthita-prajña
  question_text TEXT NOT NULL,
  intent TEXT,
  priority INTEGER DEFAULT 1,
  source TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS answers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id INTEGER NOT NULL,     -- FK to questions.id
  length_tier TEXT NOT NULL,        -- 'short' | 'medium' | 'long'
  answer_text TEXT NOT NULL,        -- HTML/text
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_questions_microtopic ON questions(micro_topic_id);
CREATE INDEX IF NOT EXISTS idx_answers_question ON answers(question_id);
"""

def main():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SQL)
    con.commit()
    con.close()
    print(f"[migrate] schema ensured at {DB_PATH}")

if __name__ == "__main__":
    main()
