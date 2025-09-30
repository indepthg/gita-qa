
// Minimal widget: keeps it plain, no CSS injection beyond a couple inline styles if needed.
// Usage: include this script, then call GitaWidget.mount({ root: '#gita', apiBase: 'https://YOUR-APP.onrailway.app' })

const GitaWidget = (() => {
  function el(tag, attrs = {}, ...children) {
    const e = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => {
      if (k === 'style' && typeof v === 'object') Object.assign(e.style, v);
      else if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.substring(2), v);
      else e.setAttribute(k, v);
    });
    children.flat().forEach(c => {
      if (typeof c === 'string') e.appendChild(document.createTextNode(c));
      else if (c) e.appendChild(c);
    });
    return e;
  }

  async function fetchJSON(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }

  function renderPills(container, apiBase, onPick) {
    fetchJSON(`${apiBase}/suggest`).then(data => {
      const box = el('div', { style: { display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '8px' } });
      (data.suggestions || []).forEach(s => {
        const b = el('button', { style: { padding: '6px 10px', borderRadius: '999px', border: '1px solid #ddd', background: '#f7f7f7', cursor: 'pointer' } }, s);
        b.addEventListener('click', () => onPick(s));
        box.appendChild(b);
      });
      container.appendChild(box);
    }).catch(() => {});
  }

  function mount({ root, apiBase }) {
    const host = (typeof root === 'string') ? document.querySelector(root) : root;
    if (!host) throw new Error('Root not found');

    const out = el('div', { style: { border: '1px solid #eee', padding: '12px', borderRadius: '8px' } });
    const log = el('div', { style: { display: 'flex', flexDirection: 'column', gap: '10px', minHeight: '120px' } });
    const form = el('div', { style: { display: 'flex', gap: '8px', marginTop: '8px' } });
    const input = el('input', { type: 'text', placeholder: 'Ask about the Gita…', style: { flex: 1, padding: '10px 12px', borderRadius: '6px', border: '1px solid #ddd' } });
    const send = el('button', { style: { padding: '10px 14px', borderRadius: '6px', border: '1px solid #e07a00', background: '#ff8d1a', color: '#fff', cursor: 'pointer' } }, 'Ask');
    const clear = el('button', { style: { padding: '10px 14px', borderRadius: '6px', border: '1px solid #ddd', background: '#fafafa', cursor: 'pointer' } }, 'Clear');

    function pushMessage(role, text, citations) {
      const line = el('div');
      const tag = role === 'user' ? 'You: ' : 'Answer: ';
      const t = el('div', {}, tag + (text || ''));
      line.appendChild(t);
      if (citations && citations.length) {
        const c = el('div', { style: { fontSize: '12px', color: '#666' } }, citations.join(' '));
        line.appendChild(c);
      }
      log.appendChild(line);
      log.scrollTop = log.scrollHeight;
    }

    async function ask(q) {
      pushMessage('user', q);
      try {
        const data = await fetchJSON(`${apiBase}/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q, topic: 'gita' })
        });
        pushMessage('bot', data.answer, data.citations);
      } catch (e) {
        pushMessage('bot', 'Error: ' + (e.message || e));
      }
    }

    send.addEventListener('click', () => {
      const q = input.value.trim();
      if (!q) return;
      input.value = '';
      ask(q);
    });
    input.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') send.click();
    });
    clear.addEventListener('click', () => { log.innerHTML = ''; });

    form.appendChild(input);
    form.appendChild(send);
    form.appendChild(clear);

    out.appendChild(log);
    out.appendChild(form);
    host.appendChild(out);

    renderPills(out, apiBase, (s) => ask(s));

    return { ask };
  }

  return { mount };
})();

// UMD-lite
if (typeof window !== 'undefined') window.GitaWidget = GitaWidget;
