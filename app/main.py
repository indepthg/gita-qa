# app/main.py — Gita Q&A v2 (with canonical upload + background generation)
import os
import re
import csv
import json
import time
import threading
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Header, Query, Body

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- DB helpers from your project ---
from .db import (
    get_conn,
    init_db,
    bulk_upsert,
    fetch_exact,
    fetch_neighbors,
    search_fts,
    stats,
    ensure_fts,
)

from .ingest import load_sheet_to_rows, ingest_commentary

# --- Environment ---
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*")
GEN_MODEL = os.getenv("GEN_MODEL", "gpt-4o-mini")
NO_MATCH_MESSAGE = os.getenv(
    "NO_MATCH_MESSAGE",
    "I couldn't find enough in the corpus to answer that. Try a specific verse like 12:12, or rephrase your question.",
)
TOPIC_DEFAULT = os.getenv("TOPIC_DEFAULT", "gita")
USE_EMBED = os.getenv("USE_EMBED", "0") == "1"  # kept for compatibility
RAG_SOURCE = os.getenv("RAG_SOURCE", "").strip().lower()  # e.g. "commentary2"
DB_PATH = os.environ.get("DB_PATH", "/data/gita.db")
ADMIN_TOKEN = (os.getenv("ADMIN_TOKEN", "gita-krishna") or "").strip()

# --- OpenAI client ---
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI(title="Gita Q&A v2")

# --- CORS ---
if ALLOW_ORIGINS == "*":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )
else:
    allowed = [o.strip() for o in ALLOW_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )

# Serve widget.js at /static/widget.js
app.mount("/static", StaticFiles(directory="app"), name="static")

# --- Boot DB ---
init_db()

def _clean_text_preserve_lines(t: str) -> str:
    """Preserve line breaks; remove HTML; avoid flattening to one line."""
    if not t:
        return ""
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?is)<p[^>]*>", "", t)
    t = re.sub(r"(?is)</p>", "\n\n", t)
    t = re.sub(r"(?is)<[^>]+>", "", t)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"\n{4,}", "\n\n", t)
    t = "\n".join(ln.rstrip() for ln in t.split("\n"))
    return t.strip()

def _normalize_md_answer(md: str) -> str:
    """Normalize verse mentions and shallow heading levels in model/seeded Markdown."""
    if not md:
        return md
    md = re.sub(r"Chapter\s+(\d+)\s*(?:,|)\s*Verse\s+(\d+)", r"[\1:\2]", md, flags=re.I)
    md = re.sub(r"^####\s+", "### ", md, flags=re.M)  # collapse too-deep headings
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()

# ====================== HTML (unchanged UI) ======================
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Gita Q&A</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light dark" />
  <style>
    :root{
      --bg:#0b0c0f; --card:#111318; --border:#22252b; --text:#e9e9ec; --muted:#9aa0a6;
      --pill:#171a20; --pill-border:#2a2e35; --accent:#ff8d1a;
    }
    @media (prefers-color-scheme: light) {
      :root{
        --bg:#f5f5f7; --card:#ffffff; --border:#e6e6ea; --text:#111; --muted:#5b6068;
        --pill:#f3f4f6; --pill-border:#e5e7eb; --accent:#ff8d1a;
      }
    }
    *{box-sizing:border-box}
    html,body{height:100%}
    body{
      margin:0; background:var(--bg); color:var(--text);
      font: 15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
      display:flex; align-items:stretch; justify-content:center;
    }
    .wrap{ width:min(920px, 100%); padding:24px; }
    .card{
      background:var(--card); border:1px solid var(--border); border-radius:16px;
      box-shadow: 0 8px 30px rgba(0,0,0,.12);
      overflow:hidden;
    }
    .head{ display:flex; align-items:baseline; justify-content:space-between; padding:18px 22px; border-bottom:1px solid var(--border); }
    .title{ font-size:20px; font-weight:700; letter-spacing:.2px; }
    .topic{ font-size:12px; color:var(--muted); }

    .body{ display:flex; flex-direction:column; gap:12px; padding:14px 22px 8px; }
    .pills{ display:flex; flex-wrap:wrap; gap:8px; padding:6px 0 2px; }
    .pills .pill{
      padding:6px 10px; border-radius:999px; border:1px solid var(--pill-border); background:var(--pill); color:var(--text);
      cursor:pointer; font-size:12px;
    }

    .form{ display:flex; gap:10px; align-items:center; padding-top:8px; border-top:1px solid var(--border); margin-top:8px; position:sticky; bottom:0; background:var(--card); }
    .input{ flex:1; padding:12px 14px; border:1px solid var(--border); border-radius:12px; background:transparent; color:var(--text); outline:none; font-size:15px; }
    .send{
      width:42px;height:42px;display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:9999px;
      background:var(--accent);color:#111;cursor:pointer;font-weight:700;position:relative;flex:0 0 auto;
      transition: transform .15s ease, opacity .15s ease;
    }
    .send:hover{ transform: translateY(-1px); }
    .send:active{ transform: translateY(0); }
    .send[disabled]{ opacity:.6; cursor:not-allowed; }
    .send__svg{ width:20px;height:20px; display:block; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="head">
        <div class="title">Gita Q&A</div>
        <div class="topic">Topic: gita</div>
      </div>
      <div class="body">
        <div id="gita"></div>
      </div>
    </div>
  </div>
<script>
(function () {
  var s = document.createElement('script');
  s.src = '/static/widget.js?v=' + Date.now();
  s.async = true;
  s.onload = function () {
    if (window.GitaWidget && GitaWidget.mount) {
      GitaWidget.mount({ root: '#gita', apiBase: '' });
      console.log('[GW] mounted via dynamic loader');
    } else {
      console.error('GitaWidget not found after load');
    }
  };
  s.onerror = function (e) { console.error('Failed to load widget.js', e); };
  document.head.appendChild(s);
})();
</script>
</body>
</html>
    """

# ====================== Ingest endpoints ======================
@app.post("/ingest_sheet_sql")
async def ingest_sheet_sql(file: UploadFile = File(...)):
    try:
        bytes_ = await file.read()
        rows = load_sheet_to_rows(bytes_, file.filename)
        conn = get_conn()
        n = bulk_upsert(conn, rows)
        ensure_fts(conn)
        return {"ingested_rows": n}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ingest_commentary")
async def ingest_commentary_route(
    file: UploadFile = File(...),
    topic: str = Form(TOPIC_DEFAULT),
    commentator: str = Form("Unknown"),
    source: str = Form("")
):
    try:
        bytes_ = await file.read()
        n = ingest_commentary(bytes_, file.filename, topic, commentator, source or file.filename)
        return {"chunks_added": n}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ====================== Lookup & debug ======================
@app.get("/title/{ch}/{v}")
async def get_title(ch: int, v: int):
    conn = get_conn()
    row = fetch_exact(conn, ch, v)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return {"chapter": ch, "verse": v, "title": row["title"] or ""}

@app.get("/debug/verse/{ch}/{v}")
async def debug_verse(ch: int, v: int):
    conn = get_conn()
    row = fetch_exact(conn, ch, v)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return dict(row)

@app.get("/debug/stats")
async def debug_stats():
    conn = get_conn()
    return stats(conn)

@app.get("/suggest")
async def suggest():
    return {
        "suggestions": [
            "Explain 2:47",
            "Which verses talk about devotion?",
            "What is sthita prajna?",
            "Verses on meditation",
            "Karma vs Bhakti vs Jnana"
        ]
    }

@app.get("/qa/debug-canonical")
def debug_canonical(q: str):
    conn = get_conn()
    cur = conn.execute("""
      SELECT id, question_text FROM questions
      WHERE question_text LIKE '%'||?||'%'
      ORDER BY id
    """, (q,))
    qs = [dict(r) for r in cur.fetchall()]
    out = {}
    for qrow in qs:
        cur = conn.execute("""
          SELECT length_tier, substr(answer_text,1,120) AS preview
          FROM answers WHERE question_id=?
          ORDER BY CASE length_tier WHEN 'short' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END
        """, (qrow["id"],))
        out[qrow["id"]] = {"question": qrow["question_text"], "answers": [dict(r) for r in cur.fetchall()]}
    return out

# ====================== Helpers ======================
RE_CV = re.compile(r"\b([1-9]|1[0-8])[:\. ](\d{1,2})\b")
CITE_RE = re.compile(r"\[\s*(?:C\s*:\s*)?(\d{1,2})\s*[:.]\s*(\d{1,3})\s*\]")

def _extract_ch_verse(text: str) -> Optional[Tuple[int, int]]:
    m = RE_CV.search(text or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))

def _is_word_meaning_query(q: str) -> bool:
    ql = (q or "").lower()
    return ("word meaning" in ql) or ("meaning" in ql and RE_CV.search(ql) is not None)

def _is_definition_query(q: str) -> bool:
    ql = (q or "").lower()
    return any(p in ql for p in ("what is", "meaning of", "define ", "who is", "explain the term "))

def _is_verses_listing_query(q: str) -> bool:
    ql = (q or "").lower()
    return (
        "which verses" in ql or
        "verses that" in ql or
        "verses on" in ql or
        "verses about" in ql or
        ("list" in ql and "verses" in ql) or
        ("show" in ql and "verses" in ql)
    )

def _summarize(prompt: str, max_tokens: int = 300) -> str:
    try:
        rsp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[
                {"role": "system", "content": "Answer in plain text with no markup."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return (rsp.choices[0].message.content or "").strip()
    except Exception:
        return ""

def _clean_text(t: str) -> str:
    if not t:
        return ""
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.replace("[C:V]", "").strip()

def _best_text_block(row: Dict[str, Any], force_source: Optional[str] = None) -> str:
    if force_source == "commentary2":
        v = _clean_text(row.get("commentary2") or "")
        return v or ""
    for k in ("commentary2", "commentary1", "translation", "colloquial", "roman", "title"):
        v = _clean_text(row.get(k) or "")
        if v:
            return v
    return ""

def _extract_citations_from_text(text: str) -> List[str]:
    out: List[str] = []
    for m in CITE_RE.finditer(text or ""):
        ch, v = int(m.group(1)), int(m.group(2))
        if 1 <= ch <= 18 and 1 <= v <= 200:
            out.append(f"{ch}:{v}")
    seen = set(); uniq: List[str] = []
    for c in out:
        if c in seen: continue
        seen.add(c); uniq.append(c)
    return uniq

def _make_dynamic_suggestions(user_q: str, cites: List[str]) -> List[str]:
    sug: List[str] = []
    if cites:
        show = ", ".join(cites[:5])
        sug.append(f"Show commentaries for {show}")
    sug.append("More detail")
    ql = (user_q or "").lower()
    if any(w in ql for w in ("how", "what", "why", "ways", "practice", "apply")):
        sug.append("Practical takeaway")
    return sug[:4]

# --- Light semantic expansion (improves recall) ---
THEME_EXPAND = {
    "anger": ["anger", "krodha", "wrath", "rage", "ire"],
    "desire": ["desire", "kama", "craving", "longing"],
    "self": ["self", "atman", "purusha", "kshetrajna"],
    "devotion": ["devotion", "bhakti", "worship", "surrender"],
    "meditation": ["meditation", "dhyana", "concentration", "mind control"],
    "detachment": ["detachment", "vairagya", "equanimity", "non-attachment"],
}
def _expand_query(q: str) -> str:
    ql = (q or "").lower()
    terms: List[str] = []
    for key, syns in THEME_EXPAND.items():
        if key in ql:
            terms.extend(syns)
    if not terms:
        return q
    q2 = q + " OR " + " OR ".join(dict.fromkeys(terms))
    return q2

# --- Model-only answer (fast, nicely formatted, Gita-guarded) ---
def _model_answer_guarded(question: str, max_tokens: int = 700) -> str:
    system = (
        "You are a Bhagavad Gita tutor. Answer clearly and helpfully, using only the Bhagavad Gita.\n"
        "Prefer to weave in chapter:verse citations like [2:47] whenever you refer to a verse.\n"
        "Do not cite or rely on other scriptures or external sources.\n"
        "Use a natural structure (headings, short paragraphs, lists) in plain text.\n"
        "If the question is not answerable from the Gita, say so briefly."
    )
    prompt = f"Question: {question}\n\nRespond as instructed above."
    try:
        rsp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return (rsp.choices[0].message.content or "").strip()
    except Exception:
        return ""

def _synthesize_structured(question: str, ctx_lines: List[str],
                           min_sections: int = 3, max_sections: int = 5,
                           target_words_low: int = 350, target_words_high: int = 450,
                           enforce_diversity_hint: Optional[List[str]] = None) -> str:
    ctx = "\n".join(ctx_lines)[:8000]
    diversity_hint = ""
    if enforce_diversity_hint:
        diversity_hint = (
            "Broaden citations across chapters where possible; avoid clustering from adjacent verses. "
            f"Prefer these distinct chapters if relevant: {', '.join(sorted(set(enforce_diversity_hint)))}.\n"
        )
    prompt = (
        "You are a Bhagavad Gita assistant. Use ONLY the Context below.\n"
        f"Write a structured answer with {min_sections}–{max_sections} thematic sections.\n"
        "- 2–4 sentences each, plain text, with [chapter:verse] citations where used.\n"
        f"- Total ≈ {target_words_low}–{target_words_high} words.\n"
        "- Use only context; do not invent sources.\n"
        f"{diversity_hint}\n"
        f"Question: {question}\n\n"
        "Context (each line = [chapter:verse] prose):\n"
        f"{ctx}\n"
    )
    try:
        rsp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[
                {"role": "system", "content": "Answer ONLY from the provided context. Plain text. Use [chapter:verse]."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        return (rsp.choices[0].message.content or "").strip()
    except Exception as e:
        print("LLM synth failed:", e)
        return ""

# ====================== /ask (keeps your routing) ======================
class AskPayload(BaseModel):
    question: str
    topic: Optional[str] = None

@app.post("/ask")
async def ask(payload: AskPayload):
    q = (payload.question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Empty question")

    topic = payload.topic or TOPIC_DEFAULT
    conn = get_conn()

    # Direct verse path
    cv = _extract_ch_verse(q)
    if cv:
        ch, v = cv
        row_r = fetch_exact(conn, ch, v)
        if not row_r:
            return {
                "mode": "error",
                "answer": f"Chapter {ch}, Verse {v} does not exist.",
                "citations": [],
                "debug": {"mode": "explain", "error": "no_such_verse"}
            }
        row = dict(row_r)

        # Word meaning?
        if _is_word_meaning_query(q):
            wm = row.get("word_meanings") or ""
            return {
                "mode": "word_meaning",
                "chapter": ch,
                "verse": v,
                "answer": wm if wm else NO_MATCH_MESSAGE,
                "citations": [f"[{ch}:{v}]"],
                "debug": {"mode": "word_meaning"}
            }

        # EXPLAIN — DB-only (fast), preserve line breaks, show fields in desired order
        neighbors = [dict(n) for n in fetch_neighbors(conn, ch, v, k=1)]

        resp = {
            "mode": "explain",
            "chapter": ch,
            "verse": v,
            "title": row.get("title") or "",
            "sanskrit": _clean_text_preserve_lines(row.get("sanskrit") or ""),
            "roman": _clean_text_preserve_lines(row.get("roman") or ""),
            "colloquial": _clean_text_preserve_lines(row.get("colloquial") or ""),
            "translation": _clean_text_preserve_lines(row.get("translation") or ""),

            # Summary immediately after translation (no model fallback)
            "summary": _clean_text_preserve_lines(row.get("summary") or ""),

            # Commentary2 first, then Commentary3 (additional), then Commentary1
            "commentary2": _clean_text_preserve_lines(row.get("commentary2") or ""),
            "commentary3": _clean_text_preserve_lines(row.get("commentary3") or ""),
            "commentary1": _clean_text_preserve_lines(row.get("commentary1") or ""),

            "capsule_url": row.get("capsule_url") or "",
            "neighbors": [
                {"chapter": int(n["chapter"]), "verse": int(n["verse"]), "translation": n.get("translation") or ""}
                for n in neighbors
            ],
            "citations": [f"[{ch}:{v}]"],
            "debug": {
                "mode": "explain",
                "used_db_summary": bool(row.get("summary")),
                "summary_fallback_generated": False
            }
        }
        return resp

    # ===== CANONICAL FAST PATH =====
    try:
        hit = []
        try:
            cur = conn.execute("""
                SELECT q.id, q.micro_topic_id, q.intent, q.priority, q.question_text
                FROM questions_fts
                JOIN questions q ON q.id = questions_fts.rowid
                WHERE questions_fts MATCH ?
                ORDER BY bm25(questions_fts) ASC, q.priority ASC
                LIMIT 1
            """, (q,))
            hit = [dict(r) for r in cur.fetchall()]
        except Exception:
            pass
        if not hit:
            cur = conn.execute("""
                SELECT id, micro_topic_id, intent, priority, question_text
                FROM questions
                WHERE question_text LIKE '%'||?||'%'
                ORDER BY priority ASC, id ASC
                LIMIT 1
            """, (q,))
            hit = [dict(r) for r in cur.fetchall()]

        if hit:
            qrow = hit[0]
            cur = conn.execute("""
                SELECT length_tier, answer_text
                FROM answers
                WHERE question_id=?
                ORDER BY CASE length_tier WHEN 'short' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END
            """, (qrow["id"],))
            ans_rows = [dict(r) for r in cur.fetchall()]
            if ans_rows:
                by_tier = {a['length_tier']: a['answer_text'] for a in ans_rows}
                # Use Detail (“long”) as the main answer; fall back to Summary (“short”) if needed
                body = by_tier.get('long') or by_tier.get('short') or ""
                body = _normalize_md_answer(body)
                summary = _normalize_md_answer(by_tier.get('short', "")) if 'short' in by_tier else ""

                cites = _extract_citations_from_text(body)
                return {
                    "mode": "canonical",
                    "matched_question": qrow.get("question_text"),
                    "answer": body,           # Detail only (no Short/Medium/Long headings)
                    "summary": summary,       # optional (widget can show a “Summary” toggle)
                    "citations": [f"[{c}]" for c in cites[:8]],
                    "suggestions": _make_dynamic_suggestions(q, cites[:5]),
                    "embeddings_used": False,
                    "debug": {"mode": "canonical", "qid": qrow["id"]}
                }
    except Exception:
        pass
    # ===== END CANONICAL FAST PATH =====

    # Decide: verse-list?
    q_expanded = _expand_query(q)
    fts_rows = search_fts(conn, q_expanded, limit=60)
    if _is_verses_listing_query(q):
        diversified = _diversify_hits(
            [(int(r["chapter"]), int(r["verse"]), dict(r)) for r in fts_rows],
            per_chapter=2, max_total=20, neighbor_radius=1, min_distinct_chapters=3
        )
        lines: List[str] = []
        cites: List[str] = []
        for ch, v, data in diversified[:20]:
            row = dict(data)
            title = _clean_text(row.get("title") or "")
            trans = _clean_text(row.get("translation") or row.get("roman") or row.get("colloquial") or "")
            if trans and len(trans) > 220:
                trans = trans[:220].rsplit(" ", 1)[0] + "…"
            label = f"{ch}:{v}"
            lines.append(f"{title} — {trans} [{label}]".strip())
            cites.append(label)
        answer = "\n\n".join(lines) if lines else NO_MATCH_MESSAGE
        return {
            "mode": "thematic_list",
            "answer": answer,
            "citations": [f"[{c}]" for c in cites[:8]],
            "suggestions": ["More detail"] + ([f"Explain {c}" for c in cites[:3]] if cites else []),
            "embeddings_used": False,
            "debug": {"mode": "thematic_list", "items": len(lines)}
        }

    # Definitions (short terms)
    if _is_definition_query(q) or (len(q.split()) <= 3):
        system = (
            "You are a Bhagavad Gita tutor. Define the term from the Gita only. "
            "Include 2–3 inline verse citations like [chapter:verse] where relevant."
        )
        prompt = f"Define briefly and clearly: {q}"
        try:
            rsp = client.chat.completions.create(
                model=GEN_MODEL,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=380,
            )
            ans = (rsp.choices[0].message.content or "").strip()
            ans = _normalize_md_answer(ans)
        except Exception:
            ans = ""
        cites = _extract_citations_from_text(ans)
        return {
            "mode": "definition",
            "answer": ans if ans else NO_MATCH_MESSAGE,
            "citations": [f"[{c}]" for c in cites[:8]],
            "suggestions": ["More detail", "Show related verses"],
            "embeddings_used": False,
            "debug": {"mode": "definition", "model_only": True, "cites_found": len(cites)}
        }

    # Model-only thematic
    ans = _model_answer_guarded(q, max_tokens=700)
    ans = _normalize_md_answer(ans)
    if not ans:
        merged = [(int(r["chapter"]), int(r["verse"]), dict(r)) for r in fts_rows]
        if not merged:
            return {
                "mode": "broad",
                "answer": NO_MATCH_MESSAGE,
                "citations": [],
                "suggestions": [],
                "embeddings_used": False,
                "debug": {"mode": "none", "reason": "no_hits"}
            }

        diversified = _diversify_hits(merged, per_chapter=2, max_total=12, neighbor_radius=1, min_distinct_chapters=3)
        ctx_lines: List[str] = []
        cites_unique: List[str] = []
        chapters_in_ctx: List[str] = []
        force_source = "commentary2" if RAG_SOURCE == "commentary2" else None

        for ch, v, data in diversified:
            row = dict(data)
            block = _best_text_block(row, force_source=force_source)
            if not block:
                continue
            if len(block) > 600:
                block = block[:600].rsplit(" ", 1)[0] + "…"
            ctx_lines.append(f"[{ch}:{v}] {block}")
            cites_unique.append(f"{ch}:{v}")
            chapters_in_ctx.append(str(ch))
            if len(ctx_lines) >= 10:
                break

        if not ctx_lines:
            return {
                "mode": "broad",
                "answer": NO_MATCH_MESSAGE,
                "citations": [],
                "suggestions": [],
                "embeddings_used": False,
                "debug": {"mode": "broad", "reason": "no_ctx"}
            }

        ans = _synthesize_structured(q, ctx_lines, min_sections=3, max_sections=4,
                                     target_words_low=350, target_words_high=450,
                                     enforce_diversity_hint=chapters_in_ctx)
        ans = _normalize_md_answer(ans)
        model_cites = _extract_citations_from_text(ans)
        ordered: List[str] = []
        seen = set()
        for c in model_cites + cites_unique:
            if c in seen: continue
            seen.add(c); ordered.append(c)

        return {
            "mode": "rag",
            "answer": ans if ans else NO_MATCH_MESSAGE,
            "citations": [f"[{c}]" for c in ordered[:8]],
            "suggestions": _make_dynamic_suggestions(q, ordered[:5]),
            "embeddings_used": False,
            "debug": {"mode": "rag_fallback", "rag_source": RAG_SOURCE or "mixed"}
        }

    cites = _extract_citations_from_text(ans)
    return {
        "mode": "model_only",
        "answer": ans,
        "citations": [f"[{c}]" for c in cites[:8]],
        "suggestions": _make_dynamic_suggestions(q, cites[:5]),
        "embeddings_used": False,
        "debug": {"mode": "model_only"}
    }

# ====================== Retrieval diversification ======================
def _diversify_hits(merged: List[Tuple[int, int, Dict]],
                    per_chapter: int = 2,
                    max_total: int = 10,
                    neighbor_radius: int = 1,
                    min_distinct_chapters: int = 3) -> List[Tuple[int, int, Dict]]:
    selected: List[Tuple[int, int, Dict]] = []
    per_ch = defaultdict(int)
    def is_neighbor(ch: int, v: int) -> bool:
        for (sch, sv, _) in selected:
            if ch == sch and abs(v - sv) <= neighbor_radius:
                return True
        return False
    for ch, v, data in merged:
        if len(selected) >= max_total: break
        if per_ch[ch] >= per_chapter: continue
        if is_neighbor(ch, v): continue
        selected.append((ch, v, data)); per_ch[ch] += 1
    if len({ch for ch, _, _ in selected}) < min_distinct_chapters:
        for ch, v, data in merged:
            if len(selected) >= max_total: break
            if per_ch[ch] >= per_chapter: continue
            if any((ch == sch and v == sv) for sch, sv, _ in selected): continue
            selected.append((ch, v, data)); per_ch[ch] += 1
    return selected[:max_total]

# ====================== Admin auth helper ======================
def _require_admin(x_admin_token: Optional[str]):
    given = (x_admin_token or "").strip()
    if given != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ====================== Admin: ad-hoc SQL (read-only) ======================
@app.post("/admin/sql")
async def admin_sql(
    sql: str = Body(..., media_type="text/plain"),
    x_admin_token: str = Header(None, convert_underscores=False),
):
    """
    Minimal read-only SQL runner.
    - Requires admin token.
    - Allows only SELECT / EXPLAIN / PRAGMA (read-only) single statement.
    - Returns rows as JSON (columns + rows).
    """
    _require_admin(x_admin_token)

    q = (sql or "").strip().strip(";")
    if not q:
        raise HTTPException(status_code=400, detail="Empty SQL")

    # Basic safety: only allow read-only statements
    low = q.lower()
    if not (low.startswith("select") or low.startswith("explain") or low.startswith("pragma")):
        raise HTTPException(status_code=400, detail="Only SELECT/EXPLAIN/PRAGMA allowed")

    # Disallow multiple statements
    if ";" in q:
        raise HTTPException(status_code=400, detail="Only a single statement is allowed")

    try:
        conn = get_conn()
        conn.row_factory = None  # we’ll build dicts manually using cursor.description
        cur = conn.execute(q)
        cols = [c[0] for c in cur.description] if cur.description else []
        rows_raw = cur.fetchall() if cur.description else []
        rows = [dict(zip(cols, r)) for r in rows_raw]
        return {
            "sql": q,
            "columns": cols,
            "rowcount": len(rows),
            "rows": rows,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SQL error: {e}")


# ====================== Debug: verse summary peek ======================
@app.get("/debug/summary/{ch}/{v}")
async def debug_summary(ch: int, v: int):
    """
    Convenience endpoint to quickly see the 'summary' column for a verse.
    No auth required. Read-only.
    """
    try:
        conn = get_conn()
        conn.row_factory = None
        cur = conn.execute(
            "SELECT chapter, verse, summary FROM verses WHERE chapter=? AND verse=?",
            (ch, v),
        )
        row = cur.fetchone()
        if not row:
            return {"chapter": ch, "verse": v, "summary": None}
        cols = [c[0] for c in cur.description]
        data = dict(zip(cols, row))
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ====================== Admin: ping ======================
@app.get("/admin/canonicals/ping")
async def admin_canonicals_ping(
    x_admin_token: str = Header(None, convert_underscores=False),
):
    _require_admin(x_admin_token)
    return {"ok": True}

# ====================== Admin: upload CSVs ======================
@app.post("/admin/canonicals/upload")
async def admin_upload_canonicals(
    control: UploadFile = File(...),
    master: UploadFile = File(...),
    x_admin_token: str = Header(None, convert_underscores=False),
):
    _require_admin(x_admin_token)
    try:
        os.makedirs("/data", exist_ok=True)
        control_path = "/data/control_questions_v3.csv"
        master_path = "/data/Gita_Master_Index_v1.csv"
        with open(control_path, "wb") as f:
            f.write(await control.read())
        with open(master_path, "wb") as f:
            f.write(await master.read())
        return {"saved": {"control": control_path, "master": master_path}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ====================== Canonical generation core ======================
def _parse_whitelist(whitelist: str) -> List[Tuple[int,int]]:
    # supports "18:66, 9:22, 12:8-12"
    pairs: List[Tuple[int,int]] = []
    if not whitelist:
        return pairs
    for tok in re.split(r"[,\s]+", whitelist.strip()):
        if not tok:
            continue
        m = re.match(r"^(\d{1,2})[:.](\d{1,3})(?:-(\d{1,3}))?$", tok)
        if not m: continue
        ch = int(m.group(1)); v1 = int(m.group(2))
        v2 = int(m.group(3)) if m.group(3) else v1
        for v in range(v1, v2+1):
            if 1 <= ch <= 18 and 1 <= v <= 200:
                pairs.append((ch, v))
    # unique preserving order
    seen = set(); out: List[Tuple[int,int]] = []
    for p in pairs:
        if p in seen: continue
        seen.add(p); out.append(p)
    return out

def _compose_snippet_context(cv_list: List[Tuple[int,int]], master_lookup: Dict[Tuple[int,int], Dict[str,str]]) -> str:
    # Build compact context like: [18:66] Translation: ... | Commentary: ...
    lines: List[str] = []
    for ch, v in cv_list:
        row = master_lookup.get((ch, v)) or {}
        trans = (row.get("translation") or "").strip()
        comm2 = (row.get("commentary2") or "").strip()
        bits = []
        if trans: bits.append(f"Translation: {trans}")
        if comm2: bits.append(f"Commentary: {comm2}")
        if bits:
            joined = " | ".join(bits)
            lines.append(f"[{ch}:{v}] {joined}")
    return "\n".join(lines)

def _model_canonical_tiers(question: str, context_snippets: str,
                           style_hint: str, required_points: str) -> Tuple[str,str,str]:
    """
    Ask model for three tiers in **natural varied format**; preserve model layout.
    We instruct it to output with markers so we can split safely.
    """
    system = (
        "You are a Bhagavad Gita tutor. Answer ONLY from the Bhagavad Gita.\n"
        "Use [chapter:verse] chips when you cite verses. Vary structure naturally; don't force a template.\n"
        "Keep Sanskrit words plain ASCII (Krishna, bhakti, guna)."
    )
    guide = (
        "You will produce three tiers:\n"
        "<<<SHORT>>>\n"
        "- 2–3 sentences; punchy essence; may include 1–2 verse chips.\n"
        "<<<MEDIUM>>>\n"
        "- 3–5 short paragraphs or a bulleted list + brief wrap-up; integrate verse chips.\n"
        "<<<LONG>>>\n"
        "- 6–10 paragraphs mixing narrative + bullets where helpful; weave in chips and insights.\n\n"
        "Answer the user question below. Use ONLY these context snippets; do not invent sources:\n"
        f"{context_snippets}\n\n"
        f"Style hint (optional): {style_hint or '—'}\n"
        f"Required points (optional): {required_points or '—'}\n"
        "Begin."
    )
    try:
        rsp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": f"Question: {question}\n\n{guide}"}],
            temperature=0.2,
            max_tokens=1200,
        )
        text = (rsp.choices[0].message.content or "").strip()
    except Exception as e:
        text = ""

    # Split on markers
    short, medium, long = "", "", ""
    if "<<<SHORT>>>" in text:
        parts = re.split(r"<<<(SHORT|MEDIUM|LONG)>>>", text)
        # parts like ["pre", "SHORT", "...", "MEDIUM", "...", "LONG", "..."]
        cur = None
        buf = {"SHORT":"", "MEDIUM":"", "LONG":""}
        it = iter(parts)
        first = next(it, "")
        for tag, content in zip(it, it):
            buf[tag] = content.strip()
        short = buf["SHORT"].strip()
        medium = buf["MEDIUM"].strip()
        long = buf["LONG"].strip()
    else:
        # Fallback: treat whole as medium
        medium = text

    # Normalize any “Chapter x, Verse y” into [x:y]
    def normalize(body: str) -> str:
        return re.sub(r"Chapter\s+(\d+)\s*(?:,|)\s*Verse\s+(\d+)", r"[\1:\2]", body, flags=re.I)

    return normalize(short), normalize(medium), normalize(long)

def generate_answer_tiers(question: str, verse_whitelist: str,
                          master_lookup: Dict[Tuple[int,int], Dict[str,str]],
                          style_hint: str, required_points: str) -> Tuple[str,str,str]:
    cvs = _parse_whitelist(verse_whitelist)
    ctx = _compose_snippet_context(cvs, master_lookup)
    if not ctx:
        # Degenerate: no snippets — still answer guarded
        s = _model_answer_guarded(question, max_tokens=420)
        return s, s, s
    return _model_canonical_tiers(question, ctx, style_hint, required_points)

# ====================== Admin: synchronous run (legacy) ======================
@app.post("/admin/canonicals/run")
async def admin_run_canonicals(
    x_admin_token: str = Header(None, convert_underscores=False),
    control_path: str = "/data/control_questions_v3.csv",
    master_path: str = "/data/Gita_Master_Index_v1.csv",
    sleep_sec: float = 0.6,
):
    _require_admin(x_admin_token)
    try:
        with open(control_path, "r", encoding="utf-8") as f:
            control_rows = list(csv.DictReader(f))
        with open(master_path, "r", encoding="utf-8") as f:
            master_rows = list(csv.DictReader(f))
        # Build lookup
        master_by_cv = {}
        for r in master_rows:
            try:
                ch = int((r.get("chapter") or "").strip())
                v  = int((r.get("verse") or "").strip())
            except Exception:
                continue
            master_by_cv[(ch, v)] = {
                "translation": (r.get("translation") or "").strip(),
                "commentary2": (r.get("commentary2") or "").strip(),
            }

        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        q_new = 0; q_upd = 0; a_ins = 0; a_upd = 0
        for row in control_rows:
            q_text = (row.get("question_text") or "").strip()
            mt_id = int(row.get("micro_topic_id") or 0)
            whitelist = (row.get("verse_whitelist") or "").strip()
            style = (row.get("style") or "").strip()
            req_points = (row.get("required_points") or "").strip()

            short_md, med_md, long_md = generate_answer_tiers(
                question=q_text,
                verse_whitelist=whitelist,
                master_lookup=master_by_cv,
                style_hint=style,
                required_points=req_points
            )

            # Upsert question
            cur.execute("SELECT id FROM questions WHERE question_text=?", (q_text,))
            rowq = cur.fetchone()
            if rowq:
                qid = rowq["id"]; q_upd += 1
            else:
                cur.execute("""
                    INSERT INTO questions(micro_topic_id, intent, priority, source, question_text)
                    VALUES(?, 'general', 5, 'seed', ?)
                """, (mt_id, q_text))
                qid = cur.lastrowid; q_new += 1

            # Upsert answers
            for tier, text in (("short", short_md), ("medium", med_md), ("long", long_md)):
                cur.execute("""
                    INSERT INTO answers(question_id, length_tier, answer_text)
                    VALUES(?,?,?)
                    ON CONFLICT(question_id, length_tier) DO UPDATE SET answer_text=excluded.answer_text
                """, (qid, tier, text))
                if cur.rowcount == 1:
                    a_ins += 1
                else:
                    a_upd += 1

            conn.commit()
            if sleep_sec and sleep_sec > 0:
                time.sleep(sleep_sec)

        conn.close()
        return {"status":"ok", "result":{
            "questions_inserted": q_new, "questions_updated": q_upd,
            "answers_inserted": a_ins, "answers_updated": a_upd
        }}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ====================== Admin: background job (start/status/stop) ======================
JOB = {
    "running": False,
    "done": False,
    "started_at": None,
    "finished_at": None,
    "processed": 0,
    "total": 0,
    "errors": 0,
    "last_error": "",
    "stop": False,
}
JOB_LOCK = threading.Lock()

def _canonicals_worker(control_path: str, master_path: str, sleep_sec: float):
    with JOB_LOCK:
        JOB.update({
            "running": True, "done": False, "started_at": time.time(),
            "finished_at": None, "processed": 0, "errors": 0, "last_error": "", "stop": False
        })
    try:
        with open(control_path, "r", encoding="utf-8") as f:
            control_rows = list(csv.DictReader(f))
        with open(master_path, "r", encoding="utf-8") as f:
            master_rows = list(csv.DictReader(f))

        master_by_cv = {}
        for r in master_rows:
            try:
                ch = int((r.get("chapter") or "").strip())
                v  = int((r.get("verse") or "").strip())
            except Exception:
                continue
            master_by_cv[(ch, v)] = {
                "translation": (r.get("translation") or "").strip(),
                "commentary2": (r.get("commentary2") or "").strip(),
            }

        total = len(control_rows)
        with JOB_LOCK:
            JOB["total"] = total

        import sqlite3
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        for idx, row in enumerate(control_rows, start=1):
            with JOB_LOCK:
                if JOB["stop"]:
                    break

            q_text = (row.get("question_text") or "").strip()
            mt_id = int(row.get("micro_topic_id") or 0)
            whitelist = (row.get("verse_whitelist") or "").strip()
            style = (row.get("style") or "").strip()
            req_points = (row.get("required_points") or "").strip()

            short_md, med_md, long_md = generate_answer_tiers(
                question=q_text,
                verse_whitelist=whitelist,
                master_lookup=master_by_cv,
                style_hint=style,
                required_points=req_points
            )

            # Upsert question
            cur.execute("SELECT id FROM questions WHERE question_text=?", (q_text,))
            rowq = cur.fetchone()
            if rowq:
                qid = rowq["id"]
            else:
                cur.execute("""
                    INSERT INTO questions(micro_topic_id, intent, priority, source, question_text)
                    VALUES(?, 'general', 5, 'seed', ?)
                """, (mt_id, q_text))
                qid = cur.lastrowid

            # Upsert answers
            for tier, text in (("short", short_md), ("medium", med_md), ("long", long_md)):
                cur.execute("""
                    INSERT INTO answers(question_id, length_tier, answer_text)
                    VALUES(?,?,?)
                    ON CONFLICT(question_id, length_tier) DO UPDATE SET answer_text=excluded.answer_text
                """, (qid, tier, text))
            conn.commit()

            with JOB_LOCK:
                JOB["processed"] = idx

            if sleep_sec and sleep_sec > 0:
                time.sleep(sleep_sec)

        conn.close()
    except Exception as e:
        with JOB_LOCK:
            JOB["errors"] += 1
            JOB["last_error"] = str(e)
    finally:
        with JOB_LOCK:
            JOB["running"] = False
            JOB["done"] = True
            JOB["finished_at"] = time.time()

@app.post("/admin/canonicals/start")
async def admin_canonicals_start(
    x_admin_token: str = Header(None, convert_underscores=False),
    control_path: str = "/data/control_questions_v3.csv",
    master_path: str = "/data/Gita_Master_Index_v1.csv",
    sleep_sec: float = 0.6,
):
    _require_admin(x_admin_token)
    with JOB_LOCK:
        if JOB["running"]:
            return {"status": "already_running", "processed": JOB["processed"], "total": JOB["total"]}
        JOB.update({"stop": False})
    t = threading.Thread(target=_canonicals_worker, args=(control_path, master_path, sleep_sec), daemon=True)
    t.start()
    return {"status": "started"}

@app.get("/admin/canonicals/status")
async def admin_canonicals_status(
    x_admin_token: str = Header(None, convert_underscores=False),
):
    _require_admin(x_admin_token)
    with JOB_LOCK:
        out = dict(JOB)
    pct = 0.0
    if out["total"]:
        pct = round(100.0 * (out["processed"] / float(out["total"])), 2)
    out["percent"] = pct
    return out

@app.post("/admin/canonicals/stop")
async def admin_canonicals_stop(
    x_admin_token: str = Header(None, convert_underscores=False),
):
    _require_admin(x_admin_token)
    with JOB_LOCK:
        if not JOB["running"]:
            return {"status": "not_running"}
        JOB["stop"] = True
    return {"status": "stopping"}
