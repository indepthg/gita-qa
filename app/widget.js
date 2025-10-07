// Gita Q&A v2 — v2.8 (Markdown rendering, no UI changes)
// - Renders model answers in Markdown (headings, lists, bold/italics, links).
// - Keeps existing citation pills and inline clickable citations.
// - Respects 'title' no-citations rule and suppresses redundant top citation pill.
// - Field-query support unchanged.

const GitaWidget = (() => {
  console.log('[GW] init v2.8');

  // ===== Field query addon (no UI changes) =====
  const FIELD_SYNONYMS = {
    sanskrit:        ["sanskrit"],
    roman:           ["transliteration","roman","english"], // "English" => roman
    colloquial:      ["colloquial","simple"],
    translation:     ["translation","meaning","rendering"],
    word_meanings:   ["word meaning","word meanings","word-by-word","word by word","padartha","padārtha"],
    commentary1:     ["shankara","śaṅkara","shankaracharya","commentary 1","commentary1"],
    commentary2:     ["commentary 2","commentary2","modern commentary"],
    all_commentaries:["commentary","all commentary","all commentaries","full commentary","both commentaries","complete commentary"]
  };

  function stripAccents(s){ try{ return s.normalize('NFD').replace(/[\u0300-\u036f]/g,''); }catch(_){ return s; } }

  function detectVerse(raw){
    const q = ' ' + stripAccents(String(raw).toLowerCase()) + ' ';
    let m = /(^|\D)(\d{1,2})\s*[:.\-\s]\s*(\d{1,3})(\D|$)/.exec(q);
    if (m) return { ch:+m[2], v:+m[3] };
    m = /chapter\s*(\d{1,2})\D+verse\s*(\d{1,3})/.exec(q);
    if (m) return { ch:+m[1], v:+m[2] };
    m = /\bch(?:apter)?\s*(\d{1,2})\D+v(?:erse)?\s*(\d{1,3})/.exec(q);
    if (m) return { ch:+m[1], v:+m[2] };
    return null;
  }
  function verseLooksPossible(ch,v){ return ch>=1 && ch<=18 && v>=1 && v<=200; }

  function buildSynonymIndex() {
    const idx = [];
    for (const key in FIELD_SYNONYMS) {
      (FIELD_SYNONYMS[key] || []).forEach(syn => {
        idx.push({ syn: stripAccents(String(syn).toLowerCase()), field: key });
      });
    }
    idx.sort((a,b)=> b.syn.length - a.syn.length);
    return idx;
  }
  const __SYNS = buildSynonymIndex();

  function detectFields(raw){
    let q = ' ' + stripAccents(String(raw).toLowerCase()) + ' ';
    q = q.replace(/\s*&\s*/g, ' and ');
    const picked = []; const seen = {};
    for (const {syn, field} of __SYNS){
      if (q.indexOf(' '+syn+' ') !== -1) {
        if (field === 'all_commentaries') {
          if (!seen.commentary1){ seen.commentary1=1; picked.push('commentary1'); }
          if (!seen.commentary2){ seen.commentary2=1; picked.push('commentary2'); }
        } else if (!seen[field]) {
          seen[field]=1; picked.push(field);
        }
      }
    }
    return picked;
  }

  // tolerant field picker for backend name variants
  function pickField(obj, key) {
    if (!obj) return '';
    const cap = key.charAt(0).toUpperCase()+key.slice(1);
    const list = [key, key.toLowerCase(), key.toUpperCase(), cap];
    if (key === 'roman') list.push('transliteration','Transliteration');
    if (key === 'commentary1') list.push('Commentary1','Shankara','śaṅkara','Śaṅkara');
    if (key === 'commentary2') list.push('Commentary2');
    for (const k of list) if (k in obj && String(obj[k]||'').trim()) return obj[k];
    return '';
  }
  // =============================================

  // ===== Markdown rendering (safe & tiny) =====
  function mdEscape(s){
    return String(s)
      .replace(/&/g,'&amp;')
      .replace(/</g,'&lt;')
      .replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;')
      .replace(/'/g,'&#39;');
  }
  function sanitizeUrl(url) {
    try {
      const u = new URL(url, window.location.href);
      const scheme = u.protocol.toLowerCase();
      if (scheme === 'http:' || scheme === 'https:') return u.href;
    } catch(e){}
    return '#';
  }
  function mdInline(s){
    // links [text](url)
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g, (_,txt,href) => {
      return `<a href="${sanitizeUrl(href)}" target="_blank" rel="noopener">${mdEscape(txt)}</a>`;
    });
    // code `code`
    s = s.replace(/`([^`]+)`/g, (_,code)=>`<code>${mdEscape(code)}</code>`);
    // bold **text**
    s = s.replace(/\*\*([^*]+)\*\*/g, (_,b)=>`<strong>${mdEscape(b)}</strong>`);
    // italics *text*
    s = s.replace(/(^|\W)\*([^*]+)\*(?=\W|$)/g, (_,pre,i)=>`${pre}<em>${mdEscape(i)}</em>`);
    return s;
  }
  function mdToHtml(md){
    const lines = String(md||'').replace(/\r\n?|\u2028|\u2029/g,'\n').split(/\n/);
    let out = [];
    let inUL = false, inOL = false;
    function closeLists(){ if(inUL){ out.push('</ul>'); inUL=false; } if(inOL){ out.push('</ol>'); inOL=false; } }
    for (let raw of lines){
      let l = raw.trimEnd();
      if (!l.trim()){
        closeLists();
        out.push('<p></p>');
        continue;
      }
      // headings ###, ##, #
      let hm = /^(#{1,3})\s+(.*)$/.exec(l);
      if (hm){
        closeLists();
        const level = hm[1].length;
        out.push(`<h${level}>${mdInline(hm[2])}</h${level}>`);
        continue;
      }
      // ordered list: 1. foo
      let om = /^\s*\d+\.\s+(.*)$/.exec(l);
      if (om){
        if (!inOL){ closeLists(); out.push('<ol>'); inOL=true; }
        out.push(`<li>${mdInline(om[1])}</li>`);
        continue;
      }
      // unordered list: -, *
      let um = /^\s*[-*]\s+(.*)$/.exec(l);
      if (um){
        if (!inUL){ closeLists(); out.push('<ul>'); inUL=true; }
        out.push(`<li>${mdInline(um[1])}</li>`);
        continue;
      }
      // blockquote
      let bq = /^>\s?(.*)$/.exec(l);
      if (bq){
        closeLists();
        out.push(`<blockquote>${mdInline(bq[1])}</blockquote>`);
        continue;
      }
      // paragraph
      closeLists();
      out.push(`<p>${mdInline(l)}</p>`);
    }
    closeLists();
    // collapse empty <p></p>
    return out.join('').replace(/(?:<p>\s*<\/p>)+/g, '');
  }
  function renderMarkdown(mdText){
    const div = document.createElement('div');
    div.className = 'md';
    // strip any literal [C:V] tokens (legacy)
    const cleaned = String(mdText||'').replace(/\[C:V\]/g,'');
    div.innerHTML = mdToHtml(cleaned);
    return div;
  }
  // ===========================================

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

  function toPlain(text) {
    if (text == null) return '';
    let t = String(text)
      .replace(/<\s*br\s*\/?.\s*>/gi, '\n')
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
      .gw2 .msg { display: block; white-space: normal; }
      .gw2 .msg .bubble { width: 100%; padding: 0; }
      .gw2 .msg.user .bubble { background: var(--c-bg); border: 1px solid var(--c-border); padding: 10px 12px; border-radius: 8px; white-space: pre-wrap; }
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
      .gw2 .md h1,.gw2 .md h2,.gw2 .md h3{ margin: .6em 0 .3em; line-height:1.25; }
      .gw2 .md p{ margin: .5em 0; }
      .gw2 .md ul,.gw2 .md ol{ margin: .5em 1.25em; }
      .gw2 .md code{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .95em; padding: .1em .25em; border:1px solid var(--c-border); border-radius:4px; }
      .gw2 .md a{ color: var(--c-fg); text-decoration: underline; }
      blockquote{ border-left: 3px solid var(--c-border); padding-left: .75em; color: var(--c-muted); margin: .6em 0; }
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

      // build citation set
      let citeSet = new Set(normalizeCitations(extras.citations));
      if (role === 'bot' && content && typeof content === 'object') {
        ['answer','summary','title','translation','word_meanings','commentary1','commentary2'].forEach(k => {
          if (content[k]) extractCitationsFromText(content[k]).forEach(cv => citeSet.add(cv));
        });
      } else if (role === 'bot' && typeof content === 'string') {
        extractCitationsFromText(content).forEach(cv => citeSet.add(cv));
      }

      // suppress a specific citation (to avoid the redundant top pill)
      let cites = [...citeSet];
      if (extras.suppressCv) cites = cites.filter(cv => cv !== extras.suppressCv);

      if (cites.length) {
        const pills = renderCitations(cites, (ch, v) => doAsk(`Explain ${ch}.${v}`));
        if (pills) msg.appendChild(pills);
      }

      if (role === 'user') {
        bubble.textContent = content;
      } else {
        if (content && typeof content === 'object') {
          let any = false;

          // Title (mark as nocites so we don't inline-link "2:47" here)
          let rawTitle = toPlain(content.title || '');
          if (/^\s*word\s*meaning\b/i.test(rawTitle)) rawTitle = '';
          if (rawTitle) {
            any = true;
            const t = el('div', { class: 'sect title', 'data-nocites': '1' }, rawTitle);
            bubble.appendChild(t);
          }

          if (content.sanskrit)    { any = true; bubble.appendChild(el('div', { class: 'sect' }, toPlain(content.sanskrit))); }
          if (content.roman)       { any = true; bubble.appendChild(el('div', { class: 'sect' }, toPlain(content.roman))); }
          if (content.translation) { any = true; bubble.appendChild(el('div', { class: 'sect transl' }, toPlain(content.translation))); }

          if (content.word_meanings) {
            any = true;
            bubble.appendChild(renderWordMeaningsInline(content.word_meanings));
          }

          // Commentary sections (when present) — use Markdown renderer to allow formatting
          if (content.commentary2) {
            any = true;
            const h = el('div', { class: 'sect' }, 'Commentary:');
            bubble.appendChild(h);
            const md = renderMarkdown(content.commentary2);
            md.classList.add('sect');
            bubble.appendChild(md);
          }
          if (content.commentary1) {
            any = true;
            const h = el('div', { class: 'sect' }, 'Śaṅkara (Commentary 1):');
            bubble.appendChild(h);
            const md = renderMarkdown(content.commentary1);
            md.classList.add('sect');
            bubble.appendChild(md);
          }

          if (content.summary) {
            any = true;
            const cleanedSummary = String(content.summary).replace(/\[C:V\]/g,'');
            const md = renderMarkdown('**Summary:** ' + cleanedSummary);
            md.classList.add('sect');
            bubble.appendChild(md);
          }

          const rest = content.answer;
          if (!any && rest) {
            const md = renderMarkdown(rest);
            md.classList.add('sect');
            bubble.appendChild(md);
          }
          if (!any && !rest) bubble.textContent = toPlain(JSON.stringify(content));
        } else {
          // string answer -> render as Markdown
          const md = renderMarkdown(String(content||''));
          md.classList.add('sect');
          bubble.appendChild(md);
        }
      }

      // Inline citations—but skip inside the title block
      enhanceInlineCitations(bubble, (ch, v) => doAsk(`Explain ${ch}.${v}`));

      msg.appendChild(bubble);

      if ((document.getElementById('gw2-debug') || {}).checked && extras.raw) {
        const d = el('details', { class: 'debug' }, el('summary', {}, 'Debug payload'));
        d.appendChild(el('pre', { style: { whiteSpace: 'pre-wrap' } }, JSON.stringify(extras.raw, null, 2)));
        if (extras.raw.fts_query) d.appendChild(el('div', {}, 'fts_query: ' + extras.raw.fts_query));
        msg.appendChild(d);
      }

      log.appendChild(msg);
      autoScroll();
    }

    function enhanceInlineCitations(bubble, onExplain) {
      const RE = CITE_TEXT_RE;
      const walker = document.createTreeWalker(bubble, NodeFilter.SHOW_TEXT, null);
      const targets = [];
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        // skip inside title block
        if (n.parentElement && n.parentElement.closest('.sect.title')) continue;
        targets.push(n);
      }
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
        const after = text.slice(last);
        if (after) frag.appendChild(document.createTextNode(after));
        node.parentNode.replaceChild(frag, node);
      });
    }

    async function loadPills() {
      try {
        const s = await fetchJSON(`${apiBase}/suggest`);
        (s.suggestions || []).forEach(text => {
          if (/^\s*word\s*meaning\b/i.test(text)) return;
          const b = el('button', { class: 'pill' }, text);
          b.addEventListener('click', () => doAsk(text));
          pillbar.appendChild(b);
        });
      } catch {}
    }

    async function doAsk(q) {
      // ---- Field-query intercept ----
      try {
        const cv = detectVerse(q);
        const fields = detectFields(q);
        if (cv && !verseLooksPossible(cv.ch, cv.v)) {
          pushMessage('user', q);
          pushMessage('bot', `Chapter ${cv.ch}, Verse ${cv.v} does not exist.`);
          return;
        }
        if (cv && fields.length) {
          pushMessage('user', q);
          try {
            sendBtn.classList.add('loading');
            const res = await fetchJSON(`${apiBase}/ask`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ question: `Explain ${cv.ch}.${cv.v}`, topic: 'gita' })
            });
            const obj = (res && (res.answer ?? res)) || {};
            const out = { title: String(obj.title||'').trim() };

            const want = []; const seen = {};
            for (const f of fields) { if (!seen[f]) { seen[f]=1; want.push(f); } }

            for (const key of want) {
              const val = pickField(obj, key);
              if (!val) continue;
              if (key === 'commentary1') out.commentary1 = val;
              else if (key === 'commentary2') out.commentary2 = val;
              else out[key] = val;
            }

            const citations = Array.isArray(res.citations) ? res.citations : [];
            const suppressCv = `${cv.ch}:${cv.v}`;
            pushMessage('bot', out, { citations, raw: res, asked: q, suppressCv });
          } catch (e) {
            pushMessage('bot', 'Error: ' + (e.message || e));
          } finally {
            sendBtn.classList.remove('loading');
          }
          return;
        }
      } catch (e) {
        console.error('[field-intercept] error', e);
      }
      // ---- Default flow ----
      pushMessage('user', q);
      try {
        sendBtn.classList.add('loading');
        const res = await fetchJSON(`${apiBase}/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q, topic: 'gita' })
        });
        const citations = Array.isArray(res.citations) ? res.citations : [];
        // suppress the top pill if the main result is an Explain for a single verse
        let suppressCv = '';
        const a = (res && (res.answer ?? res)) || {};
        if (a && Number.isFinite(+a.chapter) && Number.isFinite(+a.verse)) {
          suppressCv = `${+a.chapter}:${+a.verse}`;
        }
        pushMessage('bot', res.answer ?? res, { citations, raw: res, asked: q, suppressCv });

        if (Array.isArray(res.suggestions) && res.suggestions.length) {
          const bar = document.createElement('div');
          bar.className = 'pillbar';
          res.suggestions.forEach(txt => {
            const b = document.createElement('button');
            b.className = 'pill';
            b.textContent = txt;
            b.addEventListener('click', () => doAsk(txt));
            bar.appendChild(b);
          });
          // append just below the last bot message
          const msgs = document.querySelectorAll('.gw2 .msg.bot');
          if (msgs.length) msgs[msgs.length-1].appendChild(bar);
        }

      } catch (e) {
        pushMessage('bot', 'Error: ' + (e.message || e));
      } finally {
        sendBtn.classList.remove('loading');
      }
    }

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
