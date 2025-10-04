/* Gita Q&A v2 — field-select widget (natural language, AND support)
   Version: fields-v1
   - Natural-language detection of Chapter/Verse and field(s) (supports "and")
   - Mapping block at top for easy edits (synonyms → canonical fields)
   - "Commentary" (generic) dumps both Commentary1 (Śaṅkara) + Commentary2
   - If no fields specified → falls back to normal ask behavior (Explain or term search)
   - Plain-text only; clickable [C:V] citations; bold keys for word meanings
   - Friendly error for invalid verse like 2.84
   Usage: <script src="/static/widget.js?v=Date.now()"></script>
          GitaWidget.mount({ root: '#gita', apiBase: '' });
*/

console.log('[GW] widget fields-v1 loaded', new Date().toISOString());

var GitaWidget = (function () {
  // ---- EDITABLE FIELD MAPPINGS (synonyms → canonical DB fields) ----
  // You can freely add/remove synonyms here.
  var FIELD_SYNONYMS = {
    sanskrit:        ["sanskrit"],
    roman:           ["transliteration", "roman", "english"], // per your choice: "English" means roman
    colloquial:      ["colloquial", "simple"],                 // remove/rename if you don't like "colloquial"
    translation:     ["translation", "meaning", "rendering"],
    word_meanings:   ["word meaning", "word meanings", "word-by-word", "word by word", "padartha"],
    commentary1:     ["shankara", "śaṅkara", "shankaracharya", "commentary 1", "commentary1"],
    commentary2:     ["commentary 2", "commentary2", "modern commentary"],
    all_commentaries:["commentary", "all commentary", "all commentaries"] // expands to commentary1+commentary2
  };

  // Labels for display (left side headings when multiple fields are requested)
  var FIELD_LABEL = {
    sanskrit: "Sanskrit",
    roman: "Transliteration",
    colloquial: "Colloquial",
    translation: "Translation",
    word_meanings: "Word Meaning",
    commentary1: "Śaṅkara (Commentary 1)",
    commentary2: "Commentary 2"
  };

  // ---- tiny helpers ----
  function el(tag, attrs) {
    var e = document.createElement(tag);
    if (attrs && typeof attrs === 'object') {
      for (var k in attrs) {
        var v = attrs[k];
        if (k === 'style' && v && typeof v === 'object') {
          for (var sk in v) { try { e.style[sk] = v[sk]; } catch(_){} }
        } else if (k.slice(0,2) === 'on' && typeof v === 'function') {
          e.addEventListener(k.slice(2), v);
        } else if (k === 'class') {
          e.className = v;
        } else {
          e.setAttribute(k, v);
        }
      }
    }
    for (var i=2;i<arguments.length;i++) {
      var c = arguments[i];
      if (c == null) continue;
      if (Object.prototype.toString.call(c) === '[object Array]') {
        for (var j=0;j<c.length;j++) {
          var ci = c[j];
          if (ci == null) continue;
          e.appendChild(typeof ci === 'string' ? document.createTextNode(ci) : ci);
        }
      } else {
        e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
      }
    }
    return e;
  }

  function prefersDark() {
    try { return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches); }
    catch(_) { return false; }
  }

  function fetchJSON(url, opts) {
    return fetch(url, opts).then(function (r) {
      if (!r.ok) return r.text().then(function(t){ throw new Error(t || ('HTTP ' + r.status)); });
      return r.json();
    });
  }

  function toPlain(text) {
    if (text == null) return '';
    var t = String(text)
      .replace(/<\s*br\s*\/?\s*>/gi, '
')
      .replace(/<[^>]+>/g, '')
      .replace(/
?| | /g, '
');
    t = t.replace(/&nbsp;/g, ' ')
         .replace(/&amp;/g, '&')
         .replace(/&lt;/g, '<')
         .replace(/&gt;/g, '>')
         .replace(/&quot;/g, '"')
         .replace(/&#39;/g, "'")
         .replace(/[ 	]+
/g, '
')
         .replace(/
{3,}/g, '

')
         .trim();
    return t;
  }

  // word meanings inline (bold keys)
  function renderWordMeaningsInline(text) {
    var container = document.createElement('div');
    container.className = 'wm-inline';
    var clean = toPlain(text);
    var normalized = clean.replace(/\s*=\s*/g, ' — ');
    var parts = normalized.split(/;\s*/);
    var out = [];
    for (var i=0;i<parts.length;i++) {
      var s = (parts[i] || '').trim();
      if (!s) continue;
      out.push(s);
    }
    if (!out.length) { container.textContent = normalized; return container; }
    for (var k=0;k<out.length;k++) {
      var seg = out[k];
      var m = /^(.*?)\s*—\s*(.+)$/.exec(seg);
      if (m) {
        var key = m[1].trim();
        var val = m[2].trim();
        var keyEl = document.createElement('span');
        keyEl.className = 'wm-key';
        keyEl.style.fontWeight = '800';
        keyEl.textContent = key;
        container.appendChild(keyEl);
        var valEl = document.createElement('span');
        valEl.textContent = ' — ' + val;
        container.appendChild(valEl);
      } else {
        var span = document.createElement('span');
        span.textContent = seg;
        container.appendChild(span);
      }
      if (k < out.length - 1) {
        var sep = document.createElement('span');
        sep.textContent = '; ';
        container.appendChild(sep);
      }
    }
    return container;
  }

  // citations
  var CITE_TEXT_RE = /(?:\[\s*)?(?:C\s*:\s*)?(\d{1,2})\s*[:.]\s*(\d{1,3})(?:\s*\])?/g;

  function extractCitationsFromText(text) {
    var s = (text || '').toString();
    var out = {}; var list = [];
    var m;
    while ((m = CITE_TEXT_RE.exec(s))) {
      var ch = +m[1], v = +m[2];
      if (ch>=1 && ch<=18 && v>=1 && v<=200) {
        var key = ch + ':' + v;
        if (!out[key]) { out[key]=1; list.push(key); }
      }
    }
    return list;
  }

  function normalizeCitations(raw) {
    var out = {}; var list = [];
    (raw || []).forEach(function (c) {
      var s = c;
      if (Object.prototype.toString.call(c) === '[object Array]') {
        if (c.length === 2 && Number.isFinite(+c[0]) && Number.isFinite(+c[1])) s = c[0] + ':' + c[1];
        else s = c.join(':');
      } else if (c && typeof c === 'object') {
        var ch = c.chapter || c.ch || c.c || c[0];
        var v  = c.verse   || c.v  || c[1];
        if (ch && v) s = ch + ':' + v;
      }
      s = String(s).replace(/[^\d:.-]/g, '');
      var m = /(\d{1,2})[:.](\d{1,3})/.exec(s);
      if (m) {
        var key = (+m[1]) + ':' + (+m[2]);
        if (!out[key]) { out[key]=1; list.push(key); }
      }
    });
    return list;
  }

  function renderCitations(citations, onExplain) {
    if (!citations || !citations.length) return null;
    var wrap = el('div', { class: 'citations', style: { display: 'flex', gap: '6px', flexWrap: 'wrap', fontSize: '12px' } });
    citations.forEach(function (cv) {
      var m = /^(\d{1,2}):(\d{1,3})$/.exec(String(cv).trim());
      if (!m) return;
      var ch = +m[1], v = +m[2];
      var label = ch + ':' + v;
      var btn = el('button', {
        class: 'citation-pill',
        title: 'Explain ' + label,
        style: {
          borderRadius: '999px',
          padding: '2px 8px',
          border: '1px solid var(--c-border)',
          cursor: 'pointer',
          background: 'var(--c-pill-bg)',
          color: 'var(--c-pill-fg)'
        }
      }, label);
      btn.addEventListener('click', function () { if (onExplain) onExplain(ch, v); });
      wrap.appendChild(btn);
    });
    return wrap;
  }

  // ---- NL parsing ----
  function stripAccents(s) {
    try { return s.normalize('NFD').replace(/[̀-ͯ]/g, ''); }
    catch(_) { return s; }
  }

  function detectVerse(raw) {
    var q = ' ' + stripAccents(String(raw).toLowerCase()) + ' ';
    // 1) generic 2.10 / 2:10 / 2-10 / 2 10
    var m = /(^|\D)(\d{1,2})\s*[:.\-\s]\s*(\d{1,3})(\D|$)/.exec(q);
    if (m) return {ch:+m[2], v:+m[3]};
    // 2) chapter X verse Y
    m = /chapter\s*(\d{1,2})\D+verse\s*(\d{1,3})/.exec(q);
    if (m) return {ch:+m[1], v:+m[2]};
    // 3) ch X v Y
    m = /ch(?:apter)?\s*(\d{1,2})\D+v(?:erse)?\s*(\d{1,3})/.exec(q);
    if (m) return {ch:+m[1], v:+m[2]};
    return null;
  }

  function buildSynonymIndex() {
    var idx = [];
    for (var key in FIELD_SYNONYMS) {
      var arr = FIELD_SYNONYMS[key] || [];
      for (var i=0;i<arr.length;i++) {
        var syn = stripAccents(String(arr[i]).toLowerCase());
        idx.push({ syn: syn, field: key });
      }
    }
    // sort longer synonyms first to avoid partial matches ("word meaning" before "word")
    idx.sort(function (a,b) { return b.syn.length - a.syn.length; });
    return idx;
  }
  var SYNS = buildSynonymIndex();

  function detectFields(raw) {
    var q = ' ' + stripAccents(String(raw).toLowerCase()) + ' ';
    // Normalize " and " / "&"
    q = q.replace(/\s*&\s*/g, ' and ');
    var picked = []; var seen = {};
    for (var i=0;i<SYNS.length;i++) {
      var syn = ' ' + SYNS[i].syn + ' ';
      if (q.indexOf(syn) !== -1) {
        var f = SYNS[i].field;
        if (f === 'all_commentaries') {
          if (!seen['commentary1']) { seen['commentary1']=1; picked.push('commentary1'); }
          if (!seen['commentary2']) { seen['commentary2']=1; picked.push('commentary2'); }
        } else if (!seen[f]) {
          seen[f] = 1; picked.push(f);
        }
      }
    }
    return picked;
  }

  // ---- UI mounting (kept minimal; styles similar to your earlier working look) ----
  function mount(opts) {
    opts = opts || {};
    var root = opts.root;
    var apiBase = (typeof opts.apiBase === 'string') ? opts.apiBase : '';
    var host = (typeof root === 'string') ? document.querySelector(root) : root;
    if (!host) throw new Error('Root element not found');

    var dark = prefersDark();
    var vars = {
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

    var style = el('style', {}, [
      '.gw2 *{box-sizing:border-box;}',
      '.gw2{background:var(--c-bg);color:var(--c-fg);border:1px solid var(--c-border);border-radius:10px;padding:12px;}',
      '.gw2 .log{display:flex;flex-direction:column;gap:12px;min-height:38vh;max-height:65vh;overflow:auto;padding:8px;background:var(--c-panel);border:1px solid var(--c-border);border-radius:8px;}',
      '.gw2 .msg{display:block;white-space:pre-wrap;}',
      '.gw2 .msg .bubble{width:100%;padding:0;}',
      '.gw2 .msg.user .bubble{background:var(--c-bg);border:1px solid var(--c-border);padding:10px 12px;border-radius:8px;}',
      '.gw2 .row{display:flex;gap:8px;align-items:center;margin-top:10px;}',
      '.gw2 input[type="text"]{flex:1;padding:14px;border:1px solid var(--c-border);border-radius:10px;background:transparent;color:var(--c-fg);font-size:18px;}',
      '.gw2 .clear{padding:10px 12px;border:1px solid var(--c-border);background:transparent;border-radius:8px;cursor:pointer;color:var(--c-fg);}',
      '.gw2 .send{width:42px;height:42px;border-radius:999px;border:2px solid var(--c-accent-border);background:var(--c-accent);color:#fff;cursor:pointer;display:grid;place-items:center;line-height:1;position:relative;}',
      '.gw2 .send .arrow{font-size:22px;font-weight:900;transform:scaleX(1.1) scaleY(0.6);}',
      '.gw2 .send.loading .arrow{visibility:hidden;}',
      '.gw2 .send.loading::after{content:"";width:16px;height:16px;border-radius:50%;border:2px solid rgba(255,255,255,0.6);border-top-color:rgba(255,255,255,1);position:absolute;inset:0;margin:auto;animation:gw2spin .9s linear infinite;}',
      '@keyframes gw2spin{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}',
      '.gw2 .pillbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;}',
      '.gw2 .citations{margin:6px 0 6px;}',
      '.gw2 .sect{margin-top:14px;}',
      '.gw2 .sect.title{font-weight:800;}',
      '.gw2 .sect.transl{font-style:italic;}',
      '.gw2 .wm-inline{margin-top:12px;}',
      '.gw2 .wm-key{font-weight:800;}'
    ].join(''));

    var wrap = el('div', { class: 'gw2' });
    for (var vk in vars) { try { wrap.style.setProperty(vk, vars[vk]); } catch(_){} }
    wrap.appendChild(style);

    var log = el('div', { class: 'log', role: 'log', 'aria-live': 'polite' });
    var input = el('input', { type: 'text', placeholder: 'Ask about the Gita… (e.g., 2.10 Sanskrit; Shankara for 2.10; 2.10 English and Meaning)', autocomplete: 'off' });
    var clearBtn = el('button', { class: 'clear', title: 'Clear conversation' }, 'Clear');
    var sendBtn = el('button', { class: 'send', title: 'Send' }, el('span', { class: 'arrow' }, '↑'));
    var row = el('div', { class: 'row' }, input, clearBtn, sendBtn);
    var pillbar = el('div', { class: 'pillbar' });

    wrap.appendChild(log);
    wrap.appendChild(row);
    wrap.appendChild(pillbar);

    if (host.firstChild) host.innerHTML = '';
    host.appendChild(wrap);

    function autoScroll() { log.scrollTop = log.scrollHeight; }

    function pushMessage(role, content, extras) {
      extras = extras || {};
      var msg = el('div', { class: 'msg ' + role });
      var bubble = el('div', { class: 'bubble' });

      // Citations (normalized)
      var citeArr = normalizeCitations(extras.citations || []);
      var citeSet = {}; var citesList = [];
      for (var i=0;i<citeArr.length;i++) { var cvv=citeArr[i]; if (!citeSet[cvv]) { citeSet[cvv]=1; citesList.push(cvv); } }

      if (role === 'user') {
        bubble.textContent = content;
      } else {
        if (content && typeof content === 'object') {
          // When we render field-specific results, we pass a synthetic "render" array
          if (content.__render && Object.prototype.toString.call(content.__render)==='[object Array]') {
            var blocks = content.__render;
            for (var bi=0; bi<blocks.length; bi++) {
              var block = blocks[bi];
              var key = block.key, text = block.text;
              if (!text) continue;
              if (key === 'title') {
                bubble.appendChild(el('div', { class: 'sect title' }, toPlain(text)));
              } else if (key === 'word_meanings') {
                bubble.appendChild(renderWordMeaningsInline(text));
              } else if (key === 'translation') {
                bubble.appendChild(el('div', { class: 'sect transl' }, toPlain(text)));
              } else {
                // For multiple fields, show labels
                if (blocks.length > 1 && FIELD_LABEL[key]) {
                  bubble.appendChild(el('div', { class: 'sect title' }, FIELD_LABEL[key]));
                }
                bubble.appendChild(el('div', { class: 'sect' }, toPlain(text)));
              }
            }
          } else {
            // default render (existing object)
            var any = false;
            if (content.title)       { any = true; bubble.appendChild(el('div', { class: 'sect title' }, toPlain(content.title))); }
            if (content.sanskrit)    { any = true; bubble.appendChild(el('div', { class: 'sect' }, toPlain(content.sanskrit))); }
            if (content.roman)       { any = true; bubble.appendChild(el('div', { class: 'sect' }, toPlain(content.roman))); }
            if (content.translation) { any = true; bubble.appendChild(el('div', { class: 'sect transl' }, toPlain(content.translation))); }
            if (content.word_meanings){ any = true; bubble.appendChild(renderWordMeaningsInline(content.word_meanings)); }
            if (content.summary)     { any = true; bubble.appendChild(el('div', { class: 'sect' }, 'Summary: ' + toPlain(content.summary))); }
            if (!any && content.answer) bubble.appendChild(el('div', {}, toPlain(content.answer)));
            if (!any && !content.answer) bubble.textContent = toPlain(JSON.stringify(content));
          }
        } else {
          bubble.textContent = toPlain(content);
        }
      }

      if (citesList.length && role === 'bot' && extras.onExplain) {
        var pills = renderCitations(citesList, extras.onExplain);
        if (pills) msg.appendChild(pills);
      }

      msg.appendChild(bubble);
      log.appendChild(msg);
      autoScroll();
    }

    function verseExists(ch, v) {
      // Basic guard: Gita has 18 chapters; verses per chapter vary; we only hard-block obvious impossibles
      if (!(ch>=1 && ch<=18)) return false;
      if (!(v>=1 && v<=200)) return false;
      return true;
    }

    function doAskRaw(q) {
      pushMessage('user', q);
      sendBtn.classList.add('loading');
      return fetchJSON(apiBase + '/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, topic: 'gita' })
      }).then(function (res) {
        var citations = Array.isArray(res.citations) ? res.citations : [];
        pushMessage('bot', (res.answer != null ? res.answer : res), {
          citations: citations,
          onExplain: function (ch, v) { doAsk('Explain ' + ch + '.' + v); }
        });
      }).catch(function (e) {
        pushMessage('bot', 'Error: ' + (e && e.message ? e.message : String(e)));
      }).finally(function () {
        sendBtn.classList.remove('loading');
      });
    }

    function doAsk(q) {
      // Natural-language field/verse detection
      var cv = detectVerse(q);
      var fields = detectFields(q);

      if (cv && !verseExists(cv.ch, cv.v)) {
        pushMessage('user', q);
        pushMessage('bot', 'Chapter ' + cv.ch + ', Verse ' + cv.v + ' does not exist.');
        return;
      }

      // If we have a verse and at least one field, fetch Explain CV and render only requested fields.
      if (cv && fields.length) {
        pushMessage('user', q);
        sendBtn.classList.add('loading');
        // Always fetch the canonical Explain, then filter client-side
        return fetchJSON(apiBase + '/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: 'Explain ' + cv.ch + '.' + cv.v, topic: 'gita' })
        }).then(function (res) {
          var obj = (res && (res.answer != null ? res.answer : res)) || {};
          var blocks = [];
          // Title first (if present)
          if (obj && obj.title) blocks.push({ key:'title', text: obj.title });

          // Expand "all_commentaries" already handled in detectFields, so just walk requested canonical keys
          var wanted = [];
          for (var i=0;i<fields.length;i++) {
            var f = fields[i];
            if (f === 'all_commentaries') continue; // already expanded earlier
            wanted.push(f);
          }
          // Deduplicate while preserving order
          var seen = {}; var ordered = [];
          for (var i2=0;i2<wanted.length;i2++) { var w=wanted[i2]; if (!seen[w]) { seen[w]=1; ordered.push(w); } }

          // Pull each field from the object
          for (var j=0;j<ordered.length;j++) {
            var key = ordered[j];
            var val = obj ? (obj[key] || '') : '';
            if (!val && key==='roman' && obj && obj.transliteration) val = obj.transliteration; // safety alias
            if (!val) continue;
            blocks.push({ key:key, text: val });
          }

          // If "commentary" generic requested but fields absent, say so
          if (!blocks.length && fields.length) {
            blocks.push({ key:'title', text: 'No requested fields found for ' + cv.ch + '.' + cv.v });
          }

          var citations = Array.isArray(res.citations) ? res.citations : [];
          pushMessage('bot', { __render: blocks }, {
            citations: citations,
            onExplain: function (ch, v) { doAsk('Explain ' + ch + '.' + v); }
          });
        }).catch(function (e) {
          pushMessage('bot', 'Error: ' + (e && e.message ? e.message : String(e)));
        }).finally(function () {
          sendBtn.classList.remove('loading');
        });
      }

      // Otherwise just do the normal ask (Explain C.V or term search)
      return doAskRaw(q);
    }

    // wire controls
    sendBtn.addEventListener('click', function () {
      var q = (input.value || '').trim();
      if (!q) return;
      input.value = '';
      doAsk(q);
      input.focus();
    });
    input.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') sendBtn.click();
    });
    clearBtn.addEventListener('click', function () {
      log.innerHTML = '';
      input.focus();
    });

    return { ask: doAsk };
  }

  return { mount: mount };
})();

if (typeof window !== 'undefined') window.GitaWidget = GitaWidget;
