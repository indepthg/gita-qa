# app/generate_canonicals.py
import re

def _parse_whitelist(whitelist: str):
    # returns list[(ch, v)], unique, ordered
    if not whitelist:
        return []
    txt = (whitelist or "").strip()
    txt = txt.replace("–", "-").replace("—", "-")  # normalize dashes
    toks = re.split(r"[,\s]+", txt)
    out = []
    for tok in toks:
        if not tok: continue
        m = re.match(r"^(\d{1,2})[:.](\d{1,3})(?:-(\d{1,3}))?$", tok)
        if not m: continue
        ch = int(m.group(1)); v1 = int(m.group(2)); v2 = int(m.group(3)) if m.group(3) else v1
        if v1 > v2: v1, v2 = v2, v1
        for v in range(v1, v2+1):
            if 1 <= ch <= 18 and 1 <= v <= 200:
                out.append((ch, v))
    seen = set(); uniq=[]
    for cv in out:
        if cv in seen: continue
        seen.add(cv); uniq.append(cv)
    return uniq

def _clean(s: str) -> str:
    if not s: return ""
    s = re.sub(r"<\s*br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _compose_context(cv_list, master_lookup):
    # One compact line per verse, joining available fields.
    lines = []
    for ch, v in cv_list:
        row = master_lookup.get((ch, v), {})
        trans = _clean(row.get("translation") or "")
        c2 = _clean(row.get("commentary2") or "")
        c3 = _clean(row.get("commentary3") or "")
        bits = []
        if trans: bits.append(f"Translation: {trans}")
        if c2:    bits.append(f"Commentary2: {c2}")
        if c3:    bits.append(f"Commentary3: {c3}")
        if bits:
            lines.append(f"[{ch}:{v}] " + " | ".join(bits))
    return "\n".join(lines)

def _normalize_verse_mentions(text: str) -> str:
    if not text: return ""
    text = re.sub(r"Chapter\s+(\d{1,2})\s*(?:,|)\s*Verse\s+(\d{1,3})", r"[\1:\2]", text, flags=re.I)
    text = re.sub(r"\b(\d{1,2})\s*[.:]\s*(\d{1,3})\b", r"[\1:\2]", text)
    return text.strip()

def _ask_model(client, model, system, user, max_tokens, temperature=0.2):
    try:
        rsp = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (rsp.choices[0].message.content or "").strip()
    except Exception:
        return ""

def _gen_summary_and_detail(client, model, question, ctx, style_hint, required_points):
    base_system = (
        "You are a Bhagavad Gita assistant. Use ONLY the provided context. "
        "Write clean plain text (Markdown ok), with [chapter:verse] chips. No external sources."
    )
    guide = (
        f"Question: {question}\n\n"
        f"Style hint (optional): {style_hint or '—'}\n"
        f"Required points (optional): {required_points or '—'}\n\n"
        "Context lines (each begins with [C:V]):\n"
        f"{ctx}\n\n"
        "Produce two sections:\n"
        "<<<SUMMARY>>>  • 100–150 words. Natural layout: 1 paragraph OR 2 short paragraphs OR 1 paragraph + ≤4 bullets.\n"
        "<<<DETAIL>>>   • 700–900 words. Clear sections, short paragraphs, tasteful bullets or sub-headings. "
        "Weave in [C:V] chips where appropriate. Avoid repetition; keep it flowing.\n"
    )

    text = _ask_model(client, model, base_system, guide, max_tokens=1800)
    summ, detail = "", ""

    if "<<<SUMMARY>>>" in text and "<<<DETAIL>>>" in text:
        parts = re.split(r"<<<(SUMMARY|DETAIL)>>>", text)
        buf = {"SUMMARY":"", "DETAIL":""}
        it = iter(parts)
        _ = next(it, "")
        for tag, content in zip(it, it):
            buf[tag] = content.strip()
        summ = buf["SUMMARY"].strip()
        detail = buf["DETAIL"].strip()
    else:
        # fallback: first ~150 words as summary, rest as detail
        words = text.split()
        summ = " ".join(words[:150])
        detail = " ".join(words[150:])

    summ = _normalize_verse_mentions(summ)
    detail = _normalize_verse_mentions(detail)

    # If DETAIL too short, try once more with stronger expand cue
    if len(detail.split()) < 550:
        expand_guide = guide + "\nYour previous detail was too short. Expand to 700–900 words with clearer sections and examples.\n"
        text2 = _ask_model(client, model, base_system, expand_guide, max_tokens=2200, temperature=0.25)
        if "<<<DETAIL>>>" in text2:
            parts = re.split(r"<<<(SUMMARY|DETAIL)>>>", text2)
            it = iter(parts); _ = next(it, "")
            buf = {"SUMMARY":"", "DETAIL":""}
            for tag, content in zip(it, it):
                buf[tag] = content.strip()
            if buf["DETAIL"]:
                detail = _normalize_verse_mentions(buf["DETAIL"])

    # Ensure MIN floors
    if len(summ.split()) < 90:
        summ += "\n\n" + " ".join(detail.split()[:40])

    return summ.strip(), detail.strip()

# Public API used by main.py
def generate_answer_tiers(question, verse_whitelist, master_lookup, style_hint, required_points, client=None, model=None):
    from openai import OpenAI
    client = client or OpenAI()
    model = model or "gpt-4o-mini"

    cvs = _parse_whitelist(verse_whitelist)
    ctx = _compose_context(cvs, master_lookup)
    if not ctx:
        # no context? degrade gracefully (still try to produce both sections)
        s, d = _gen_summary_and_detail(client, model, question, "", style_hint, required_points)
        return s, s, d  # (short/medium unused, long)
    s, d = _gen_summary_and_detail(client, model, question, ctx, style_hint, required_points)
    return s, s, d
