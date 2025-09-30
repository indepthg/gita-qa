
# Gita Q&A v2 — Hybrid (SQLite FTS5 + Chroma)

Plain responses (no HTML formatting), minimal logic, Railway-ready.

## Environment

Set these on Railway:

- `OPENAI_API_KEY=...`
- `DATA_DIR=/data`
- `DB_PATH=/data/gita.db`
- `CHROMA_DIR=/data/chroma`
- `COLLECTION_NAME=gita_commentary_v1`
- `TOPIC_DEFAULT=gita`
- `ALLOW_ORIGINS=*`           # or a comma-separated list
- `GEN_MODEL=gpt-4o-mini`
- `EMBED_MODEL=text-embedding-3-small`
- `NO_MATCH_MESSAGE=I couldn't find enough in the corpus to answer that. Try a specific verse like 12:12, or rephrase your question.`

## Railway

- **Build command**: `pip install -r requirements.txt`
- **Start command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Persistent Volume**: add one mounted at `/data`

## Ingest

### CSV → SQLite
```
curl -X POST "$APP/ingest_sheet_sql" \
-F "file=@gita_verses_clean.csv"
```

Required columns (case-insensitive):
`rownum,audio_id,chapter,verse,sanskrit,roman,colloquial,translation,capsule_url,word_meanings,title`

### PDF/DOCX Commentary → Chroma
```
curl -X POST "$APP/ingest_commentary" \
-F "file=@commentary.pdf" \
-F "topic=gita" \
-F "commentator=Swami X" \
-F "source=Publisher or URL"
```

## Ask

```
# Direct verse
curl -s "$APP/ask" -H 'Content-Type: application/json' \
-d '{"question":"Explain 2:47","topic":"gita"}' | jq .

# Word meaning
curl -s "$APP/ask" -H 'Content-Type: application/json' \
-d '{"question":"Word meaning 2:47","topic":"gita"}' | jq .

# Broad
curl -s "$APP/ask" -H 'Content-Type: application/json' \
-d '{"question":"Which verses talk about devotion?","topic":"gita"}' | jq .
```

## Debug

```
curl "$APP/debug/verse/2/47"
curl "$APP/debug/stats"
```

## UI widget

Load `app/widget.js` in your page and mount it:
```html
<div id="gita"></div>
<script src="/path/to/widget.js"></script>
<script>
  GitaWidget.mount({ root: '#gita', apiBase: 'https://YOUR-APP.up.railway.app' });
</script>
```

## Notes

- Responses are plain text. No bold/italics/newlines injected by the API—just the data and short LLM summaries.
- FTS5 indexes `title, translation, word_meanings, roman`.
- Commentary chunks try to auto-tag `[chapter:verse]` if found; otherwise they still contribute semantically.
- To prune or rebuild: delete `/data/gita.db` or `/data/chroma` on Railway and re-ingest.
