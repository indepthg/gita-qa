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

-- Helpful index for joins/lookups
CREATE INDEX IF NOT EXISTS idx_answers_question_id ON answers(question_id);

-- Optional: simple keyword alias table to help matching (fallback)
CREATE TABLE IF NOT EXISTS question_aliases (
  id INTEGER PRIMARY KEY,
  question_id INTEGER NOT NULL,
  alias TEXT NOT NULL,
  UNIQUE(question_id, alias),
  FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
);

-- FTS5 on questions:
CREATE VIRTUAL TABLE IF NOT EXISTS questions_fts
USING fts5(
  question_text,
  intent UNINDEXED,
  source UNINDEXED,
  content='questions',
  content_rowid='id'
);

-- Triggers to keep FTS in sync
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

# ------------------------------------------------------------------
# Alias seeds (ASCII + diacritics variants -> map to canonical Q text)
# ------------------------------------------------------------------
ALIASES_MAP = {
  # Chapter 16: Divine / Demoniac
  "What are the divine qualities listed in Chapter 16?": [
    "daivi sampat","daivī sampat","daivi-sampat","daivī-sampat",
    "daivi qualities","daivī qualities","divine qualities","chapter 16 divine qualities"
  ],
  "What are the demoniac qualities listed in Chapter 16?": [
    "asuri sampat","āsurī sampat","asuri-sampat","āsurī-sampat",
    "asuri qualities","āsurī qualities","demonic qualities","chapter 16 demonic qualities"
  ],
  "What are divine and demoniac qualities?": [
    "daivi and asuri","daivī and āsurī","daivi vs asuri","daivī vs āsurī",
    "daivi asuri","daivī āsurī","asuric qualities"
  ],

  # Sthita-prajna
  "What is a sthita-prajna in the Gita?": [
    "sthita prajna","sthitaprajna","stitha prajna","sthita-prajna",
    "sthita prajña","sthita-prajña","sthita prajna meaning",
    "lakshanas of sthita prajna","marks of sthitaprajna"
  ],
  "What are the marks of a sthita-prajna?": [
    "lakshanas of sthita prajna","marks of sthitaprajna","sthita prajna qualities"
  ],
  "How does a sthita-prajna live?": [
    "life of sthitaprajna","sthita prajna behavior","sthita prajna conduct"
  ],

  # Surrender
  "What does the Gita say about surrender?": [
    "saranagati","śaraṇāgati","saranagathi","prapatti",
    "surrender to krishna","take refuge","take refuge in krishna",
    "sarva dharman parityajya","18.66 surrender"
  ],
  "How can one practice surrender according to the Gita?": [
    "how to surrender","ladder of practice","12.8 12.9 12.10 12.11 12.12 surrender"
  ],
  "Why is surrender central in the Gita?": [
    "why surrender","importance of surrender","centrality of surrender"
  ],

  # Bhakti
  "What is Bhakti (devotion) in the Gita?": [
    "bhakti","bhakthi","devotion","bhakti yoga","bhakti in gita",
    "9.26 leaf flower fruit water"
  ],
  "What are the qualities of a true devotee?": [
    "bhakta lakshanas","qualities of bhakta","12.13-20 devotee qualities"
  ],

  # Gunas
  "What are the three gunas?": [
    "gunas","guṇa","sattva rajas tamas","sattvic rajasic tamasic","three modes of nature",
    "guna theory gita","chapter 14 gunas"
  ],
  "How do the three gunas bind the soul?": [
    "how gunas bind","effects of gunas","guna bondage"
  ],
  "How can one rise beyond the gunas?": [
    "transcend gunas","go beyond gunas","14.26 bhakti beyond gunas"
  ],

  # Food
  "What food should I eat according to the Gita?": [
    "sattvic food","rajasic food","tamasic food","food in gita","gita diet","17.8 17.9 17.10 food"
  ],
  "How does food affect the mind in the Gita?": [
    "food and mind","diet and mind gita","food gunas"
  ],

  # Meditation / Mind
  "How does the Gita teach meditation?": [
    "dhyana","meditation posture","asana seat gita","meditation steps gita",
    "6.11 6.12 6.13 posture"
  ],
  "What posture and setting are recommended for meditation?": [
    "asana","seat posture","meditation seat","kusa grass","antelope skin"
  ],
  "How to steady the wandering mind?": [
    "restless mind","chanchala mana","6.26 mind","6.35 mind control"
  ],
  "Is the mind hard to control? What does Krishna say?": [
    "mind hard to control","mana durnigraha","arduous to control mind"
  ],

  # Karma Yoga
  "What is Karma Yoga?": [
    "nishkama karma","karma-yoga","selfless action","2.47 duty not fruits",
    "offer the fruits","karmayoga"
  ],
  "How to act without attachment to results?": [
    "without attachment to fruits","fruit of action","detachment in action"
  ],

  # Equanimity
  "What is equanimity (samatva) in the Gita?": [
    "samatvam","samatva","samatvam yoga ucyate","equipoise","2.48 equanimity"
  ],
  "How can I develop equanimity?": [
    "develop equanimity","cultivate equanimity","practise samatva"
  ],

  # Self / Atman
  "What does the Gita say about the Self (Atman)?": [
    "atman","ātman","self in gita","avinaashi tu tad viddhi","2.17 atman","na hanyate hanyamane sharire"
  ],
  "What is always real according to the Gita?": [
    "what is always real","2.16 2.17 real unreal","avinaashi tu tad viddhi"
  ],
  "How is the Self beyond harm?": [
    "weapons do not cut","2.23 self beyond harm","adahyah akledyah ashoshyah"
  ],
  "Why should one not grieve over death?": [
    "do not grieve over death","2.27 death certainty","janma mrityu"
  ],

  # Ladder of fall
  "What is the ladder of fall described in the Gita?": [
    "ladder of fall","2.62 2.63 ladder of fall","kama krodha ladder","attachment desire anger"
  ],
  "How do desire and anger lead to ruin?": [
    "desire anger ruin","kama krodha destruction","delusion memory loss ruin"
  ],

  # Vishvarupa
  "What is the universal form (Vishvarupa) in the Gita?": [
    "vishvarupa","vishwaroopa","virat rupa","11.32 time i am","krishna universal form"
  ],

  # OM / Pranava
  "What is the significance of OM in the Gita?": [
    "omkara","pranava","aum","8.13 om","17.23 om tat sat"
  ],

  # Three gates to hell
  "What are the three gates to hell?": [
    "three gates to hell","kama krodha lobha","16.21 gates to hell"
  ],
}

def seed_aliases(cur):
    inserted = 0
    for qtext, alias_list in ALIASES_MAP.items():
        row = cur.execute("SELECT id FROM questions WHERE question_text=?", (qtext,)).fetchone()
        if not row:
            continue  # canonical not present yet (ok)
        qid = row[0]
        for alias in alias_list:
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO question_aliases(question_id, alias) VALUES(?, ?)",
                    (qid, alias)
                )
                inserted += 1
            except Exception:
                pass
    return inserted

def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript(SCHEMA_SQL)

    # Seed selected aliases (safe, idempotent)
    ali = seed_aliases(cur)

    # Rebuild FTS to reflect current questions content (safe if table exists)
    try:
        cur.execute(REBUILD_FTS)
    except Exception:
        pass

    con.commit()
    con.close()
    print(f"[migrate] schema ensured at {DB_PATH}; aliases added/kept: {ali}")

if __name__ == "__main__":
    main()
