#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Canonical Q&A generator (AI-first, commentary-informed) — with commentary3 (Sethu)

- Reads control CSV: /data/control_questions_v3.csv
  columns: question_id,question_text,style,whitelist,priority
  - style ∈ {analytical, explanatory}
  - whitelist supports ranges like 12:8-12 and single chips like 18:66

- For each row:
  * expand whitelist chips to concrete (ch,verse) list
  * fetch translation + commentary2 + commentary3 from SQLite (DB_PATH or /data/gita.db)
  * build a compact "evidence pack" from commentary2/3 (+translation fallback)
  * ask the model for DETAIL (>=500 words, aim 700–800) in the requested style
  * derive SUMMARY (>=100 words, flexible layout)
  * upsert both into answers table:
      (question_id, 'long', detail_markdown)
      (question_id, 'short', summary_markdown)

Env:
  DB_PATH=/data/gita.db
  CONTROL_CSV=/data/control_questions_v3.csv
  OPENAI_API_KEY=...
  GEN_MODEL=gpt-4o-mini (default)
  GEN_SLEEP=0.6
"""

import csv
import os
import re
import sqlite3
import sys
import time
from typing import List, Tuple, Dict, Optional

DB_PATH = os.environ.get("DB_PATH", "/data/gita.db")
CONTROL_CSV = os.environ.get("CONTROL_CSV", "/data/control_questions_v3.csv")
GEN_MODEL = os.environ.get("GEN_MODEL", "gpt-4o-mini")
SLEEP_BETWEEN = float(os.environ.get("GEN_SLEEP", "0.6"))

# ---- OpenAI client ----
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
except Exception as e:
    print("[FATAL] OpenAI client not available:", e, file=sys.stderr)
    sys.exit(1)

# ---- Regex helpers ----
CHIP_RE = re.compile(r"\b([1-9]|1[0-8])\s*[:.]\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?\b")
PHRASE_CHAPTER_VERSE = re.compile(r"Chapter\s+(\d+)\s*(?:,|)\s*Verse\s+(\d+)", re.I)

def norm_chips(text: str) -> str:
    """Normalize 'Chapter X Verse Y' => [X:Y]."""
    return PHRASE_CHAPTER_VERSE.sub(r"[\1:\2]", text or "")

def expand_whitelist(raw: str) -> List[Tuple[int,int]]:
    """Expand comma-separated chips, allowing ranges like 12:8-12."""
    out: List[Tuple[int,int]] = []
    for part in (raw or "").replace(" ", "").split(","):
        if not part:
            continue
        m = CHIP_RE.search(part)
        if not m:
            continue
        ch = int(m.group(1))
        v1 = int(m.group(2))
        v2 = m.group(3)
        if v2:
            v2 = int(v2)
            lo, hi = min(v1, v2), max(v1, v2)
            out.extend((ch, v) for v in range(lo, hi+1))
        else:
            out.append((ch, v1))
    # dedupe, preserve order
    seen = set(); uniq = []
    for ch,v in out:
        if (ch,v) in seen: continue
        seen.add((ch,v)); uniq.append((ch,v))
    return uniq

def connect_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def fetch_verse(con: sqlite3.Connection, ch: int, v: int) -> Optional[Dict]:
    r = con.execute("""
        SELECT chapter, verse, title, translation, commentary2, commentary3
        FROM verses
        WHERE chapter=? AND verse=?
    """, (ch, v)).fetchone()
    return dict(r) if r else None

def summarize_to_bullets(text: str, max_bullets: int = 3, max_chars: int = 480) -> List[str]:
    """Tiny heuristic: carve 1–3 sentence bullets from commentary/translation."""
    if not text: return []
    t = re.sub(r"\s+", " ", text).strip()
    t = t[:max_chars]
    parts = re.split(r"(?<=[.!?])\s+", t)
    bullets = []
    for p in parts:
        p = p.strip()
        if len(p) < 30: 
            continue
        bullets.append(p)
        if len(bullets) >= max_bullets:
            break
    return bullets

def build_evidence_pack(con: sqlite3.Connection, chips: List[Tuple[int,int]]) -> Tuple[str, List[str]]:
    """
    Build compact evidence bullets for the model:
      - prefer commentary2 + commentary3; fallback to translation
      - 2–3 bullets per verse if possible
    Returns (markdown_list, chip_labels)
    """
    lines = []
    chip_labels = []
    for ch, v in chips:
        row = fetch_verse(con, ch, v)
        if not row: 
            continue
        chip = f"{ch}:{v}"
        chip_labels.append(chip)

        trans = (row.get("translation") or "").strip()
        comm2 = (row.get("commentary2") or "").strip()
        comm3 = (row.get("commentary3") or "").strip()

        combo = " ".join([s for s in (comm2, comm3) if s]) or trans
        bullets = summarize_to_bullets(combo, max_bullets=3)
        if not bullets and trans:
            bullets = summarize_to_bullets(trans, max_bullets=2)

        if bullets:
            lines.append(f"- [{chip}] " + bullets[0])
            for b in bullets[1:]:
                lines.append(f"  • {b}")
        else:
            gist = re.sub(r"\s+", " ", combo or trans)[:200]
            lines.append(f"- [{chip}] {gist}")
    return "\n".join(lines), chip_labels

def call_openai_detail(question: str, style: str, whitelist: List[str], evidence_md: str) -> str:
    style_clause = (
        "Use an analytical, sectioned style with `###` headings and simple `-` bullets where appropriate."
        if style.lower().strip() == "analytical"
        else "Use an explanatory, flowing narrative with a few `###` sub-headings (not too many)."
    )
    system = (
        "You are a Bhagavad Gita teacher. Answer ONLY from the Gita and from the following notes. "
        "Keep a single, confident teacherly voice (do not mention any commentators by name). "
        "Cite verses inline as [chapter:verse] chips. Avoid boilerplate closers."
    )
    user = f"""
Question:
{question}

Allowed verse chips (prefer citing these): {", ".join(f"[{c}]" for c in whitelist)}

Reference notes (compact bullets distilled from translation/commentary):
{evidence_md}

Write the DETAIL answer with these rules:
- {style_clause}
- Word count: target 700–800; DO NOT go under 500 words.
- Keep verse chips like [18:66], [12:8] inline.
- You may include at most two short translation fragments (<= 20 words) where they illuminate.
- Do NOT name or quote commentators; integrate ideas in your own voice.
- Keep formatting clean; use only `###` for headings and `-` bullets; no deep nesting.
"""
    rsp = client.chat.completions.create(
        model=GEN_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.35,
        max_tokens=1200,
    )
    return (rsp.choices[0].message.content or "").strip()

def call_openai_summary(detail_markdown: str) -> str:
    system = (
        "You are a concise Bhagavad Gita teacher. Create a short Summary from the given DETAIL answer. "
        "Preserve meaning and the 2–4 strongest [chapter:verse] chips."
    )
    user = f"""
DETAIL (source):
{detail_markdown}

Now produce a SUMMARY with these rules:
- 100–140 words minimum.
- Layout: either (a) 1 paragraph; or (b) 2 short paragraphs; or (c) 1 short paragraph + a mini bullet list (max 4 bullets).
- Keep 2–4 of the strongest verse chips like [18:66].
- Keep a clean teacherly voice; no headings; no deep formatting.
"""
    rsp = client.chat.completions.create(
        model=GEN_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.35,
        max_tokens=420,
    )
    return (rsp.choices[0].message.content or "").strip()

def normalize_markdown(md: str) -> str:
    if not md: return md
    md = norm_chips(md)
    md = re.sub(r"^####\s+", "### ", md, flags=re.M)  # normalize too-deep headings
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()

def ensure_question_exists(con: sqlite3.Connection, qid: int, qtext: str):
    con.execute("""
        INSERT INTO questions(id, micro_topic_id, intent, priority, source, question_text)
        VALUES(?, 0, 'general', 5, 'seed', ?)
        ON CONFLICT(id) DO UPDATE SET question_text=excluded.question_text
    """, (qid, qtext))

def upsert_answer(con: sqlite3.Connection, qid: int, tier: str, text_md: str):
    con.execute("""
        INSERT INTO answers(question_id, length_tier, answer_text)
        VALUES(?, ?, ?)
        ON CONFLICT(question_id, length_tier) DO UPDATE SET answer_text=excluded.answer_text
    """, (qid, tier, text_md))

def main():
    if not os.path.exists(CONTROL_CSV):
        print(f"[FATAL] Control CSV not found: {CONTROL_CSV}", file=sys.stderr)
        sys.exit(1)

    con = connect_db()

    with open(CONTROL_CSV, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    print(f"[info] control rows: {total}")

    for idx, row in enumerate(rows, 1):
        try:
            qid = int(row.get("question_id") or 0)
            qtext = (row.get("question_text") or "").strip()
            style = (row.get("style") or "explanatory").strip().lower()
            whitelist_raw = (row.get("whitelist") or "").strip()

            if not qid or not qtext or not whitelist_raw:
                print(f"[skip] row#{idx}: missing qid/qtext/whitelist")
                continue

            chips = expand_whitelist(whitelist_raw)
            if not chips:
                print(f"[warn] row#{idx} qid={qid}: empty chips after expand for '{whitelist_raw}'")
                continue

            evidence_md, chip_labels = build_evidence_pack(con, chips)

            ensure_question_exists(con, qid, qtext)
            con.commit()

            detail = call_openai_detail(qtext, style, chip_labels, evidence_md)
            detail = normalize_markdown(detail)

            # Expand if too short
            if len(detail.split()) < 480:
                system = "Expand while preserving structure, chips, and voice. Do not add filler."
                user = f"Expand this DETAIL to ~700–800 words (minimum 500) without changing meaning:\n\n{detail}"
                try:
                    rsp = client.chat.completions.create(
                        model=GEN_MODEL,
                        messages=[{"role": "system", "content": system},
                                  {"role": "user", "content": user}],
                        temperature=0.3,
                        max_tokens=900,
                    )
                    expanded = (rsp.choices[0].message.content or "").strip()
                    if len(expanded.split()) > len(detail.split()):
                        detail = normalize_markdown(expanded)
                except Exception:
                    pass

            summary = call_openai_summary(detail)
            summary = normalize_markdown(summary)

            if len(summary.split()) < 95:
                summary += "\n\n" + "In essence, this teaching centers on loving trust, steady remembrance, and offering all results to the Lord [18:66][12:10][3:30]."

            upsert_answer(con, qid, "long", detail)
            upsert_answer(con, qid, "short", summary)
            con.commit()

            print(f"[ok] {idx}/{total} qid={qid} chips={len(chips)} style={style} "
                  f"detail_words~{len(detail.split())} summary_words~{len(summary.split())}")

            time.sleep(SLEEP_BETWEEN)

        except KeyboardInterrupt:
            print("\n[abort] interrupted by user"); break
        except Exception as e:
            print(f"[err] row#{idx} qid={row.get('question_id')} : {e}", file=sys.stderr)
            # continue

    con.close()
    print("[done] generation complete")

if __name__ == "__main__":
    main()
