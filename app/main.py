# main.py — Gita Q&A v2 (Explain: summary from commentary2 + More detail; Broad: commentary2-only; Verse listings)
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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
from . import embed_store

# --- Environment ---
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*")
GEN_MODEL = os.getenv("GEN_MODEL", "gpt-4o-mini")
NO_MATCH_MESSAGE = os.getenv(
    "NO_MATCH_MESSAGE",
    "I couldn't find enough in the corpus to answer that. Try a specific verse like 12:12, or rephrase your question.",
)
TOPIC_DEFAULT = os.getenv("TOPIC_DEFAULT", "gita")
USE_EMBED = os.getenv("USE_EMBED", "0") == "1"  # set to 1 later to enable embeddings on broad queries

# --- OpenAI client ---
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI(title="Gita Q&A v2")

# --- CORS ---
if ALLOW_ORIGINS == "*":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    allowed = [o.strip() for o in ALLOW_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Serve widget.js at /static/widget.js (served from the app/ directory)
app.mount("/static", StaticFiles(directory="app"), name="static")

# --- Boot DB ---
init_db()

# ---------- Home (unchanged UI) ----------
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
  s.src = '/static/widget.js?v=' + Date.now();   // auto cache-buster
  s.async = true;                                // don't block page render
  s.onload = function () {
    // only run once widget.js is ready
    if (window.GitaWidget && GitaWidget.mount) {
      GitaWidget.mount({ root: '#gita', apiBase: '' });
      console.log('[GW] mounted via dynamic loader');
    } else {
      console.error('GitaWidget not found after load');
    }
  };
  s.onerror = function (e) {
    console.error('Failed to load widget.js', e);
  };
  document.head.appendChild(s);
})();
</script>
</body>
</html>
    """

# ---------- Ingest endpoints ----------
@app.post("/ingest_sheet_sql")
async def ingest_sheet_sql(file: UploadFile = File(...)):
    try:
        bytes_ = await file.read()
        rows = load_sheet_to_rows(bytes_, file.filename)
        conn = get_conn()
        n = bulk_upsert(conn, rows)
        ensure_fts(conn)  # rebuild the contentless FTS index so broad queries work
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

# ---------- Lookup & debug ----------
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
            "Which verses contain krodha?",
            "Verses on meditation",
            "What is sthita prajna?",
            "Karma vs Bhakti vs Jnana",
        ]
    }

# ---------- Helpers ----------
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

def _summarize(prompt: str, max_tokens: int = 360, temp: float = 0.2) -> str:
    """Model helper (plain text; no markup)."""
    try:
        rsp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[
                {"role": "system", "content": "You answer succinctly in plain text with no markup."},
                {"role": "user", "content": prompt},
            ],
            temperature=temp,
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

def _extract_citations_from_text(text: str) -> List[str]:
    out: List[str] = []
    for m in CITE_RE.finditer(text or ""):
        ch, v = int(m.group(1)), int(m.group(2))
        if 1 <= ch <= 18 and 1 <= v <= 200:
            out.append(f"{ch}:{v}")
    # unique preserving order
    seen = set()
    uniq: List[str] = []
    for c in out:
        if c in seen: continue
        seen.add(c); uniq.append(c)
    return uniq

# --- Query type detectors ---
LIST_RE = re.compile(r"\b(verses?\s+(that\s+)?(contain|mention|talk\s+about|have)\s+)(?P<term>.+)$", re.I)

def _is_listing_query(q: str) -> Optional[str]:
    m = LIST_RE.search(q or "")
    if m:
        return m.group("term").strip()
    return None

def _is_single_term(q: str) -> Optional[str]:
    # very light heuristic: 1-2 words, not a verse, not a question mark
    q2 = (q or "").strip()
    if RE_CV.search(q2): return None
    if len(q2.split()) <= 2 and " " in q2 or len(q2.split()) == 1:
        # avoid empty/very short
        if len(q2) >= 2:
            return q2
    return None

# --- FTS helpers for composing listing/term answers ---
def _fts_find_verses(conn, term: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Find verses where the TERM appears (prefer commentary2, then translation/title).
    Returns rows with chapter, verse, title, translation, commentary2.
    """
    term = term.strip()
    if not term: return []
    # Compose a permissive OR query across fields; unicode61 will handle diacritics
    q = f'"{term}" OR {term}'
    rows = search_fts(conn, q, limit=120)  # get a bigger pool; we’ll prune below

    # Rank/sort lightly by: has commentary2 hit -> earlier; otherwise translation/title hit
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for r in rows:
        txt_c2 = (r.get("commentary2") or "").lower()
        txt_tr = (r.get("translation") or "").lower()
        txt_ti = (r.get("title") or "").lower()
        score = 0
        if term.lower() in txt_c2: score += 3
        if term.lower() in txt_tr: score += 2
        if term.lower() in txt_ti: score += 1
        scored.append((score, dict(r)))

    scored.sort(key=lambda x: (-x[0], int(x[1]["chapter"]), int(x[1]["verse"])))

    out: List[Dict[str, Any]] = []
    seen = set()
    for _, r in scored:
        cv = (int(r["chapter"]), int(r["verse"]))
        if cv in seen: continue
        seen.add(cv)
        out.append(r)
        if len(out) >= limit: break
    return out

# --- Structured synthesis (broad, commentary2-only, 2 paragraphs) ---
def _synthesize_broad_from_c2(question: str, ctx_lines: List[str]) -> str:
    ctx = "\n".join(ctx_lines)[:6000]
    prompt = (
        "Use ONLY the Context below (excerpts from commentary2). "
        "Write 2–3 natural paragraphs, no bullets/sections, plain text. "
        "Include inline verse refs like [2:47] when the sentence uses them. "
        "If context is insufficient, say so briefly.\n\n"
        f"Question: {question}\n\n"
        "Context (each line = [chapter:verse] prose):\n"
        f"{ctx}\n"
    )
    return _summarize(prompt, max_tokens=520, temp=0.3)

# ---------- /ask ----------
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

    # ----- "More detail X.Y" requests -----
    m_more = re.search(r"\bmore\s+detail\b.*?(\d{1,2})[:\.](\d{1,3})", q, re.I)
    if m_more:
        ch, v = int(m_more.group(1)), int(m_more.group(2))
        row = fetch_exact(conn, ch, v)
        if not row:
            return {"answer": f"Chapter {ch}, Verse {v} does not exist.", "citations": []}
        c2 = _clean_text(row.get("commentary2") or "")
        c1 = _clean_text(row.get("commentary1") or "")
        blocks: List[str] = []
        if c2:
            blocks.append("Commentary:\n" + c2)
        if c1:
            blocks.append("Shankara's commentary:\n" + c1)
        return {
            "mode": "detail",
            "chapter": ch,
            "verse": v,
            "answer": "\n\n".join(blocks) if blocks else "No commentary available.",
            "citations": [f"[{ch}:{v}]"],
            "suggestions": []
        }

    # ----- Verse-specific "Explain X.Y" (or any X.Y) -----
    cv = _extract_ch_verse(q)
    if cv:
        ch, v = cv
        row = fetch_exact(conn, ch, v)
        if not row:
            fts_rows = search_fts(conn, f"{ch}:{v}", limit=5)
            if not fts_rows:
                return {"answer": NO_MATCH_MESSAGE, "citations": []}
            row = fts_rows[0]

        c2 = _clean_text(row.get("commentary2") or "")
        # If no commentary2, fall back to translation for summary
        base_txt = c2 if c2 else _clean_text(row.get("translation") or "")

        # Generate summary FROM commentary2 (or fallback)
        summary_prompt = (
            "Summarize the following in 2–4 sentences, plain text, no markup. "
            "Include at least one inline citation like [C:V] using the verse number provided.\n\n"
            f"Verse: {ch}:{v}\n"
            f"Text:\n{base_txt}\n"
        )
        summary = _summarize(summary_prompt, max_tokens=220, temp=0.2)

        # Build response object
        neighbors = fetch_neighbors(conn, ch, v, k=1)
        return {
            "mode": "explain",
            "chapter": ch,
            "verse": v,
            "title": row.get("title") or "",
            "sanskrit": row.get("sanskrit") or "",
            "roman": row.get("roman") or "",
            "colloquial": row.get("colloquial") or "",
            "translation": row.get("translation") or "",
            "word_meanings": row.get("word_meanings") or "",
            "capsule_url": row.get("capsule_url") or "",
            "commentary1": row.get("commentary1") or "",
            "commentary2": row.get("commentary2") or "",
            # NEW: Summary comes from commentary2 (prefixed client-side)
            "summary": summary or "",
            "neighbors": [
                {"chapter": int(n["chapter"]), "verse": int(n["verse"]), "translation": n["translation"] or ""}
                for n in neighbors
            ],
            # IMPORTANT: no top citation pill in Explain mode (you asked to hide it)
            "citations": [],
            "suggestions": [f"More detail {ch}.{v}"]
        }

    # ----- Listing queries like "Which verses contain krodha" -----
    term_for_list = _is_listing_query(q)
    if term_for_list:
        verses = _fts_find_verses(conn, term_for_list, limit=20)
        if not verses:
            return {"mode": "list", "answer": NO_MATCH_MESSAGE, "citations": [], "suggestions": []}

        # Build plain-text list; include [C:V] to make them clickable in your widget
        lines: List[str] = []
        for r in verses:
            ch, v = int(r["chapter"]), int(r["verse"])
            title = _clean_text(r.get("title") or "")
            trans = _clean_text(r.get("translation") or "")
            block = f"{ch}:{v} — {title}\n{trans}\n[{ch}:{v}]"
            lines.append(block)
        answer = "\n\n".join(lines)
        return {
            "mode": "list",
            "answer": answer,
            "citations": [],  # inline [C:V] makes them clickable already
            "suggestions": []
        }

    # ----- Single-term queries like "krodha" (define + list) -----
    term = _is_single_term(q)
    if term:
        verses = _fts_find_verses(conn, term, limit=20)

        # Short definition from commentary2 context
        ctx_lines: List[str] = []
        for r in verses[:8]:
            ch, v = int(r["chapter"]), int(r["verse"])
            c2 = _clean_text(r.get("commentary2") or "")
            if c2:
                snippet = c2 if len(c2) < 320 else c2[:320].rsplit(" ", 1)[0] + "…"
                ctx_lines.append(f"[{ch}:{v}] {snippet}")

        definition = ""
        if ctx_lines:
            definition = _synthesize_broad_from_c2(f"What does the term '{term}' mean in the Gita? Define briefly.", ctx_lines)

        # Verse list (as above)
        if verses:
            lines: List[str] = []
            for r in verses:
                ch, v = int(r["chapter"]), int(r["verse"])
                title = _clean_text(r.get("title") or "")
                trans = _clean_text(r.get("translation") or "")
                block = f"{ch}:{v} — {title}\n{trans}\n[{ch}:{v}]"
                lines.append(block)
            listing = "\n\n".join(lines)
            answer = (definition + "\n\n" if definition else "") + listing
            return {
                "mode": "term",
                "answer": answer,
                "citations": [],
                "suggestions": []
            }
        else:
            return {
                "mode": "term",
                "answer": definition or NO_MATCH_MESSAGE,
                "citations": [],
                "suggestions": []
            }

    # ----- Broad/thematic questions: commentary2-only, 2–3 paragraphs -----
    fts_rows = search_fts(conn, q, limit=24)
    if not fts_rows:
        return {"mode": "broad", "answer": NO_MATCH_MESSAGE, "citations": [], "suggestions": []}

    # Build context strictly from commentary2
    ctx_lines: List[str] = []
    cites: List[str] = []
    seen = set()
    for r in fts_rows:
        ch, v = int(r["chapter"]), int(r["verse"])
        cv = (ch, v)
        if cv in seen: continue
        seen.add(cv)
        c2 = _clean_text(r.get("commentary2") or "")
        if not c2: continue
        short = c2 if len(c2) < 480 else c2[:480].rsplit(" ", 1)[0] + "…"
        ctx_lines.append(f"[{ch}:{v}] {short}")
        cites.append(f"{ch}:{v}")
        if len(ctx_lines) >= 10:
            break

    if not ctx_lines:
        return {"mode": "broad", "answer": NO_MATCH_MESSAGE, "citations": [], "suggestions": []}

    ans = _synthesize_broad_from_c2(q, ctx_lines)

    return {
        "mode": "broad",
        "answer": ans if ans else NO_MATCH_MESSAGE,
        "citations": list(dict.fromkeys(cites))[:8],
        "suggestions": [f"More detail {q}"]
    }
