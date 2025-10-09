# app/generate_canonicals.py
import os, csv, time, sqlite3, re
from typing import Dict, List, Tuple
from openai import OpenAI

DB_PATH = os.getenv("DB_PATH", "/data/gita.db")
GEN_MODEL = os.getenv("GEN_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

_CV_RE = re.compile(r"^(\d{1,2})\s*[:.]\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?$")

def _expand_whitelist(s: str) -> List[Tuple[int,int]]:
    out: List[Tuple[int,int]] = []
    if not s: return out
    for part in re.split(r"[;,]\s*|\s+", s.strip()):
        if not part: continue
        m = _CV_RE.match(part)
        if not m: continue
        ch = int(m.group(1)); v1 = int(m.group(2))
        if m.group(3):
            v2 = int(m.group(3))
            lo, hi = sorted((v1, v2))
            out.extend([(ch, v) for v in range(lo, hi+1)])
        else:
            out.append((ch, v1))
    # unique & sorted
    return sorted(set(out))

def _load_master_rows(master_csv: str) -> Dict[Tuple[int,int], Dict[str,str]]:
    # Expect columns like: chapter, verse, translation, commentary2, (optionally commentary1, roman, title…)
    out: Dict[Tuple[int,int], Dict[str,str]] = {}
    with open(master_csv, newline='', encoding="utf-8") as f:
        r = csv.DictReader(f)
        # normalize headers
        def norm(h): return (h or "").strip().lower()
        for row in r:
            cols = {norm(k): v for k, v in row.items()}
            try:
                ch = int(str(cols.get("chapter") or cols.get("chap") or "").strip())
                ve = int(str(cols.get("verse") or "").strip())
            except Exception:
                continue
            out[(ch, ve)] = {
                "translation": cols.get("translation","").strip(),
                "commentary2": cols.get("commentary2","").strip(),
                "commentary1": cols.get("commentary1","").strip(),
                "roman": cols.get("roman","").strip(),
                "title": cols.get("title","").strip(),
                "colloquial": cols.get("colloquial","").strip(),
            }
    return out

def _make_context(whitelist, master_map, max_per_verse_chars=600) -> List[str]:
    """Builds compact context lines like: [2:47] <snippet>"""
    ctx = []
    for (ch, v) in whitelist:
        data = master_map.get((ch, v)) or {}
        block = data.get("commentary2") or data.get("commentary1") or data.get("translation") or ""
        block = (block or "").strip()
        if not block: continue
        if len(block) > max_per_verse_chars:
            block = block[:max_per_verse_chars].rsplit(" ", 1)[0] + "…"
        ctx.append(f"[{ch}:{v}] {block}")
        if len(ctx) >= 40:
            break
    return ctx

def _call_model(system, user, max_tokens=900, temperature=0.2) -> str:
    try:
        rsp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (rsp.choices[0].message.content or "").strip()
    except Exception as e:
        return ""

def _gen_answer(question_text: str, style: str, ctx_lines: List[str], tier: str) -> str:
    # length targets (you can tweak later)
    if tier == "short":
        guide = "Give a crisp 2–4 sentence answer."
        max_toks = 300
    elif tier == "medium":
        guide = "Write 3–6 short paragraphs with a natural flow (may include lists where it fits)."
        max_toks = 700
    else:
        guide = "Write an in-depth, well-structured exposition (6–10 paragraphs, varied formatting as natural)."
        max_toks = 1000

    style_note = ""
    if style == "portrait":
        style_note = "If natural, enumerate qualities or signs succinctly; avoid robotic templates."
    elif style == "doctrinal":
        style_note = "Favor a readable narrative; insert brief bullets only if they help clarity."

    system = (
        "You are a Bhagavad Gita tutor. Answer ONLY from the provided context.\n"
        "Use the model’s natural formatting (headings/lists if helpful), but do not force a rigid template.\n"
        "Weave in Bhagavad Gita verse chips like [chapter:verse] wherever relevant.\n"
        "Avoid boilerplate like 'the commentary says'; write directly in plain, elegant English.\n"
    )
    user = (
        f"Question: {question_text}\n"
        f"{guide}\n{style_note}\n\n"
        "Context lines (each begins with a verse chip you may cite):\n" +
        "\n".join(ctx_lines[:120])
    )

    text = _call_model(system, user, max_tokens=max_toks)
    # normalize any 'Chapter 18 Verse 66' to [18:66]
    text = re.sub(r"Chapter\s+(\d+)\s*(?:,|)\s*Verse\s+(\d+)", r"[\1:\2]", text, flags=re.I)
    return text

def _ensure_tables():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
      id INTEGER PRIMARY KEY,
      micro_topic_id INTEGER NOT NULL,
      intent TEXT DEFAULT 'general',
      priority INTEGER DEFAULT 5,
      source TEXT DEFAULT 'seed',
      question_text TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS answers (
      id INTEGER PRIMARY KEY,
      question_id INTEGER NOT NULL,
      length_tier TEXT CHECK(length_tier IN ('short','medium','long')) NOT NULL,
      answer_text TEXT NOT NULL,
      UNIQUE(question_id, length_tier),
      FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
    );
    """)
    con.commit(); con.close()

def run_generate(control_csv: str, master_csv: str, sleep_sec: float = 0.6) -> Dict[str,int]:
    _ensure_tables()
    master_map = _load_master_rows(master_csv)

    inserted_q = updated_q = 0
    inserted_a = updated_a = 0

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    with open(control_csv, newline='', encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            qtext = (row.get("question_text") or "").strip()
            if not qtext: continue
            micro_topic_id = int(row.get("micro_topic_id") or 0)
            style = (row.get("style") or "doctrinal").strip().lower()
            whitelist = _expand_whitelist(row.get("verse_whitelist") or "")

            if not whitelist:
                # Skip entries with no usable verses
                continue

            ctx_lines = _make_context(whitelist, master_map)

            # upsert question
            cur.execute("SELECT id FROM questions WHERE question_text=?", (qtext,))
            qrow = cur.fetchone()
            if qrow:
                qid = qrow["id"]; updated_q += 0
            else:
                cur.execute(
                    "INSERT INTO questions(question_text, micro_topic_id, intent, priority, source) VALUES(?,?,?,?,?)",
                    (qtext, micro_topic_id, "general", 3, "canonical")
                )
                qid = cur.lastrowid
                inserted_q += 1

            for tier in ("short","medium","long"):
                ans = _gen_answer(qtext, style, ctx_lines, tier)
                cur.execute("SELECT id FROM answers WHERE question_id=? AND length_tier=?", (qid, tier))
                arow = cur.fetchone()
                if arow:
                    cur.execute("UPDATE answers SET answer_text=? WHERE id=?", (ans, arow["id"]))
                    updated_a += 1
                else:
                    cur.execute("INSERT INTO answers(question_id,length_tier,answer_text) VALUES(?,?,?)",
                                (qid, tier, ans))
                    inserted_a += 1
                # be gentle with the API
                time.sleep(sleep_sec)

            con.commit()

    con.close()
    return {
        "questions_inserted": inserted_q,
        "questions_updated": updated_q,
        "answers_inserted": inserted_a,
        "answers_updated": updated_a
    }
