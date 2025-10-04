/* Gita Q&A v2 — field-select widget (NL + AND), minimal UI, ES5-safe
   Version: fields-v1.0.1 (syntax-hardened)
   Notes:
   - Natural-language: "2.10 Sanskrit", "Shankara commentary for 2-10",
     "2:10 English and Meaning", "commentary for chapter 2 verse 10"
   - "English" = Transliteration (roman). "Meaning"/"Translation" = translation.
   - "Commentary" (generic) => Commentary1 (Śaṅkara) + Commentary2.
   - If no field words found -> normal ask (Explain / free Q).
   - Plain text only; clickable [C:V] citations; bold keys for word meanings.
   - Friendly error for obviously invalid verses (e.g., 2.84).
   - Minimal UI: no global CSS; keeps existing look.
*/

(function (global) {
  'use strict';

  // ========= EDITABLE FIELD MAPPINGS =========
  var FIELD_SYNONYMS = {
    sanskrit:        ["sanskrit"],
    roman:           ["transliteration", "roman", "english"],
    colloquial:      ["colloquial", "simple"],
    translation:     ["translation", "meaning", "rendering"],
    word_meanings:   ["word meaning", "word meanings", "word-by-word", "word by word", "padartha"],
    commentary1:     ["shankara", "śaṅkara", "shankaracharya", "commentary 1", "commentary1"],
    commentary2:     ["commentary 2", "commentary2", "modern commentary"],
    all_commentaries:["commentary", "all commentary", "all commentaries"]
  };

  var FIELD_LABEL = {
    sanskrit: "Sanskrit",
    roman: "Transliteration",
    colloquial: "Colloquial",
    translation: "Translation",
    word_meanings: "Word Meaning",
    commentary1: "Śaṅkara (Commentary 1)",
    commentary2: "Commentary 2"
  };

  // ========= small helpers =========
  function el(tag, attrs) {
    var e = document.createElement(tag);
    if (attrs && typeof attrs === 'object') {
      for (var k in attrs) {
        if (!Object.prototype.hasOwnProperty.call(attrs, k)) continue;
        var v = attrs[k];
        if (k === 'style' && v && typeof v === 'object') {
          for (var sk in v) { if (Object.prototype.hasOwnProperty.call(v, sk)) { try { e.style[sk] = v[sk]; } catch(_){} } }
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

  function fetchJSON(url, opts) {
    return fetch(url, opts).then(function (r) {
      if (!r.ok) return r.text().then(function(t){ throw new Error(t || ('HTTP ' + r.status)); });
      return r.json();
    });
  }

  // Hardened: no stray line breaks inside string literals
  function toPlain(text) {
    if (text == null) return '';
    var t = String(text);
    t = t.replace(/<\s*br\s*\/?\s*>/gi, '\\n');
    t = t.replace(/<[^>]+>/g, '');
    t = t.replace(/\r\n?|\u2028|\u2029/g, '\\n');
    t = t.replace(/&nbsp;/g, ' ');
    t = t.replace(/&amp;/g, '&');
    t = t.replace(/&lt;/g, '<');
    t = t.replace(/&gt;/g, '>');
    t = t.replace(/&quot;/g, '"');
    t = t.replace(/&#39;/g, "'");
    t = t.replace(/[ \t]+\n/g, '\\n');
    t = t.replace(/\n{3,}/g, '\\n\\n');
    t = t.trim();
    return t;
  }

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

  function normalizeCitations(raw) {
    var out = {}; var list = [];
    (raw || []).forEach(function (c) {
      var s = c;
      if (Object.prototype.toString.call(c) === '[object Array]') {
        if (c.length === 2 && !isNaN(+c[0]) && !isNaN(+c[1])) s = c[0] + ':' + c[1];
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
        style: { borderRadius: '999px', padding: '2px 8px', cursor: 'pointer' }
      }, label);
      btn.addEventListener('click', function () { if (onExplain) onExplain(ch, v); });
      wrap.appendChild(btn);
    });
    return wrap;
  }

  // ========= NL parsing =========
  function stripAccents(s) {
    try { return s.normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }
    catch(_) { return s; }
  }

  function detectVerse(raw) {
    var q = ' ' + stripAccents(String(raw).toLowerCase()) + ' ';
    var m = /(^|\D)(\d{1,2})\s*[:.\-\s]\s*(\d{1,3})(\D|$)/.exec(q);
    if (m) return {ch:+m[2], v:+m[3]};
    m = /chapter\s*(\d{1,2})\D+verse\s*(\d{1,3})/.exec(q);
    if (m) return {ch:+m[1], v:+m[2]};
    m = /\bch(?:apter)?\s*(\d{1,2})\D+v(?:erse)?\s*(\d{1,3})/.exec(q);
    if (m) return {ch:+m[1], v:+m[2]};
    return null;
  }

  function buildSynonymIndex() {
    var idx = [];
    for (var key in FIELD_SYNONYMS) {
      if (!Object.prototype.hasOwnProperty.call(FIELD_SYNONYMS, key)) continue;
      var arr = FIELD_SYNONYMS[key] || [];
      for (var i=0;i<arr.length;i++) {
        var syn = stripAccents(String(arr[i]).toLowerCase());
        idx.push({ syn: syn, field: key });
      }
    }
    idx.sort(function (a,b) { return b.syn.length - a.syn.length; });
    return idx;
  }
  var SYNS = buildSynonymIndex();

  function detectFields(raw) {
    var q = ' ' + stripAccents(String(raw).toLowerCase()) + ' ';
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

  // ========= Core widget =========
  function mount(opts) {
    opts = opts || {};
    var host = (typeof opts.root === 'string') ? document.querySelector(opts.root) : opts.root;
    if (!host) throw new Error('Root element not found');
    var apiBase = (typeof opts.apiBase === 'string') ? opts.apiBase : '';

    var log = el('div', { class: 'log' });
    var input = el('input', { type: 'text', placeholder: 'Ask… e.g., 2.10 Sanskrit; Shankara for 2:10; 2.10 English and Meaning', style: { width:'100%', padding:'12px', borderRadius:'8px', border:'1px solid #444' } });
    var clearBtn = el('button', { type:'button' }, 'Clear');
    var sendBtn = el('button', { type:'button' }, 'Send');
    var form = el('div', { class: 'row', style:{ display:'flex', gap:'8px', marginTop:'10px' } }, input, clearBtn, sendBtn);

    function autoScroll() { log.scrollTop = log.scrollHeight; }

    function pushMessage(role, content, extras) {
      extras = extras || {};
      var msg = el('div', { class: 'msg ' + role });
      var bubble = el('div', { class: 'bubble' });

      var citeArr = normalizeCitations(extras.citations || []);
      if (role === 'user') {
        bubble.textContent = content;
      } else {
        if (content && typeof content === 'object' && content.__render) {
          var blocks = content.__render;
          for (var bi=0; bi<blocks.length; bi++) {
            var block = blocks[bi];
            if (block.key === 'title') {
              bubble.appendChild(el('div', {}, toPlain(block.text)));
            } else if (block.key === 'word_meanings') {
              bubble.appendChild(renderWordMeaningsInline(block.text));
            } else if (block.key === 'translation') {
              bubble.appendChild(el('div', {}, toPlain(block.text)));
            } else {
              if (blocks.length > 1 && FIELD_LABEL[block.key]) {
                bubble.appendChild(el('div', { style:{ fontWeight:'800', marginTop:'8px' } }, FIELD_LABEL[block.key]));
              }
              bubble.appendChild(el('div', {}, toPlain(block.text)));
            }
          }
        } else if (content && typeof content === 'object') {
          var any = false;
          if (content.title)       { any = true; bubble.appendChild(el('div', {}, toPlain(content.title))); }
          if (content.sanskrit)    { any = true; bubble.appendChild(el('div', {}, toPlain(content.sanskrit))); }
          if (content.roman)       { any = true; bubble.appendChild(el('div', {}, toPlain(content.roman))); }
          if (content.translation) { any = true; bubble.appendChild(el('div', {}, toPlain(content.translation))); }
          if (content.word_meanings){ any = true; bubble.appendChild(renderWordMeaningsInline(content.word_meanings)); }
          if (content.summary)     { any = true; bubble.appendChild(el('div', {}, 'Summary: ' + toPlain(content.summary))); }
          if (!any && content.answer) bubble.appendChild(el('div', {}, toPlain(content.answer)));
          if (!any && !content.answer) bubble.textContent = toPlain(JSON.stringify(content));
        } else {
          bubble.textContent = toPlain(content);
        }
      }

      var pills = renderCitations(citeArr, function(ch, v) { doAsk('Explain ' + ch + '.' + v); });
      if (pills) msg.appendChild(pills);

      msg.appendChild(bubble);
      log.appendChild(msg);
      autoScroll();
    }

    function verseExists(ch, v) {
      if (!(ch>=1 && ch<=18)) return false;
      if (!(v>=1 && v<=200)) return false;
      return true;
    }

    function doAskRaw(q) {
      pushMessage('user', q);
      return fetchJSON(apiBase + '/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, topic: 'gita' })
      }).then(function (res) {
        var citations = Array.isArray(res.citations) ? res.citations : [];
        pushMessage('bot', (res.answer != null ? res.answer : res), { citations: citations });
      }).catch(function (e) {
        pushMessage('bot', 'Error: ' + (e && e.message ? e.message : String(e)));
      });
    }

    function doAsk(q) {
      var cv = detectVerse(q);
      var fields = detectFields(q);

      if (cv && !verseExists(cv.ch, cv.v)) {
        pushMessage('user', q);
        pushMessage('bot', 'Chapter ' + cv.ch + ', Verse ' + cv.v + ' does not exist.');
        return;
      }

      if (cv && fields.length) {
        pushMessage('user', q);
        return fetchJSON(apiBase + '/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: 'Explain ' + cv.ch + '.' + cv.v, topic: 'gita' })
        }).then(function (res) {
          var obj = (res && (res.answer != null ? res.answer : res)) || {};
          var blocks = [];
          if (obj && obj.title) blocks.push({ key:'title', text: obj.title });

          var wanted = [];
          for (var i=0;i<fields.length;i++) {
            var f = fields[i];
            if (f === 'all_commentaries') continue;
            wanted.push(f);
          }
          var seen = {}; var ordered = [];
          for (var i2=0;i2<wanted.length;i2++) { var w=wanted[i2]; if (!seen[w]) { seen[w]=1; ordered.push(w); } }

          for (var j=0;j<ordered.length;j++) {
            var key = ordered[j];
            var val = obj ? (obj[key] || '') : '';
            if (!val && key==='roman' && obj && obj.transliteration) val = obj.transliteration;
            if (!val) continue;
            blocks.push({ key:key, text: val });
          }

          var citations = Array.isArray(res.citations) ? res.citations : [];
          if (!blocks.length && fields.length) blocks.push({ key:'title', text: 'No requested fields found for ' + cv.ch + '.' + cv.v });

          pushMessage('bot', { __render: blocks }, { citations: citations });
        }).catch(function (e) {
          pushMessage('bot', 'Error: ' + (e && e.message ? e.message : String(e)));
        });
      }

      return doAskRaw(q);
    }

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

    // Mount
    var container = el('div', {});
    container.appendChild(log);
    container.appendChild(form);
    host.innerHTML = '';
    host.appendChild(container);

    return { ask: doAsk };
  }

  var api = { mount: mount };
  if (typeof global !== 'undefined') global.GitaWidget = api;

})(typeof window !== 'undefined' ? window : this);
