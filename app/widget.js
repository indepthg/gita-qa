// Gita Q&A v2 — HOTFIX build
// - Robust Word Meaning detection: formats BOTH `word_meanings` field and plain `answer` strings that look like word-meaning lists.
// - Title for WM: prefer pretty title from /title/{ch}/{v}; suppress numeric-only like "2:47".
// - Friendly error for invalid refs (e.g., 2.84).
// - Arrow: short, thick ↑; spinner replaces arrow on send.

const GitaWidget = (() => {
  function el(tag, attrs = {}, ...children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'style' && typeof v === 'object') Object.assign(e.style, v);
      else if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2), v);
      else if (k === 'class') e.className = v;
      else if (k === 'html') e.innerHTML = v;
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

  function renderCitations(citations, onExplain) {
    if (!citations || !citations.length) return null;
    const wrap = el('div', { class: 'citations', style: { display: 'flex', gap: '6px', flexWrap: 'wrap', fontSize: '12px' } });
    citations.forEach(tag0 => {
      const s = String(tag0).trim().replace(/^\[|\]$/g, '');
      const m = /^(\d{1,2})[:.-](\d{1,3})$/.exec(s);
      if (!m) return;
      const btn = el('button', {
        class: 'citation-pill',
        title: 'Explain this verse',
        style: {
          borderRadius: '999px', padding: '2px 8px', border: '1px solid var(--c-border)',
          cursor: 'pointer', background: 'var(--c-pill-bg)', color: 'var(--c-pill-fg)'
        }
      }, `${m[1]}:${m[2]}`);
      btn.addEventListener('click', () => { onExplain && onExplain(m[1], m[2]); });
      wrap.appendChild(btn);
    });
    return wrap;
  }

  function looksLikeWordMeanings(s) {
    if (!s) return false;
    const t = toPlain(s);
    return (/=/.test(t) && /;/.test(t)) || (t.match(/—/g) || []).length >= 2;
  }

  function renderWordMeaningsInline(text) {
    const container = el('div', { class: 'wm-inline' });
    const clean = toPlain(text);
    const normalized = clean.replace(/\s*=\s*/g, ' — ');
    const parts = normalized.split(/;\s*/).map(s => s.trim()).filter(Boolean);
    if (!parts.length) { container.textContent = normalized; return container; }
    parts.forEach((seg, i) => {
      const m = /^(.*?)\s*—\s*(.+)$/.exec(seg);
      if (m) {
        container.appendChild(el('span', { class: 'wm-key' }, m[1].trim()));
        container.appendChild(el('span', {}, ' — ', m[2].trim()));
      } else {
        container.appendChild(el('span', {}, seg));
      }
      if (i < parts.length - 1) container.appendChild(el('span', {}, '; '));
    });
    return container;
  }

  function detectMode(q) {
    const s = (q || '').trim().toLowerCase();
    if (/^(word\s*meaning|meaning)\b/.test(s)) return 'wm';
    if (/\bexplain\b/.test(s)) return 'explain';
    return '';
  }

  async function fetchPrettyTitle(q, apiBase) {
    const m = /\b(?:word\s*meaning|meaning)\s+(\d{1,2})[.:](\d{1,3})/i.exec(q || '');
    if (!m) return '';
    try {
      const j = await fetchJSON(`${apiBase}/title/${m[1]}/${m[2]}`);
      return toPlain(j?.title || j?.result || j?.answer || '');
    } catch { return ''; }
  }

  const GITA_VERSE_COUNTS = [0,47,72,43,42,29,47,30,28,34,42,55,20,35,27,20,24,28,78];
  function extractRef(q) {
    const m = /(\d{1,2})[.:](\d{1,3})/.exec(q || '');
    return m ? { ch: +m[1], v: +m[2] } : null;
  }
  function validateRef(q) {
    const ref = extractRef(q); if (!ref) return { ok:true };
    const { ch, v } = ref;
    if (ch < 1 || ch > 18) return { ok:false, ch, v, max:0 };
    const max = GITA_VERSE_COUNTS[ch];
    return { ok: v >= 1 && v <= max, ch, v, max };
  }

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
      .gw2 .pill { padding: 6px 10px; border-radius: 999px; border: 1px solid var(--c-border); background: var(--c-pill-bg); color: var(--c-pill-fg); cursor: pointer; }
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
    const input = el('input', { type: 'text', placeholder: 'Ask about the Gita… (e.g., 2.47 meaning)', autocomplete: 'off' });
    const clearBtn = el('button', { class: 'clear', title: 'Clear conversation' }, 'Clear');
    const sendBtn = el('button', { class: 'send', title: 'Send' }, el('span', { class: 'arrow' }, '↑'));
    const row = el('div', { class: 'row' }, input, clearBtn, sendBtn);
    const pillbar = el('div', { class: 'pillbar' });
    const debugToggle = el('label', { style: { display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px', fontSize: '12px', color: 'var(--c-muted)' } },
      el('input', { type: 'checkbox', id: 'gw2-debug' }), 'Debug');

    wrap.appendChild(log); wrap.appendChild(row); wrap.appendChild(pillbar); wrap.appendChild(debugToggle);
    host.appendChild(wrap);

    function autoScroll() { log.scrollTop = log.scrollHeight; }

    function pushMessage(role, content, extras = {}) {
      const msg = el('div', { class: 'msg ' + role });
      const bubble = el('div', { class: 'bubble' });
      const asked = extras.asked || '';
      const mode = extras.mode || detectMode(asked);
      const isExplainMode = mode === 'explain' || (extras?.raw?.mode === 'explain');

      if (role === 'bot' && !isExplainMode && extras.citations && extras.citations.length) {
        const c = renderCitations(extras.citations, (ch, v) => doAsk(`Explain ${ch}.${v}`));
        if (c) msg.appendChild(c);
      }

      if (role === 'user') {
        bubble.textContent = content;
      } else {
        if (content && typeof content === 'object') {
          let any = false;

          if (mode === 'wm') {
            const pretty = extras.prettyTitle || '';
            const rawTitle = toPlain(content.title || '');
            const looksLikeRef = /^\s*\d{1,2}[.:]\d{1,3}\s*$/.test(rawTitle);
            const title = pretty || (looksLikeRef ? '' : rawTitle);
            if (title) { any = true; bubble.appendChild(el('div', { class: 'sect title' }, title)); }
            if (content.sanskrit) { any = true; bubble.appendChild(el('div', { class: 'sect' }, toPlain(content.sanskrit))); }
            if (content.roman)    { any = true; bubble.appendChild(el('div', { class: 'sect' }, toPlain(content.roman))); }
            if (content.word_meanings) { any = true; bubble.appendChild(renderWordMeaningsInline(content.word_meanings)); }
            else if (content.answer && looksLikeWordMeanings(content.answer)) { any = true; bubble.appendChild(renderWordMeaningsInline(content.answer)); }
          } else {
            const rawTitle = toPlain(content.title || '');
            if (rawTitle) { any = true; bubble.appendChild(el('div', { class: 'sect title' }, rawTitle)); }
            if (content.sanskrit) { any = true; bubble.appendChild(el('div', { class: 'sect' }, toPlain(content.sanskrit))); }
            if (content.roman)    { any = true; bubble.appendChild(el('div', { class: 'sect' }, toPlain(content.roman))); }
            if (content.translation) { any = true; bubble.appendChild(el('div', { class: 'sect transl' }, toPlain(content.translation))); }
            if (content.word_meanings) { any = true; bubble.appendChild(renderWordMeaningsInline(content.word_meanings)); }
            else if (content.answer && looksLikeWordMeanings(content.answer)) { any = true; bubble.appendChild(renderWordMeaningsInline(content.answer)); }
            if (content.summary) { any = true; bubble.appendChild(el('div', { class: 'sect' }, 'Summary: ' + toPlain(content.summary))); }
            const rest = content.answer;
            if (!any && rest) bubble.appendChild(el('div', {}, toPlain(rest)));
            if (!any && !rest) bubble.textContent = toPlain(JSON.stringify(content));
          }
        } else {
          const s = String(content || '');
          if (looksLikeWordMeanings(s)) bubble.appendChild(renderWordMeaningsInline(s));
          else bubble.textContent = toPlain(s);
        }
      }

      msg.appendChild(bubble);
      if (extras.citations && extras.citations.length && isExplainMode) {
        const c = renderCitations(extras.citations, (ch, v) => doAsk(`Explain ${ch}.${v}`));
        if (c) msg.appendChild(c);
      }
      if ((document.getElementById('gw2-debug') || {}).checked && extras.raw) {
        const d = el('details', { class: 'debug' }, el('summary', {}, 'Debug payload'));
        d.appendChild(el('pre', { style: { whiteSpace: 'pre-wrap' } }, JSON.stringify(extras.raw, null, 2)));
        if (extras.raw.fts_query) d.appendChild(el('div', {}, 'fts_query: ' + extras.raw.fts_query));
        msg.appendChild(d);
      }
      log.appendChild(msg); autoScroll();
    }

    async function loadPills() {
      try {
        const s = await fetchJSON(`${apiBase}/suggest`);
        (s.suggestions || []).forEach(text => {
          const b = el('button', { class: 'pill' }, text);
          b.addEventListener('click', () => doAsk(text));
          pillbar.appendChild(b);
        });
      } catch {}
    }

    async function doAsk(q) {
      pushMessage('user', q);
      const validity = validateRef(q);
      if (!validity.ok) {
        const msg = `Chapter ${validity.ch}, Verse ${validity.v} does not exist (max is ${validity.max}).`;
        pushMessage('bot', msg, { asked: q });
        return;
      }

      const mode = detectMode(q);
      let prettyTitle = '';
      if (mode === 'wm') prettyTitle = await fetchPrettyTitle(q, apiBase);

      try {
        sendBtn.classList.add('loading');
        const res = await fetchJSON(`${apiBase}/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q, topic: 'gita' })
        });
        const citations = Array.isArray(res.citations) ? res.citations : [];
        pushMessage('bot', res.answer ?? res, { citations, raw: res, asked: q, mode, prettyTitle });
      } catch (e) {
        pushMessage('bot', 'Error: ' + (e.message || e));
      } finally {
        sendBtn.classList.remove('loading');
      }
    }

    sendBtn.addEventListener('click', () => {
      const q = (input.value || '').trim();
      if (!q) return;
      input.value=''; doAsk(q); input.focus();
    });
    input.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') sendBtn.click(); });
    clearBtn.addEventListener('click', () => { log.innerHTML = ''; input.focus(); });

    loadPills();
    return { ask: doAsk };
  }

  return { mount };
})();

if (typeof window !== 'undefined') window.GitaWidget = GitaWidget;
