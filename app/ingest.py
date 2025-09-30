
import io
import math
import os
import re
from typing import Dict, Iterable, List, Tuple

import pandas as pd
from pypdf import PdfReader
from docx import Document

from .db import bulk_upsert
from . import embed_store

RE_CV = re.compile(r"\b([1-9]|1[0-8])[:\. ](\d{1,2})\b")  # 1-18 : 1-99

REQUIRED_COLS = [
    "rownum","audio_id","chapter","verse","sanskrit","roman","colloquial",
    "translation","capsule_url","word_meanings","title"
]


def _coerce_int(x):
    try:
        return int(str(x).strip())
    except Exception:
        return None


def load_sheet_to_rows(file_bytes: bytes, filename: str) -> List[Dict]:
    name = filename.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes))
    elif name.endswith(".xlsx"):
        df = pd.read_excel(io.BytesIO(file_bytes))
    else:
        raise ValueError("Unsupported sheet format. Use CSV or XLSX.")

    cols = {c.strip().lower(): c for c in df.columns}
    for rc in REQUIRED_COLS:
        if rc not in cols:
            raise ValueError(f"Missing required column: {rc}")

    out: List[Dict] = []
    for _, r in df.iterrows():
        chap = _coerce_int(r[cols["chapter"]])
        ver = _coerce_int(r[cols["verse"]])
        if chap is None or ver is None:
            continue  # skip malformed
        out.append({
            "rownum": _coerce_int(r[cols["rownum"]]),
            "audio_id": str(r.get(cols["audio_id"], "") or ""),
            "chapter": chap,
            "verse": ver,
            "sanskrit": str(r.get(cols["sanskrit"], "") or ""),
            "roman": str(r.get(cols["roman"], "") or ""),
            "colloquial": str(r.get(cols["colloquial"], "") or ""),
            "translation": str(r.get(cols["translation"], "") or ""),
            "capsule_url": str(r.get(cols["capsule_url"], "") or ""),
            "word_meanings": str(r.get(cols["word_meanings"], "") or ""),
            "title": str(r.get(cols["title"], "") or ""),
        })
    return out


def _chunk_text(txt: str, size: int = 1000, overlap: int = 120) -> List[str]:
    txt = txt.replace("\r", "\n")
    parts: List[str] = []
    i = 0
    while i < len(txt):
        j = min(len(txt), i + size)
        parts.append(txt[i:j])
        i = j - overlap
        if i < 0:
            i = 0
    return parts


def _infer_cv(text: str) -> Tuple[int, int]:
    m = RE_CV.search(text)
    if not m:
        return (0, 0)
    chap = int(m.group(1))
    ver = int(m.group(2))
    return (chap, ver)


def pdf_to_chunks(file_bytes: bytes) -> List[Tuple[str, Dict]]:
    reader = PdfReader(io.BytesIO(file_bytes))
    chunks: List[Tuple[str, Dict]] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for chunk in _chunk_text(text):
            ch, v = _infer_cv(chunk)
            chunks.append((chunk, {"page": i, "chapter": ch, "verse": v}))
    return chunks


def docx_to_chunks(file_bytes: bytes) -> List[Tuple[str, Dict]]:
    doc = Document(io.BytesIO(file_bytes))
    text = "\n".join([p.text for p in doc.paragraphs])
    chunks: List[Tuple[str, Dict]] = []
    for chunk in _chunk_text(text):
        ch, v = _infer_cv(chunk)
        chunks.append((chunk, {"page": None, "chapter": ch, "verse": v}))
    return chunks


def ingest_commentary(file_bytes: bytes, filename: str, topic: str, commentator: str, source: str) -> int:
    name = filename.lower()
    if name.endswith(".pdf"):
        kv = pdf_to_chunks(file_bytes)
    elif name.endswith(".docx"):
        kv = docx_to_chunks(file_bytes)
    else:
        raise ValueError("Unsupported commentary format. Use PDF or DOCX.")

    docs = [k for k, _ in kv]
    metas = []
    for _, meta in kv:
        m = {**meta, "topic": topic, "commentator": commentator, "source": source}
        metas.append(m)

    return embed_store.add_chunks(docs, metas)
