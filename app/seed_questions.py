# app/seed_questions.py
import os, sqlite3

DB_PATH = os.environ.get("DB_PATH", "/data/gita.db")

SEED = [
  # Surrender / Refuge (śaraṇāgati) — 18.66, 9.22, 9.31–32
  (1001, "What does the Gītā mean by surrender to the Lord?", "definition", 1, "generated"),
  (1001, "Why is surrender central in the Gītā?",              "why",        1, "generated"),
  (1001, "How can one practice surrender in daily life?",      "practice",   2, "generated"),
  (1001, "Which verses teach about surrender?",                "verses_only",1, "generated"),

  # Sthita-prajña (2.54–72)
  (1002, "What is a sthita-prajña in the Bhagavad Gītā?",      "definition", 1, "generated"),
  (1002, "What are the main qualities of a sthita-prajña?",    "list",       1, "generated"),
  (1002, "Where does the Gītā describe the sthita-prajña?",    "verses_only",1, "generated"),
]

UPSERT = """
INSERT INTO questions (micro_topic_id, question_text, intent, priority, source)
SELECT ?, ?, ?, ?, ?
WHERE NOT EXISTS (
  SELECT 1 FROM questions
  WHERE micro_topic_id = ? AND question_text = ?
);
"""

def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    for micro_id, text, intent, prio, src in SEED:
        cur.execute(UPSERT, (micro_id, text, intent, prio, src, micro_id, text))
    con.commit()
    print(f"[seed_questions] inserted/kept {len(SEED)} rows")
    # Optional: show what got inserted
    for row in cur.execute("SELECT id, micro_topic_id, question_text FROM questions ORDER BY id"):
        print(row)
    con.close()

if __name__ == "__main__":
    main()
