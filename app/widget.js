// Gita Q&A v2 — Explain + Clickable Citations (No "Word Meaning" mode/pill)
// Version: v2.4-explain-cites
// - Removes the “Word Meaning …” pill/heading entirely.
// - Restores Word Meanings inside Explain answers (inline list; Sanskrit terms bold).
// - Renders citations as clickable pills whether they come from res.citations
//   (even if like "[2:16]") or appear in the answer text (2:16 / [2:16] / 2.16).
// - Keeps Explain layout: title, Sanskrit, Roman, Translation (italic), Summary inline.
// - Plain-text rendering only (strip HTML; <br> -> \n).
// - Send button: orange round, short/thick ↑; spinner replaces arrow while sending.

const GitaWidget = (() => {
  console.log('[GW] init v2.4-explain-cites');

  // -------- helpers --------
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

  // -------- text cleaning (no HTML/MD) --------
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

  // -------- word-meanings inline (bold keys) --------
  // Accepts strings like: "karmāṇi = in prescribed duties; eva = certainly; ..."
  function renderWordMeaningsInline(text) {
    const container = el('div', { class: 'wm-inline' });
    const clean = toPlain(text);
    const normalized = clean.replace(/\s*=\s*/g, ' — '); // canonical em-dash
    const parts = normalized.split(/;\s*/).map(s => s.trim()).filter(Boolean);
    if (!parts.length) { container.textContent = normalized; return container; }
    parts.forEach((seg, i) => {
      const m = /^(.*?)\s*—\s*(.+)$/.exec(seg);
      if (m) {
        const key = m[1].trim();
        const val = m[2].trim();
        const bold = el('span', { class: 'wm-key', style: { fontWeight: '800' } }, key);
        container.appendChild(bold);
        container.appendChild(el('span', {}, ' — ' + val));
      } else {
        container.appendChild(el('span', {}, seg));
      }
      if (i < parts.length - 1) container.appendChild(el('span', {}, '; '));
    });
    return container;
  }

  // -------- citations: normalize + extract --------
  const CITE_TEXT_RE = /(?:\[\s*)?(\d{1,2})\s*[:.]\s*(\d{1,3})(?:\s*\])?/g;

  function extractCitationsFromText(text) {
    const s = (text || '').toString();
    const out = [];
    let m;
    while ((m = CITE_TEXT_RE.exec(s))) {
      const ch = +m[1], v = +m[2];
      if (ch >= 1 && ch <= 18 && v >= 1 && v <= 200) out.push(`${ch}:${v}`);
    }
    return out;
  }

  function normalizeCitations(raw) {
    const out = [];
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
      if (m) out.push(`${+m[1]}:${+m[2]}`);
    });
    return Array.from(new Set(out));
  }

  function renderCitations(citations, onExplain) {
    if (!citations || !citations.length) return null;
    const wrap = el('div', { class: 'citations', style: { display: 'flex', gap: '6px', flexWrap: 'wrap', fontSize: '12px' } });
    citations.forEach(cv => {
      const m = /^(\d{1,2}):(\d{1,3})$/.exec(String(cv).trim());
      if (!m) return;
      const label = `${m[1]}:${m[2]}`;
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
      btn.addEventListener('click', () => { onExplain && onExplain(m[1], m[2]); });
      wrap.appendChild(btn);
    });
    return wrap;
  }

  // -------- mount --------
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
    host.appendChild(wrap);

    function autoScroll() { log.scrollTop = log.scrollHeight; }

    function pushMessage(role, content, extras = {}) {
      const msg = el('div', { class: 'msg ' + role });
      const bubble = el('div', { class: 'bubble' });

      // Normalize & extract citations for pills
      const citeSet = new Set(normalizeCitations(extras.citations));
      if (role === 'bot' && content && typeof content === 'object') {
        ['answer','summary','title','translation','word_meanings'].forEach(k => {
          if (content[k]) extractCitationsFromText(content[k]).forEach(cv => citeSet.add(cv));
        });
      } else if (role === 'bot' && typeof content === 'string') {
        extractCitationsFromText(content).forEach(cv => citeSet.add(cv));
      }

      // Render pills first (so they're easy to tap)
      const cites = Array.from(citeSet);
      if (cites.length) {
        const pills = renderCitations(cites, (ch, v) => doAsk(`Explain ${ch}.${v}`));
        if (pills) msg.appendChild(pills);
      }

      if (role === 'user') {
        bubble.textContent = content;
      } else {
        if (content && typeof content === 'object') {
          let any = false;

          // Title (suppress "Word meaning ..." headings that might come from backend)
          let rawTitle = toPlain(content.title || '');
          if (/^\s*word\s*meaning\b/i.test(rawTitle)) rawTitle = '';
          if (rawTitle) { any = true; bubble.appendChild(el('div', { class: 'sect title' }, rawTitle)); }

          if (content.sanskrit)   { any = true; bubble.appendChild(el('div', { class: 'sect' }, toPlain(content.sanskrit))); }
          if (content.roman)      { any = true; bubble.appendChild(el('div', { class: 'sect' }, toPlain(content.roman))); }
          if (content.translation){ any = true; bubble.appendChild(el('div', { class: 'sect transl' }, toPlain(content.translation))); }

          // **Word meanings within Explain** (no heading label; bold keys)
          if (content.word_meanings) {
            any = true;
            bubble.appendChild(renderWordMeaningsInline(content.word_meanings));
          }

          if (content.summary)    { any = true; bubble.appendChild(el('div', { class: 'sect' }, 'Summary: ' + toPlain(content.summary))); }

          const rest = content.answer;
          if (!any && rest) bubble.appendChild(el('div', {}, toPlain(rest)));
          if (!any && !rest) bubble.textContent = toPlain(JSON.stringify(content));
        } else {
          bubble.textContent = toPlain(content);
        }
      }

      msg.appendChild(bubble);

      // Debug payload
      if ((document.getElementById('gw2-debug') || {}).checked && extras.raw) {
        const d = el('details', { class: 'debug' }, el('summary', {}, 'Debug payload'));
        d.appendChild(el('pre', { style: { whiteSpace: 'pre-wrap' } }, JSON.stringify(extras.raw, null, 2)));
        if (extras.raw.fts_query) d.appendChild(el('div', {}, 'fts_query: ' + extras.raw.fts_query));
        msg.appendChild(d);
      }

      log.appendChild(msg);
      autoScroll();
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

    // Wire controls
    sendBtn.addEventListener('click', () => {
      const q = (input.value || '').trim();
      if (!q) return;
      input.value = '';
      doAsk(q);
      input.focus();
    });
    input.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') sendBtn.click(); });
    clearBtn.addEventListener('click', () => { log.innerHTML = ''; input.focus(); });

    // Init
    loadPills();
    return { ask: doAsk };
  }

  return { mount };
})();

if (typeof window !== 'undefined') window.GitaWidget = GitaWidget;
