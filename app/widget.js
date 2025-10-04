// Gita Q&A v2 — bundled widget with dynamic follow-ups
// Version: v2.7 (dynamic pills, self-citation hide, "More detail", closure-safe cites)
// - Plain-text only rendering (no HTML/Markdown).
// - Clickable citations (top + inline inside paragraphs) -> Explain C.V.
// - Hides self-citation pill for Explain C.V.
// - Word meanings inline with bold Sanskrit keys (no "Word Meaning" label).
// - Follow-up chips under each bot answer:
//    * "More detail" (uses your requested wording)
//    * 2–3 dynamic, model-generated follow-up questions (secondary /ask)
// - Orange round send button; spinner while sending.
// Use with a dynamic cache-busting loader in your HTML (already added in main.py).

console.log('[GW] widget v2.7 loaded', new Date().toISOString());

const GitaWidget = (() => {
  // ---------- small helpers ----------
  function el(tag, attrs = {}, ...children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'style' && typeof v === 'object') Object.assign(e.style, v);
      else if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2), v);
      else if (k === 'class') e.className = v;
      else e.setAttribute(k, v);
    }
    for (const c of children.flat()) {
      if (c == null) continue;
      e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return e;
  }

  function prefersDark() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  async function fetchJSON(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }

  // ---------- plain text ----------
  function toPlain(text) {
    if (text == null) return '';
    let t = String(text)
      .replace(/<\s*br\s*\/?\s*>/gi, '\n')
      .replace(/<[^>]+>/g, '')
      .replace(/\r\n?|\u2028|\u2029/g, '\n');
    t = t.replace(/&nbsp;/g, ' ')
         .replace(/&amp;/g, '&')
         .replace(/&lt;/g, '<')
         .replace(/&gt;/g, '>')
         .replace(/&quot;/g, '"')
         .replace(/&#39;/g, "'")
         .replace(/[ \t]+\n/g, '\n')
         .replace(/\n{3,}/g, '\n\n')
         .trim();
    return t;
  }

  // ---------- word meanings inline (bold keys) ----------
  function renderWordMeaningsInline(text) {
    const container = document.createElement('div');
    container.className = 'wm-inline';
    const clean = toPlain(text);
    const normalized = clean.replace(/\s*=\s*/g, ' — ');
    const parts = normalized.split(/;\s*/).map(s => s.trim()).filter(Boolean);
    if (!parts.length) { container.textContent = normalized; return container; }
    parts.forEach((seg, i) => {
      const m = /^(.*?)\s*—\s*(.+)$/.exec(seg);
      if (m) {
        const key = m[1].trim();
        const val = m[2].trim();
        const keyEl = document.createElement('span');
        keyEl.className = 'wm-key';
        keyEl.style.fontWeight = '800';
        keyEl.textContent = key;
        container.appendChild(keyEl);
        const valEl = document.createElement('span');
        valEl.textContent = ' — ' + val;
        container.appendChild(valEl);
      } else {
        const span = document.createElement('span');
        span.textContent = seg;
        container.appendChild(span);
      }
      if (i < parts.length - 1) {
        const sep = document.createElement('span');
        sep.textContent = '; ';
        container.appendChild(sep);
      }
    });
    return container;
  }

  // ---------- citations utilities ----------
  const CITE_TEXT_RE = /(?:\[\s*)?(?:C\s*:\s*)?(\d{1,2})\s*[:.]\s*(\d{1,3})(?:\s*\])?/g;

  function extractCitationsFromText(text) {
    const s = (text || '').toString();
    const out = new Set();
    let m;
    while ((m = CITE_TEXT_RE.exec(s))) {
      const ch = +m[1], v = +m[2];
      if (ch >= 1 && ch <= 18 && v >= 1 && v <= 200) out.add(`${ch}:${v}`);
    }
    return [...out];
  }

  function normalizeCitations(raw) {
    const out = new Set();
    (raw || []).forEach((c) => {
      let s = c;
      if (Array.isArray(c)) {
        if (c.length === 2 && Number.isFinite(+c[0]) && Number.isFinite(+c[1])) {
          s = `${c[0]}:${c[1]}`;
        } else {
          s = c.join(':');
        }
      } else if (typeof c === 'object' && c) {
        const ch = c.chapter ?? c.ch ?? c.c ?? c[0];
        const v  = c.verse   ?? c.v ?? c[1];
        if (ch && v) s = `${ch}:${v}`;
      }
      s = String(s).replace(/[^\d:.-]/g, '');
      const m = /(\d{1,2})[:.](\d{1,3})/.exec(s);
      if (m) out.add(`${+m[1]}:${+m[2]}`);
    });
    return [...out];
  }

  function renderCitations(citations, onExplain) {
    if (!citations || !citations.length) return null;
    const wrap = el('div', { class: 'citations', style: { display: 'flex', gap: '6px', flexWrap: 'wrap', fontSize: '12px' } });
    citations.forEach(cv => {
      const m = /^(\d{1,2}):(\d{1,3})$/.exec(String(cv).trim());
      if (!m) return;
      const ch = +m[1], v = +m[2];
      const label = `${ch}:${v}`;
      const btn = el('button', {
        class: 'citation-pill',
        title: `Explain ${label}`,
        style: {
          borderRadius: '999px',
          padding: '2px 8px',
          border: '1px solid var(--c-border)',
          cursor: 'pointer',
          background: 'var(--c-pill-bg)',
          color: 'var(--c-pill-fg)'
        }
      }, label);
      btn.addEventListener('click', () => { onExplain && onExplain(ch, v); });
      wrap.appendChild(btn);
    });
    return wrap;
  }

  // ---------- follow-up bar ----------
  function addFollowupBar(container, items) {
    if (!items || !items.length) return;
    const bar = document.createElement('div');
    bar.className = 'pillbar';
    items.forEach(({label, onClick}) => {
      const b = document.createElement('button');
      b.className = 'pill';
      b.textContent = label;
      b.addEventListener('click', onClick);
      bar.appendChild(b);
    });
    container.appendChild(bar);
  }

  async function generateDynamicPillsFromAnswer(apiBase, lastAnswerText) {
    const meta = [
      "Based on the answer below, propose 2–3 short follow-up questions that let the user go deeper into under-covered commentary and important cross-references.",
      "Each 30–55 characters, plain text, no quotes or markdown, no internal field names.",
      "Avoid repeating the last question. Prefer distinct angles (analysis, practice, cross-refs).",
      "Return one per line, nothing else.",
      "", "Answer:", lastAnswerText
    ].join("\n");

    try {
      const res = await fetchJSON(`${apiBase}/ask`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: meta, topic: 'gita' })
      });
      const raw = (res && (res.answer || res)) || '';
      const lines = String(raw).split(/\r?\n/).map(s => s.trim()).filter(Boolean);
      const uniq = [...new Set(lines)].filter(s => s.length >= 18 && s.length <= 70);
      return uniq.slice(0, 3).map(text => ({ label: text, onClick: () => doAsk(text) }));
    } catch {
      return [];
    }
  }

  // ---------- mount ----------
  function mount({ root, apiBase }) {
    const host = typeof root === 'string' ? document.querySelector(root) : root;
    if (!host) throw new Error('Root element not found');

    const dark = prefersDark();
    const vars = {
      '--c-bg': dark ? '#0f1115' : '#ffffff',
      '--c-panel': dark ? '#141820' : '#f9fafb',
      '--c-border': dark ? '#2a2f3a' : '#e5e7eb',
      '--c-fg': dark ? '#e5e7eb' : '#111827',
      '--c-muted': dark ? '#a3aab8' : '#6b7280',
      '--c-pill-bg': dark ? '#1f2530' : '#f3f4f6',
      '--c-pill-fg': dark ? '#e5e7eb' : '#1f2937',
      '--c-accent': '#ff8d1a',
      '--c-accent-border': '#e07a00'
    };

    const style = el('style', {}, `
      .gw2 * { box-sizing: border-box; }
      .gw2 { background: var(--c-bg); color: var(--c-fg); border: 1px solid var(--c-border); border-radius: 10px; padding: 12px; }
      .gw2 .log { display: flex; flex-direction: column; gap: 12px; min-height: 38vh; max-height: 65vh; overflow: auto; padding: 8px; background: var(--c-panel); border: 1px solid var(--c-border); border-radius: 8px; }
      .gw2 .msg { display: block; white-space: pre-wrap; }
      .gw2 .msg .bubble { width: 100%; padding: 0; }
      .gw2 .msg.user .bubble { background: var(--c-bg); border: 1px solid var(--c-border); padding: 10px 12px; border-radius: 8px; }
      .gw2 .row { display: flex; gap: 8px; align-items: center; margin-top: 10px; }
      .gw2 input[type="text"] { flex: 1; padding: 14px; border: 1px solid var(--c-border); border-radius: 10px; background: transparent; color: var(--c-fg); font-size: 18px; }
      .gw2 .clear { padding: 10px 12px; border: 1px solid var(--c-border); background: transparent; border-radius: 8px; cursor: pointer; color: var(--c-fg); }
      .gw2 .send { width: 42px; height: 42px; border-radius: 999px; border: 2px solid var(--c-accent-border); background: var(--c-accent); color: #fff; cursor: pointer; display: grid; place-items: center; line-height: 1; position: relative; }
      .gw2 .send .arrow { font-size: 22px; font-weight: 900; transform: scaleX(1.3) scaleY(0.5); }
      .gw2 .send:hover { transform: translateY(-1px); }
      .gw2 .send:active { transform: translateY(0); }
      .gw2 .send.loading .arrow { visibility: hidden; }
      .gw2 .send.loading::after {
        content: ""; width: 16px; height: 16px; border-radius: 50%;
        border: 2px solid rgba(255,255,255,0.6); border-top-color: rgba(255,255,255,1);
        position: absolute; inset: 0; margin: auto; animation: gw2spin 0.9s linear infinite;
      }
      @keyframes gw2spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      .gw2 .pillbar { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
      .gw2 details.debug { margin-top: 6px; font-size: 12px; color: var(--c-muted); }
      .gw2 .citations { margin: 6px 0 6px; }
      .gw2 .sect { margin-top: 14px; }
      .gw2 .sect.title { font-weight: 800; }
      .gw2 .sect.transl { font-style: italic; }
      .gw2 .wm-inline { margin-top: 12px; }
      .gw2 .wm-key { font-weight: 800; }
    `);

    const wrap = el('div', { class: 'gw2' });
    Object.entries(vars).forEach(([k, v]) => wrap.style.setProperty(k, v));
    wrap.appendChild(style);

    const log = el('div', { class: 'log', role: 'log', 'aria-live': 'polite' });
    const input = el('input', { type: 'text', placeholder: 'Ask about the Gita… (e.g., Explain 2.47 or nasato)', autocomplete: 'off' });
    const clearBtn = el('button', { class: 'clear', title: 'Clear conversation' }, 'Clear');
    const sendBtn = el('button', { class: 'send', title: 'Send' }, el('span', { class: 'arrow' }, '↑'));

    const row = el('div', { class: 'row' }, input, clearBtn, sendBtn);
    const pillbar = el('div', { class: 'pillbar' });
    const debugToggle = el('label', { style: { display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px', fontSize: '12px', color: 'var(--c-muted)' } },
      el('input', { type: 'checkbox', id: 'gw2-debug' }), 'Debug');

    wrap.appendChild(log);
    wrap.appendChild(row);
    wrap.appendChild(pillbar);
    wrap.appendChild(debugToggle);

    host.innerHTML = '';
    host.appendChild(wrap);

    function autoScroll() { log.scrollTop = log.scrollHeight; }

    function pushMessage(role, content, extras = {}) {
      const msg = el('div', { class: 'msg ' + role });
      const bubble = el('div', { class: 'bubble' });

      // Build citation set
      const citeSet = new Set(normalizeCitations(extras.citations));
      if (role === 'bot' && content && typeof content === 'object') {
        ['answer','summary','title','translation','word_meanings'].forEach(k => {
          if (content[k]) extractCitationsFromText(content[k]).forEach(cv => citeSet.add(cv));
        });
      } else if (role === 'bot' && typeof content === 'string') {
        extractCitationsFromText(content).forEach(cv => citeSet.add(cv));
      }

      // If this was "Explain C.V", drop self-citation
      let askedCV = null;
      if (extras && typeof extras.asked === 'string') {
        const m = /^\s*explain\s+(\d{1,2})[.:](\d{1,3})/i.exec(extras.asked);
        if (m) askedCV = `${+m[1]}:${+m[2]}`;
      }

      let cites = [...new Set([...citeSet])];
      if (askedCV) cites = cites.filter(cv => cv !== askedCV);

      if (cites.length) {
        const pills = renderCitations(cites, (ch, v) => doAsk(`Explain ${ch}.${v}`));
        if (pills) msg.appendChild(pills);
      }

      if (role === 'user') {
        bubble.textContent = content;
      } else {
        if (content && typeof content === 'object') {
          let any = false;

          // Title (suppress any "Word meaning ..." headings)
          let rawTitle = toPlain(content.title || '');
          if (/^\s*word\s*meaning\b/i.test(rawTitle)) rawTitle = '';
          if (rawTitle) { any = true; bubble.appendChild(el('div', { class: 'sect title' }, rawTitle)); }

          if (content.sanskrit)    { any = true; bubble.appendChild(el('div', { class: 'sect' }, toPlain(content.sanskrit))); }
          if (content.roman)       { any = true; bubble.appendChild(el('div', { class: 'sect' }, toPlain(content.roman))); }
          if (content.translation) { any = true; bubble.appendChild(el('div', { class: 'sect transl' }, toPlain(content.translation))); }

          // Word meanings (inline, bold keys)
          if (content.word_meanings) {
            any = true;
            bubble.appendChild(renderWordMeaningsInline(content.word_meanings));
          }

          if (content.summary)     { any = true; bubble.appendChild(el('div', { class: 'sect' }, 'Summary: ' + toPlain(content.summary))); }

          const rest = content.answer;
          if (!any && rest) bubble.appendChild(el('div', {}, toPlain(rest)));
          if (!any && !rest) bubble.textContent = toPlain(JSON.stringify(content));
        } else {
          bubble.textContent = toPlain(content);
        }
      }

      // Enhance inline refs inside bubble into clickable micro-pills
      enhanceInlineCitations(bubble, (ch, v) => doAsk(`Explain ${ch}.${v}`));

      msg.appendChild(bubble);

      // Debug payload
      if ((document.getElementById('gw2-debug') || {}).checked && extras.raw) {
        const d = el('details', { class: 'debug' }, el('summary', {}, 'Debug payload'));
        d.appendChild(el('pre', { style: { whiteSpace: 'pre-wrap' } }, JSON.stringify(extras.raw, null, 2)));
        if (extras.raw.fts_query) d.appendChild(el('div', {}, 'fts_query: ' + extras.raw.fts_query));
        msg.appendChild(d);
      }

      // FOLLOW-UP CHIPS (More detail + dynamic)
      if (role === 'bot') {
        // Compose a plain-text version of just-displayed content
        let lastAnswerText = '';
        if (typeof content === 'string') {
          lastAnswerText = toPlain(content);
        } else if (content && typeof content === 'object') {
          const bits = [];
          if (content.title) bits.push(toPlain(content.title));
          if (content.sanskrit) bits.push(toPlain(content.sanskrit));
          if (content.roman) bits.push(toPlain(content.roman));
          if (content.translation) bits.push(toPlain(content.translation));
          if (content.summary) bits.push('Summary: ' + toPlain(content.summary));
          if (content.answer) bits.push(toPlain(content.answer));
          if (content.word_meanings) bits.push(toPlain(content.word_meanings));
          lastAnswerText = bits.join('\n').trim();
        }

        // Default "More detail" pill
        const moreDetail = (() => {
          const q = (extras && extras.asked) || '';
          const m = /^\s*explain\s+(\d{1,2})[.:](\d{1,3})/i.exec(q);
          const label = 'More detail';
          if (m) {
            const cv = `${+m[1]}.${+m[2]}`;
            return { label, onClick: () => doAsk(`Explain ${cv} — more detail. Include additional commentary and context.`) };
          }
          if (q) return { label, onClick: () => doAsk(`${q} — more detail. Include additional commentary and context.`) };
          return null;
        })();

        (async () => {
          const pills = [];
          if (moreDetail) pills.push(moreDetail);
          const dyn = await generateDynamicPillsFromAnswer(apiBase, lastAnswerText);
          const seen = new Set(pills.map(p => p.label));
          dyn.forEach(p => { if (!seen.has(p.label)) pills.push(p); });
          addFollowupBar(msg, pills.slice(0, 3)); // cap to 3 total
        })();
      }

      log.appendChild(msg);
      autoScroll();
    }

    // turn inline 2:63 / [2:63] / C:2:63 into clickable micro-pills
    function enhanceInlineCitations(bubble, onExplain) {
      const RE = CITE_TEXT_RE;
      const walker = document.createTreeWalker(bubble, NodeFilter.SHOW_TEXT, null);
      const targets = [];
      for (let n = walker.nextNode(); n; n = walker.nextNode()) targets.push(n);
      targets.forEach(node => {
        const text = node.nodeValue;
        if (!RE.test(text)) return;
        RE.lastIndex = 0;
        const frag = document.createDocumentFragment();
        let last = 0, m;
        while ((m = RE.exec(text))) {
          const before = text.slice(last, m.index);
          if (before) frag.appendChild(document.createTextNode(before));
          const ch = +m[1], v = +m[2];
          const cv = `${ch}:${v}`;
          const btn = el('button', { class: 'citation-pill inline', title: `Explain ${cv}`, style: {
            display:'inline-block', margin:'0 .25em', padding:'0 .5em',
            borderRadius:'999px', border:'1px solid var(--c-border)',
            background:'var(--c-pill-bg)', color:'var(--c-pill-fg)', cursor:'pointer',
            fontSize:'0.9em', lineHeight:'1.6'
          }}, cv);
          btn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); onExplain && onExplain(ch, v); }, true);
          frag.appendChild(btn);
          last = RE.lastIndex;
        }
        const after = text.slice[last);
        if (after) frag.appendChild(document.createTextNode(after));
        node.parentNode.replaceChild(frag, node);
      });
    }

    async function loadPills() {
      try {
        const s = await fetchJSON(`${apiBase}/suggest`);
        (s.suggestions || []).forEach(text => {
          // Drop any "Word meaning ..." suggestion pill
          if (/^\s*word\s*meaning\b/i.test(text)) return;
          const b = document.createElement('button');
          b.className = 'pill';
          b.textContent = text;
          b.addEventListener('click', () => doAsk(text));
          pillbar.appendChild(b);
        });
      } catch {}
    }

    async function doAsk(q) {
      pushMessage('user', q);
      try {
        sendBtn.classList.add('loading');
        const res = await fetchJSON(`${apiBase}/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q, topic: 'gita' })
        });
        const citations = Array.isArray(res.citations) ? res.citations : [];
        pushMessage('bot', res.answer ?? res, { citations, raw: res, asked: q });
      } catch (e) {
        pushMessage('bot', 'Error: ' + (e.message || e));
      } finally {
        sendBtn.classList.remove('loading');
      }
    }

    // wire controls
    sendBtn.addEventListener('click', () => {
      const q = (input.value || '').trim();
      if (!q) return;
      input.value = '';
      doAsk(q);
      input.focus();
    });
    input.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') sendBtn.click(); });
    clearBtn.addEventListener('click', () => { log.innerHTML = ''; input.focus(); });

    loadPills();
    return { ask: doAsk };
  }

  return { mount };
})();

if (typeof window !== 'undefined') window.GitaWidget = GitaWidget;
