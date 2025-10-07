# main.py — Gita Q&A v2 (Explain + Definition + Thematic List + Model-only answers; UI unchanged)
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
USE_EMBED = os.getenv("USE_EMBED", "0") == "1"  # kept for compatibility
RAG_SOURCE = os.getenv("RAG_SOURCE", "").strip().lower()  # e.g. "commentary2"

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

# Serve widget.js at /static/widget.js
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

# ---------- Ingest endpoints ----------
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
            "Which verses talk about devotion?",
            "What is sthita prajna?",
            "Verses on meditation",
            "Karma vs Bhakti vs Jnana"
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
    # unique preserving order
    seen = set()
    uniq: List[str] = []
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

# --- Retrieval diversification ---
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

# --- Model-only answer (fast, nicely formatted, Gita-guarded) ---
def _model_answer_guarded(question: str, max_tokens: int = 700) -> str:
    """
    Lets the model answer directly with its best format, but keeps it inside Gita boundaries.
    """
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

# --- Structured synthesis (fallback essay from retrieved context) ---
def _synthesize_structured(question: str, ctx_lines: List[str],
                           min_sections: int = 3,
                           max_sections: int = 5,
                           target_words_low: int = 350,
                           target_words_high: int = 450,
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

    # ----- Direct verse path (Explain / Word meaning) -----
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

        # Explain — order: WM -> Summary(DB) -> Commentary2 -> Commentary1
        neighbors = [dict(n) for n in fetch_neighbors(conn, ch, v, k=1)]

        c2 = _clean_text(row.get("commentary2") or "")
        db_summary = _clean_text(row.get("summary") or "")  # <-- use DB summary FIRST
        summary = db_summary
        generated = False
        if not summary and c2:
            # Fallback: synthesize short summary from commentary2 only if DB summary missing
            prompt = (
                "Summarize the following commentary in 3–5 plain sentences, "
                "grounded in the text. No markup, no quotes, concise:\n\n" + c2[:3000]
            )
            summary = _summarize(prompt, max_tokens=320)
            generated = True

        resp = {
            "mode": "explain",
            "chapter": ch,
            "verse": v,
            "title": row.get("title") or "",
            "sanskrit": row.get("sanskrit") or "",
            "roman": row.get("roman") or "",
            "colloquial": row.get("colloquial") or "",
            "translation": row.get("translation") or "",
            "word_meanings": row.get("word_meanings") or "",
            "summary": summary or "",
            "commentary2": c2,
            "commentary1": _clean_text(row.get("commentary1") or ""),
            "capsule_url": row.get("capsule_url") or "",
            "neighbors": [
                {"chapter": int(n["chapter"]), "verse": int(n["verse"]), "translation": n.get("translation") or ""}
                for n in neighbors
            ],
            "citations": [f"[{ch}:{v}]"],
            "debug": {
                "mode": "explain",
                "used_db_summary": bool(db_summary),
                "summary_fallback_generated": generated
            }
        }
        return resp

    # ----- Decide broad path: definition vs verse-list vs model-only essay -----
    # (We still keep FTS for LIST mode; everything else goes model-only by default.)
    q_expanded = _expand_query(q)
    fts_rows = search_fts(conn, q_expanded, limit=60)  # give list mode some headroom

    # LIST mode?
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
            # Title first, then translation; widget will render [C:V] clickable pill
            line = f"{title} — {trans} [{label}]".strip()
            lines.append(line)
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

    # DEFINITION mode? (short terms like “sthita prajna”, “krodha”)
    if _is_definition_query(q) or (len(q.split()) <= 3):
        # Use model directly (fast) but ask it to include 2–3 citations
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
        except Exception:
            ans = ""

        # Pull out any [C:V] to surface pills
        cites = _extract_citations_from_text(ans)
        return {
            "mode": "definition",
            "answer": ans if ans else NO_MATCH_MESSAGE,
            "citations": [f"[{c}]" for c in cites[:8]],
            "suggestions": ["More detail", "Show related verses"],
            "embeddings_used": False,
            "debug": {"mode": "definition", "model_only": True, "cites_found": len(cites)}
        }

    # MODEL-ONLY essay/explanation (default for thematic questions now)
    ans = _model_answer_guarded(q, max_tokens=700)
    if not ans:
        # Fallback to retrieved essay if model call fails
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

    # Happy path: model-only thematic answer
    cites = _extract_citations_from_text(ans)
    return {
        "mode": "model_only",
        "answer": ans,
        "citations": [f"[{c}]" for c in cites[:8]],
        "suggestions": _make_dynamic_suggestions(q, cites[:5]),
        "embeddings_used": False,
        "debug": {"mode": "model_only"}
    }
