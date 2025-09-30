
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import get_conn, init_db, bulk_upsert, fetch_exact, fetch_neighbors, search_fts, stats
from .ingest import load_sheet_to_rows, ingest_commentary
from . import embed_store

# --- Environment ---
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*")
GEN_MODEL = os.getenv("GEN_MODEL", "gpt-4o-mini")
NO_MATCH_MESSAGE = os.getenv("NO_MATCH_MESSAGE", "I couldn't find enough in the corpus to answer that. Try a specific verse like 12:12, or rephrase your question.")
TOPIC_DEFAULT = os.getenv("TOPIC_DEFAULT", "gita")

# --- OpenAI client (new SDK style) ---
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

# --- Boot DB ---
init_db()

RE_CV = re.compile(r"\b([1-9]|1[0-8])[:\. ](\d{1,2})\b")


class AskPayload(BaseModel):
    question: str
    topic: Optional[str] = None


@app.post("/ingest_sheet_sql")
async def ingest_sheet_sql(file: UploadFile = File(...)):
    try:
        bytes_ = await file.read()
        rows = load_sheet_to_rows(bytes_, file.filename)
        conn = get_conn()
        n = bulk_upsert(conn, rows)
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
    # session-agnostic starter pills
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


# --- ASK routing helpers ---

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
    # FTS first
    for r in fts_rows:
        key = (int(r["chapter"]), int(r["verse"]))
        if key in seen:
            continue
        seen.add(key)
        results.append((key[0], key[1], dict(r)))
    # Embedding next
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

    # Direct verse?
    cv = _extract_ch_verse(q)
    conn = get_conn()

    if cv:
        ch, v = cv
        row = fetch_exact(conn, ch, v)
        if not row:
            # fallback to FTS for this CV string
            fts_rows = search_fts(conn, f"{ch}:{v}", limit=5)
            if not fts_rows:
                return {"answer": NO_MATCH_MESSAGE, "citations": []}
            row = fts_rows[0]

        if _is_word_meaning_query(q):
            wm = row["word_meanings"] or ""
            answer = wm if wm else NO_MATCH_MESSAGE
            return {
                "mode": "word_meaning",
                "chapter": ch,
                "verse": v,
                "answer": answer,
                "citations": [f"[{ch}:{v}]"]
            }
        else:
            # explain: base on verse, neighbors, optional brief summary
            neighbors = fetch_neighbors(conn, ch, v, k=1)
            parts = []
            parts.append((ch, v, row["translation"] or ""))
            for n in neighbors:
                parts.append((int(n["chapter"]), int(n["verse"]), n["translation"] or ""))
            context_txt = "\n".join([f"{c}:{vv} {t}".strip() for c, vv, t in parts if t])
            prompt = (
                "Summarize the central teaching of this verse in 2-3 plain sentences, "
                "no formatting, and include the citation [C:V] somewhere in the text.\n\n" + context_txt
            )
            summary = _summarize(prompt)
            answer = summary if summary else (row["translation"] or NO_MATCH_MESSAGE)
            return {
                "mode": "explain",
                "chapter": ch,
                "verse": v,
                "answer": answer,
                "citations": [f"[{ch}:{v}]"]
            }

    # Broad query: combine FTS + embeddings
    fts_rows = search_fts(conn, q, limit=6)
    
    emb = None
    embeddings_used = False
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
        else:
            s = ""
        if s:
            ctx_lines.append(f"{ch}:{v} {s}")
    
    ctx = "\n".join(ctx_lines) if ctx_lines else ""
    prompt = (
        "Answer the question using only the provided context. Keep it concise, plain text, no markup. "
        "Weave in verse citations like [C:V] when relevant.\n\nQuestion: " + q + "\n\nContext:\n" + ctx
    )
    ans = _summarize(prompt) if ctx else ""
    
    return {
        "mode": "broad",
        "answer": ans if ans else NO_MATCH_MESSAGE,
        "citations": list(dict.fromkeys(cites))[:8],
        "embeddings_used": embeddings_used
    }


