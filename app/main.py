import os
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .db import get_conn, init_db, bulk_upsert, fetch_exact, fetch_neighbors, search_fts, stats, ensure_fts

from .ingest import load_sheet_to_rows, ingest_commentary
from . import embed_store

# --- Environment ---
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*")
GEN_MODEL = os.getenv("GEN_MODEL", "gpt-4o-mini")
NO_MATCH_MESSAGE = os.getenv("NO_MATCH_MESSAGE", "I couldn't find enough in the corpus to answer that. Try a specific verse like 12:12, or rephrase your question.")
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

# Serve widget.js at /static/widget.js
app.mount("/static", StaticFiles(directory="app"), name="static")

# --- Boot DB ---
init_db()

RE_CV = re.compile(r"\b([1-9]|1[0-8])[:\. ](\d{1,2})\b")


class AskPayload(BaseModel):
    question: str
    topic: Optional[str] = None


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
  <script src="/static/widget.js?v=wm-fix-3"></script>
  <script>
    GitaWidget.mount({ root: '#gita', apiBase: '' });
  </script>
</body>
</html>
    """


# add ensure_fts to your imports at the top of main.py:
# from .db import get_conn, init_db, bulk_upsert, fetch_exact, fetch_neighbors, search_fts, stats, ensure_fts

@app.post("/ingest_sheet_sql")
async def ingest_sheet_sql(file: UploadFile = File(...)):
    try:
        bytes_ = await file.read()
        rows = load_sheet_to_rows(bytes_, file.filename)
        conn = get_conn()
        n = bulk_upsert(conn, rows)
        ensure_fts(conn)  # <— rebuild the contentless FTS index so broad queries work
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
            "Word meaning 2:47",
            "Which verses talk about devotion?",
            "What is sthita prajna?",
            "Verses on meditation",
            "Karma vs Bhakti vs Jnana"
        ]
    }


def _extract_ch_verse(text: str) -> Optional[Tuple[int,int]]:
    m = RE_CV.search(text)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)))


def _is_word_meaning_query(q: str) -> bool:
    ql = q.lower()
    return ("word meaning" in ql) or ("meaning" in ql and RE_CV.search(ql) is not None)


def _summarize(prompt: str) -> str:
    try:
        rsp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[
                {"role": "system", "content": "You answer succinctly in plain text with no markup."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=300,
        )
        return rsp.choices[0].message.content.strip()
    except Exception:
        return ""


def _merge_hits(fts_rows: List[Dict], embed_hits: Dict) -> List[Tuple[int,int,Dict]]:
    results = []
    seen = set()
    for r in fts_rows:
        key = (int(r["chapter"]), int(r["verse"]))
        if key in seen:
            continue
        seen.add(key)
        results.append((key[0], key[1], dict(r)))
    if embed_hits and embed_hits.get("metadatas"):
        for metas in embed_hits["metadatas"]:
            for m in metas:
                ch = int(m.get("chapter") or 0)
                v = int(m.get("verse") or 0)
                if ch <= 0 or v <= 0:
                    continue
                key = (ch, v)
                if key in seen:
                    continue
                seen.add(key)
                results.append((ch, v, m))
    return results[:10]


@app.post("/ask")
async def ask(payload: AskPayload):
    q = (payload.question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Empty question")

    topic = payload.topic or TOPIC_DEFAULT
    cv = _extract_ch_verse(q)
    conn = get_conn()

    if cv:
        ch, v = cv
        row = fetch_exact(conn, ch, v)
        if not row:
            fts_rows = search_fts(conn, f"{ch}:{v}", limit=5)
            if not fts_rows:
                return {"answer": NO_MATCH_MESSAGE, "citations": []}
            row = fts_rows[0]

        if _is_word_meaning_query(q):
            wm = row["word_meanings"] or ""
            return {
                "mode": "word_meaning",
                "chapter": ch,
                "verse": v,
                "answer": wm if wm else NO_MATCH_MESSAGE,
                "citations": [f"[{ch}:{v}]"]
            }

        neighbors = fetch_neighbors(conn, ch, v, k=1)
        parts = [(ch, v, row["translation"] or "")]
        for n in neighbors:
            parts.append((int(n["chapter"]), int(n["verse"]), n["translation"] or ""))

        context_txt = "\n".join([f"{c}:{vv} {t}".strip() for c, vv, t in parts if t])
        prompt = (
            "Summarize the central teaching of this verse in 2-3 plain sentences, "
            "no formatting, and include the citation [C:V] somewhere in the text.\n\n" + context_txt
        )
        summary = _summarize(prompt)

        return {
            "mode": "explain",
            "chapter": ch,
            "verse": v,
            "title": row["title"] or "",
            "sanskrit": row["sanskrit"] or "",
            "roman": row["roman"] or "",
            "colloquial": row["colloquial"] or "",
            "translation": row["translation"] or "",
            "word_meanings": row["word_meanings"] or "",
            "capsule_url": row["capsule_url"] or "",
            "summary": summary or "",
            "neighbors": [
                {"chapter": int(n["chapter"]), "verse": int(n["verse"]), "translation": n["translation"] or ""}
                for n in neighbors
            ],
            "citations": [f"[{ch}:{v}]"]
        }

    # Broad query: FTS primary; embeddings optional
    fts_rows = search_fts(conn, q, limit=10)

    emb = None
    embeddings_used = False
    if USE_EMBED:
        try:
            emb = embed_store.query(q, top_k=6, where={"topic": topic})
            embeddings_used = True
        except Exception as e:
            print("Embedding query failed:", e)
            embeddings_used = False

    merged = _merge_hits(fts_rows, emb or {})

    if not merged:
        return {"mode": "broad", "answer": NO_MATCH_MESSAGE, "citations": [], "embeddings_used": embeddings_used}

    ctx_lines: List[str] = []
    cites: List[str] = []
    for ch, v, data in merged:
        cites.append(f"[{ch}:{v}]")
        if isinstance(data, dict) and "translation" in data:
            s = data.get("translation") or data.get("roman") or data.get("title") or ""
            if s:
                ctx_lines.append(f"{ch}:{v} {s}")

    if not ctx_lines:
        return {"mode": "broad", "answer": NO_MATCH_MESSAGE, "citations": list(dict.fromkeys(cites))[:8], "embeddings_used": embeddings_used}

    ctx = "\n".join(ctx_lines)
    prompt = (
        "Answer the question using only the provided context. Keep it concise, plain text, no markup. "
        "Weave in verse citations like [C:V] when relevant.\n\nQuestion: " + q + "\n\nContext:\n" + ctx
    )
    ans = _summarize(prompt)

    return {
        "mode": "broad",
        "answer": ans if ans else NO_MATCH_MESSAGE,
        "citations": list(dict.fromkeys(cites))[:8],
        "embeddings_used": embeddings_used
    }
