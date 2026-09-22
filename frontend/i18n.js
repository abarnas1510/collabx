(() => {
  const API_BASE = window.__COLLABX_API_BASE__ || window.COLLABX_API_BASE || 'http://127.0.0.1:8000';
  const LANG_KEY = 'collabx_lang';
  const cache = new Map();
  const ignoredTags = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'SVG', 'CODE', 'PRE']);
  let scheduled = false;
  const translatedNodes = new WeakSet();

  function language() {
    return localStorage.getItem(LANG_KEY) || document.documentElement.lang || 'en';
  }

  function cleanText(value) {
    return value.replace(/\s+/g, ' ').trim();
  }

  function shouldTranslate(textNode) {
    const text = cleanText(textNode.nodeValue || '');
    const parent = textNode.parentElement;
    if (!text || !parent || ignoredTags.has(parent.tagName)) return false;
    if (translatedNodes.has(textNode)) return false;
    if (parent.closest('[data-no-translate], .brand-name, .brand-mark, option')) return false;
    if (/^[\d\s.,:%+–—#()/_-]+$/.test(text)) return false;
    return text.length >= 2;
  }

  async function translate(text, target) {
    const key = `${target}:${text}`;
    if (cache.has(key)) return cache.get(key);
    const saved = localStorage.getItem(`collabx_translation:${key}`);
    if (saved) {
      cache.set(key, saved);
      return saved;
    }
    try {
      const response = await fetch(`${API_BASE}/i18n/translate?language=${encodeURIComponent(target)}&text=${encodeURIComponent(text)}`);
      if (!response.ok) return text;
      const data = await response.json();
      const result = data.translation || text;
      cache.set(key, result);
      localStorage.setItem(`collabx_translation:${key}`, result);
      return result;
    } catch (_) {
      return text;
    }
  }

  async function translatePage() {
    const target = language();
    if (!target || target === 'en') return;
    const nodes = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) if (shouldTranslate(node)) nodes.push(node);

    await Promise.all(nodes.map(async textNode => {
      const original = cleanText(textNode.nodeValue);
      const translated = await translate(original, target);
      if (translated && translated !== original && textNode.parentElement) {
        textNode.nodeValue = textNode.nodeValue.replace(original, translated);
        translatedNodes.add(textNode);
      }
    }));

    document.querySelectorAll('input[placeholder], textarea[placeholder], [aria-label]').forEach(async element => {
      if (element.matches('[data-no-translate], .brand-name')) return;
      const attribute = element.hasAttribute('placeholder') ? 'placeholder' : 'aria-label';
      const original = element.getAttribute(attribute);
      if (!original || !original.trim()) return;
      const translated = await translate(original.trim(), target);
      if (translated) element.setAttribute(attribute, translated);
    });

    document.querySelectorAll('[title]:not([data-no-translate])').forEach(async element => {
      const original = element.getAttribute('title');
      if (!original || !original.trim()) return;
      const translated = await translate(original.trim(), target);
      if (translated) element.setAttribute('title', translated);
    });
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    setTimeout(() => {
      scheduled = false;
      translatePage();
    }, 80);
  }

  const observer = new MutationObserver(schedule);
  window.addEventListener('DOMContentLoaded', () => {
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    document.querySelectorAll('select#globalLang, select#workspace-lang').forEach(select => select.addEventListener('change', schedule));
    schedule();
  });
  window.addEventListener('collabx-language-changed', schedule);
})();
