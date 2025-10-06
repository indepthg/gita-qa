import os
import re
import sqlite3
import random
from fastapi import FastAPI, Request, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

DB_PATH = os.environ.get("DB_PATH", "gita.db")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
RAG_SOURCE = os.environ.get("RAG_SOURCE", "").lower()

client = OpenAI(api_key=OPENAI_KEY)

app = FastAPI(title="Gita Q&A v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app"), name="static")


def clean_text(t: str) -> str:
    if not t:
        return ""
    return re.sub(r"\s+", " ", str(t)).strip()


def fetch_row(ch: int, v: int):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM verses WHERE chapter=? AND verse=?", (ch, v))
    row = cur.fetchone()
    con.close()
    return row


def fts_search(q: str, limit: int = 12, fields=None):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    sql = "SELECT rowid,* FROM verses_fts WHERE verses_fts MATCH ? LIMIT ?"
    cur.execute(sql, (q, limit))
    rows = cur.fetchall()
    con.close()
    return rows


def diversify(rows, max_per_ch=2):
    """limit to 2 per chapter and suppress adjacent verses"""
    out, seen = [], {}
    for r in rows:
        ch, v = r["chapter"], r["verse"]
        if seen.get(ch, 0) >= max_per_ch:
            continue
        if out and out[-1]["chapter"] == ch and abs(out[-1]["verse"] - v) <= 1:
            continue
        out.append(r)
        seen[ch] = seen.get(ch, 0) + 1
    return out


def build_context(rows):
    parts = []
    for r in rows:
        ch, v = r["chapter"], r["verse"]
        txt = []
        if RAG_SOURCE == "commentary2":
            if r.get("commentary2"):
                txt.append(clean_text(r["commentary2"]))
        else:
            # original multi-field retrieval
            for f in ["commentary2", "commentary1", "translation", "colloquial", "roman"]:
                if r.get(f):
                    txt.append(clean_text(r[f]))
        if txt:
            parts.append(f"[{ch}:{v}] " + " ".join(txt))
    return "\n".join(parts)


def synthesize_answer(q, context):
    prompt = f"""
You are a Bhagavad Gita assistant. 
Answer the user’s question using ONLY the Context. 
Keep it natural, ~250–400 words. 
Prefer plain paragraphs. If topic has facets, use at most 4 sections with clear headers. 
Always cite verses inline like [2:47]. 
If the context has no info, reply briefly that nothing is available.

Question: {q}

Context:
{context}
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.5,
    )
    return resp.choices[0].message.content


@app.post("/ask")
async def ask(req: Request):
    data = await req.json()
    q = data.get("question", "").strip()

    # Try detect verse-specific queries
    m = re.match(r"(\d{1,2})[:.](\d{1,3})", q)
    if m:
        ch, v = int(m.group(1)), int(m.group(2))
        row = fetch_row(ch, v)
        if not row:
            return {"answer": f"Chapter {ch}, Verse {v} does not exist."}
        return {
            "answer": {
                "title": f"{ch}:{v}",
                "sanskrit": row.get("sanskrit"),
                "roman": row.get("roman"),
                "translation": row.get("translation"),
                "commentary1": row.get("commentary1"),
                "commentary2": row.get("commentary2"),
                "summary": row.get("summary"),
            }
        }

    # Broad query path
    rows = fts_search(q, limit=20)
    rows = diversify(rows, max_per_ch=2)
    ctx = build_context(rows)
    if not ctx:
        return {"answer": "No relevant context found."}

    answer = synthesize_answer(q, ctx)
    citations = [f"{r['chapter']}:{r['verse']}" for r in rows]
    return {"answer": answer, "citations": citations}


@app.get("/", response_class=HTMLResponse)
async def home():
    return """
<html>
<head><title>Gita Q&A</title></head>
<body>
<div id="gita"></div>
<script src="/static/widget.js?v=1"></script>
<script>
GitaWidget.mount({ root: '#gita', apiBase: '' });
</script>
</body>
</html>
"""
