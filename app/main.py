# main.py — Gita Q&A v2 (Explain summary from commentary2 + term lists + safe RAG)
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
USE_EMBED = os.getenv("USE_EMBED", "0") == "1"

# Optional: restrict broad/thematic RAG to commentary2 only
RAG_SOURCE = os.getenv("RAG_SOURCE", "").strip().lower()  # "" or "commentary2"

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

# Serve widget.js from /app
app.mount("/static", StaticFiles(directory="app"), name="static")

# --- Boot DB ---
init_db()

# ---------- UI (unchanged) ----------
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

# ---------- Ingest ----------
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

# ---------- Debug helpers ----------
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
    return { "suggestions": [
        "Explain 2:47",
        "Which verses talk about devotion?",
        "What is sthita prajna?",
        "Verses on meditation",
        "Karma vs Bhakti vs Jnana"
    ]}

# ---------- Core helpers ----------
RE_CV = re.compile(r"\b([1-9]|1[0-8])[:\. ](\d{1,3})\b")
CITE_RE = re.compile(r"\[\s*(?:C\s*:\s*)?(\d{1,2})\s*[:.]\s*(\d{1,3})\s*\]")

def _extract_ch_verse(text: str) -> Optional[Tuple[int, int]]:
    m = RE_CV.search(text or "")
    if not m: return None
    return int(m.group(1)), int(m.group(2))

def _summarize(prompt: str, max_tokens: int = 320, temp: float = 0.2) -> str:
    try:
        rsp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[
                {"role": "system", "content": "Plain text only. No markup. Be concise and faithful to the provided text."},
                {"role": "user", "content": prompt},
            ],
            temperature=temp,
            max_tokens=max_tokens,
        )
        return (rsp.choices[0].message.content or "").strip()
    except Exception:
        return ""

def _clean_text(t: str) -> str:
    if not t: return ""
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.replace("[C:V]", "").strip()

def _best_text_block(row: Dict[str, Any], force_source: Optional[str] = None) -> str:
    if force_source == "commentary2":
        return _clean_text(row.get("commentary2") or "")
    for k in ("commentary2", "commentary1", "translation", "colloquial", "roman", "title"):
        v = _clean_text(row.get(k) or "")
        if v: return v
    return ""

def _extract_citations_from_text(text: str) -> List[str]:
    out: List[str] = []
    for m in CITE_RE.finditer(text or ""):
        ch, v = int(m.group(1)), int(m.group(2))
        if 1 <= ch <= 18 and 1 <= v <= 200:
            out.append(f"{ch}:{v}")
    uniq = []
    seen = set()
    for c in out:
        if c in seen: continue
        seen.add(c); uniq.append(c)
    return uniq

# very small theme expansion (keeps your earlier behavior)
THEME_EXPAND = {
    "anger": ["anger", "krodha", "wrath", "rage", "ire"],
    "desire": ["desire", "kama", "craving", "longing"],
    "self": ["Self", "Atman", "Purusha", "Kshetrajna"],
    "devotion": ["devotion", "bhakti", "worship", "surrender"],
    "meditation": ["meditation", "dhyana", "concentration", "mind control"],
    "detachment": ["detachment", "vairagya", "equanimity", "non-attachment"],
}
def _expand_query(q: str) -> str:
    ql = (q or "").lower()
    terms: List[str] = []
    for key, syns in THEME_EXPAND.items():
        if key in ql: terms.extend(syns)
    if not terms: return q
    return q + " OR " + " OR ".join(dict.fromkeys(terms))

def _diversify_hits(merged: List[Tuple[int,int,Dict]],
                    per_chapter:int=2, max_total:int=12,
                    neighbor_radius:int=1, min_distinct_chapters:int=3) -> List[Tuple[int,int,Dict]]:
    selected: List[Tuple[int,int,Dict]] = []
    per_ch = defaultdict(int)
    def is_neighbor(ch:int,v:int)->bool:
        for sch,sv,_ in selected:
            if ch==sch and abs(v-sv)<=neighbor_radius: return True
        return False
    for ch,v,data in merged:
        if len(selected)>=max_total: break
        if per_ch[ch]>=per_chapter: continue
        if is_neighbor(ch,v): continue
        selected.append((ch,v,data)); per_ch[ch]+=1
    if len({ch for ch,_,_ in selected})<min_distinct_chapters:
        for ch,v,data in merged:
            if len(selected)>=max_total: break
            if per_ch[ch]>=per_chapter: continue
            if any((ch==sch and v==sv) for sch,sv,_ in selected): continue
            selected.append((ch,v,data)); per_ch[ch]+=1
    return selected[:max_total]

# ---------- Term-mode detection ----------
TERM_ASK_RE = re.compile(r"\bwhich\s+verses?\s+(contain|mention|talk\s+about|include)\s+(.+)", re.I)
def _looks_like_term_query(q: str) -> Optional[str]:
    """Return the term if it looks like a term search; else None."""
    q = (q or "").strip()
    m = TERM_ASK_RE.search(q)
    if m:
        term = m.group(2).strip()
        term = re.sub(r"[?.!,;:]$", "", term)
        return term
    # simple single/dual-token heuristic (no chapter:verse present)
    if not RE_CV.search(q):
        parts = re.findall(r"[A-Za-zĀ-ž\-']+", q)
        if 1 <= len(parts) <= 2:
            return " ".join(parts)
    return None

# ---------- Synthesis (2 paragraphs for broad answers) ----------
def _synthesize_two_paras(question:str, ctx_lines:List[str]) -> str:
    ctx = "\n".join(ctx_lines)[:6000]
    prompt = (
        "You are a Bhagavad Gita assistant. Use ONLY the Context lines below.\n"
        "Write 2 short paragraphs (plain text, no bullets). Weave citations like [chapter:verse] when relevant.\n"
        f"Question: {question}\n\nContext (each line = [chapter:verse] prose):\n{ctx}\n"
    )
    return _summarize(prompt, max_tokens=480, temp=0.2)

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

    # 1) Explain / verse path
    cv = _extract_ch_verse(q)
    if cv:
        ch, v = cv
        row = fetch_exact(conn, ch, v)
        if not row:
            fts_rows = search_fts(conn, f"{ch}:{v}", limit=5)
            if not fts_rows:
                return {"answer": NO_MATCH_MESSAGE, "citations": []}
            row = fts_rows[0]

        # Build a summary **from commentary2** (fallbacks: commentary1 → translation)
        base = _clean_text(row.get("commentary2") or "") \
               or _clean_text(row.get("commentary1") or "") \
               or _clean_text(row.get("translation") or "")
        summary = ""
        if base:
            prompt = (
                f"Summarize the following commentary into 2–3 plain sentences. "
                f"Keep it faithful. Include the citation [C:V] somewhere.\n\n{base}"
            )
            summary = _summarize(prompt)

        # Suggestions: include a **fully qualified pill** for more detail
        suggestions = [f"More detail on {ch}:{v}"]

        return {
            "mode": "explain",
            "chapter": ch,
            "verse": v,
            "title": row.get("title") or "",
            "sanskrit": row.get("sanskrit") or "",
            "roman": row.get("roman") or "",
            "colloquial": row.get("colloquial") or "",
            "translation": row.get("translation") or "",
            # hide commentaries on first pass (widget shows only present fields)
            "summary": summary or "",
            "citations": [f"[{ch}:{v}]"],
            "suggestions": suggestions,
            "ctx_source": "commentary2" if row.get("commentary2") else ("mixed" if row.get("commentary1") else "none"),
            "used_commentary2": bool(row.get("commentary2")),
        }

    # 2) More detail on C:V
    mdetail = re.search(r"\bmore\s+detail\s+on\s+([1-9]|1[0-8])[:\. ](\d{1,3})\b", q, re.I)
    if mdetail:
        ch, v = int(mdetail.group(1)), int(mdetail.group(2))
        row = fetch_exact(conn, ch, v)
        if not row:
            return {"answer": NO_MATCH_MESSAGE, "citations": []}
        return {
            "mode": "commentary_detail",
            "chapter": ch,
            "verse": v,
            "title": row.get("title") or "",
            "commentary2": row.get("commentary2") or "",
            "commentary1": row.get("commentary1") or "",
            "citations": [f"[{ch}:{v}]"],
            "ctx_source": "commentary2" if row.get("commentary2") else ("mixed" if row.get("commentary1") else "none"),
            "used_commentary2": bool(row.get("commentary2")),
        }

    # 3) Term-style list: “which verses contain …” OR short single/dual-word query
    term = _looks_like_term_query(q)
    if term:
        # prefer verses where commentary2 mentions the term; fallback to everything
        q_fts = f'"{term}"'
        rows = search_fts(conn, q_fts, limit=60)
        # Build list: 2:63 — <translation…> [2:63]
        lines: List[str] = []
        cites: List[str] = []
        seen = set()
        for r in rows:
            ch, v = int(r["chapter"]), int(r["verse"])
            key = (ch, v)
            if key in seen: continue
            seen.add(key)
            trans = _clean_text(r.get("translation") or r.get("colloquial") or r.get("roman") or r.get("title") or "")
            if not trans: continue
            # keep each item short
            if len(trans) > 220: trans = trans[:220].rsplit(" ", 1)[0] + "…"
            lines.append(f"{ch}:{v} — {trans} [{ch}:{v}]")
            cites.append(f"{ch}:{v}")
            if len(lines) >= 20: break
        if not lines:
            return {"mode": "term_list", "answer": NO_MATCH_MESSAGE, "citations": []}
        return {
            "mode": "term_list",
            "answer": "\n\n".join(lines),
            "citations": [f"[{c}]" for c in cites[:8]],
            "ctx_source": "mixed",
            "used_commentary2": any(_clean_text(r.get("commentary2") or "") for r in rows),
        }

    # 4) Broad/thematic RAG
    q_expanded = _expand_query(q)
    fts_rows = search_fts(conn, q_expanded, limit=24)

    emb = None
    embeddings_used = False
    if USE_EMBED:
        try:
            emb = embed_store.query(q, top_k=6, where={"topic": TOPIC_DEFAULT})
            embeddings_used = True
        except Exception as e:
            print("Embedding query failed:", e)
            embeddings_used = False

    # merge hits (keep FTS order)
    def _merge_hits(fts_rows: List[Dict], embed_hits: Dict) -> List[Tuple[int,int,Dict]]:
        results: List[Tuple[int,int,Dict]] = []
        seen = set()
        for r in fts_rows:
            key = (int(r["chapter"]), int(r["verse"]))
            if key in seen: continue
            seen.add(key); results.append((key[0], key[1], dict(r)))
        if embed_hits and embed_hits.get("metadatas"):
            for metas in embed_hits["metadatas"]:
                for m in metas:
                    ch = int(m.get("chapter") or 0); v = int(m.get("verse") or 0)
                    if ch<=0 or v<=0: continue
                    key = (ch,v)
                    if key in seen: continue
                    seen.add(key); results.append((ch,v,m))
        return results

    merged = _merge_hits(fts_rows, emb or {})
    if not merged:
        return {"mode":"broad","answer":NO_MATCH_MESSAGE,"citations":[],"suggestions":[],"embeddings_used":embeddings_used}

    diversified = _diversify_hits(
        merged, per_chapter=2, max_total=12, neighbor_radius=1, min_distinct_chapters=3
    )

    ctx_lines: List[str] = []
    cites_unique: List[str] = []
    chapters_in_ctx: List[str] = []
    force_source = "commentary2" if RAG_SOURCE == "commentary2" else None

    for ch, v, data in diversified:
        cv = f"{ch}:{v}"
        block = _best_text_block(data if isinstance(data, dict) else {}, force_source=force_source)
        if not block: continue
        if len(block) > 600: block = block[:600].rsplit(" ", 1)[0] + "…"
        ctx_lines.append(f"[{cv}] {block}")
        if cv not in cites_unique: cites_unique.append(cv)
        chapters_in_ctx.append(str(ch))
        if len(ctx_lines) >= 10: break

    if not ctx_lines:
        return {"mode":"broad","answer":NO_MATCH_MESSAGE,"citations":cites_unique[:8],"suggestions":[],"embeddings_used":embeddings_used}

    # 2 short paragraphs (not 5–6 sections)
    ans = _synthesize_two_paras(q, ctx_lines)
    model_cites = _extract_citations_from_text(ans)

    # merge citations (model first, then retrieved)
    ordered: List[str] = []
    seen = set()
    for c in model_cites + cites_unique:
        if c in seen: continue
        seen.add(c); ordered.append(c)

    return {
        "mode": "rag",
        "answer": ans if ans else NO_MATCH_MESSAGE,
        "citations": ordered[:8],
        "suggestions": ["More detail on " + ordered[0]] if ordered else [],
        "embeddings_used": embeddings_used,
        "ctx_source": "commentary2" if RAG_SOURCE == "commentary2" else "mixed",
        "used_commentary2": any("commentary2" in (line.lower()) for line in ctx_lines),
    }
