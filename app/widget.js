// Gita Q&A v2 – widget (focused update per request)
// Changes in this build:
// 1) Word Meaning: bold the left “key” for items in the pattern “key = meaning; …” (semicolon-separated)
// 2) Chat area sizing: viewport-based min/max height so it isn’t squished on first load (desktop + phone)
// 3) Move Clear next to the arrow (order: input | Clear | Send), make arrow less thick, smaller circle
// 4) Circle doubles as a spinner while a request is in-flight

const GitaWidget = (() => {
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

  // Plain text cleaning
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

  // Clean citation pills like 2:47 and call Explain on click
  function renderCitations(apiBase, citations, onExplain) {
    if (!citations || !citations.length) return null;
    const wrap = el('div', { class: 'citations', style: { display: 'flex', gap: '6px', flexWrap: 'wrap', fontSize: '12px' } });
    citations.forEach(tag0 => {
      const s = String(tag0).trim()
        .replace(/^\[+|\]+$/g, '')
        .replace(/^\[+/, '')
        .replace(/\]+$/, '');
      const m = /^(\d{1,2})[:.-](\d{1,3})$/.exec(s);
      if (!m) return;
      const label = `${m[1]}:${m[2]}`;
      const btn = el('button', {
        class: 'citation-pill',
        title: 'Explain this verse',
        style: {
          borderRadius: '999px', padding: '2px 8px', border: '1px solid var(--c-border)', cursor: 'pointer',
          background: 'var(--c-pill-bg)', color: 'var(--c-pill-fg)'
        }
      }, label);
      btn.addEventListener('click', () => { if (typeof onExplain==='function') onExplain(m[1], m[2]); });
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
      /* Chat area sizing: min/max by viewport so first load isn't squished */
      .gw2 .log { display: flex; flex-direction: column; gap: 12px; min-height: 38vh; max-height: 65vh; overflow: auto; padding: 8px; background: var(--c-panel); border: 1px solid var(--c-border); border-radius: 8px; }
      .gw2 .msg { display: block; white-space: pre-wrap; }
      .gw2 .msg .bubble { width: 100%; padding: 0; }
      .gw2 .msg.user .bubble { background: var(--c-bg); border: 1px solid var(--c-border); padding: 10px 12px; border-radius: 8px; }
      .gw2 .row { display: flex; gap: 8px; align-items: center; margin-top: 10px; }
      .gw2 input[type="text"] { flex: 1; padding: 12px; border: 1px solid var(--c-border); border-radius: 8px; background: transparent; color: var(--c-fg); font-size: 16px; }
      .gw2 .clear { padding: 10px 12px; border: 1px solid var(--c-border); background: transparent; border-radius: 8px; cursor: pointer; color: var(--c-fg); }
      /* Smaller, less-thick circle; arrow turns spinner on loading */
      .gw2 .send { width: 36px; height: 36px; border-radius: 999px; border: 2px solid var(--c-accent-border); background: var(--c-accent); color: #fff; cursor: pointer; display: grid; place-items: center; font-size: 18px; font-weight: 600; line-height: 1; }
      .gw2 .send:active { transform: translateY(1px); }
      .gw2 .send.loading { animation: gw2spin 0.9s linear infinite; }
      @keyframes gw2spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      .gw2 .pillbar { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
      .gw2 .pill { padding: 6px 10px; border-radius: 999px; border: 1px solid var(--c-border); background: var(--c-pill-bg); color: var(--c-pill-fg); cursor: pointer; }
      .gw2 details.debug { margin-top: 6px; font-size: 12px; color: var(--c-muted); }
      .gw2 .citations { margin: 6px 0 6px; }
      .gw2 .sect { margin-top: 12px; }
      .gw2 .wm-line { margin-top: 6px; }
      .gw2 .wm-key { font-weight: 700; }
    `);

    const wrap = el('div', { class: 'gw2' });
    Object.entries(vars).forEach(([k, v]) => wrap.style.setProperty(k, v));
    wrap.appendChild(style);

    const log = el('div', { class: 'log', role: 'log', 'aria-live': 'polite' });
    const input = el('input', { type: 'text', placeholder: 'Ask about the Gita… (e.g., 2.47 meaning)', autocomplete: 'off' });
    const clearBtn = el('button', { class: 'clear', title: 'Clear conversation' }, 'Clear');
    const sendBtn = el('button', { class: 'send', title: 'Send' }, '↑'); // straighter, lighter arrow

    // Order: input | Clear | Send
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

    // Word meanings: parse "key = value; key2 = value2; ..." and bold the key
    function renderWordMeanings(text) {
      const container = el('div', { class: 'sect word-mean' });
      const clean = toPlain(text);

      const items = clean.split(/;\s*/).map(s => s.trim()).filter(Boolean);
      if (!items.length) { container.textContent = clean; return container; }

      items.forEach(item => {
        const m = /^(.*?)\s*=\s*(.+)$/.exec(item);
        if (!m) {
          container.appendChild(el('div', { class: 'wm-line' }, item));
          return;
        }
        let key = m[1].trim();
        const val = m[2].trim();

        const pm = /(.*?)(\()(.*?)(\))(.*)?/.exec(key);
        let keyNode;
        if (pm && pm[3]) {
          keyNode = el('span', {},
            pm[1] || '',
            el('span', {}, '('),
            el('span', { class: 'wm-key' }, pm[3]),
            el('span', {}, ')'),
            pm[5] || ''
          );
        } else {
          keyNode = el('span', { class: 'wm-key' }, key);
        }

        container.appendChild(el('div', { class: 'wm-line' },
          keyNode,
          el('span', {}, ' — '),
          el('span', { class: 'wm-val' }, val)
        ));
      });

      return container;
    }

    async function doAsk(q) {
      pushMessage('user', q);
      try {
        sendBtn.classList.add('loading');
        const payload = { question: q, topic: 'gita' };
        const res = await fetchJSON(`${apiBase}/ask`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const citations = Array.isArray(res.citations) ? res.citations : [];
        pushMessage('bot', res.answer ?? res, { citations, raw: res, asked: q });
      } catch (e) {
        pushMessage('bot', 'Error: ' + (e.message || e));
      } finally {
        sendBtn.classList.remove('loading');
      }
    }

    function pushMessage(role, content, extras = {}) {
      const msg = el('div', { class: 'msg ' + role });
      const bubble = el('div', { class: 'bubble' });

      const isExplain = !!(extras && extras.raw && (extras.raw.mode === 'explain' || /\bexplain\b/i.test(extras.raw.question || extras.asked || '')));

      if (role === 'bot' && !isExplain && extras.citations && extras.citations.length) {
        const c = renderCitations(apiBase, extras.citations, (ch, v) => doAsk(`Explain ${ch}.${v}`));
        if (c) msg.appendChild(c);
      }

      if (role === 'user') {
        bubble.textContent = content;
      } else {
        if (content && typeof content === 'object') {
          const fieldsOrder = ['title','sanskrit','roman','colloquial','translation','word_meanings','summary','answer'];
          let any = false;
          for (const k of fieldsOrder) {
            if (!content[k]) continue;
            any = true;
            const val = toPlain(content[k]);
            if (k === 'word_meanings') {
              bubble.appendChild(renderWordMeanings(val));
            } else {
              bubble.appendChild(el('div', { class: 'sect' }, val));
            }
          }
          if (!any) bubble.textContent = toPlain(JSON.stringify(content));
        } else {
          bubble.textContent = toPlain(content);
        }
      }

      msg.appendChild(bubble);

      if ((document.getElementById('gw2-debug') || {}).checked && extras.raw) {
        const d = el('details', { class: 'debug' }, el('summary', {}, 'Debug payload'));
        const pre = el('pre', { style: { whiteSpace: 'pre-wrap' } }, JSON.stringify(extras.raw, null, 2));
        d.appendChild(pre);
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
      } catch (e) { /* ignore */ }
    }

    // Controls
    sendBtn.addEventListener('click', () => {
      const q = (input.value || '').trim();
      if (!q) return; input.value = ''; doAsk(q); input.focus();
    });
    input.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') sendBtn.click(); });
    clearBtn.addEventListener('click', () => { log.innerHTML = ''; input.focus(); });

    loadPills();
    return { ask: doAsk };
  }

  return { mount };
})();

if (typeof window !== 'undefined') window.GitaWidget = GitaWidget;
