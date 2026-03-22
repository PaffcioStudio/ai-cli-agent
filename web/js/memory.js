/** memory.js - panel pamięci globalnej (memory.json) */

import { API } from './config.js';
import { escHtml, reinitIcons } from './utils.js';

const $ = id => document.getElementById(id);

// ── Helpers ───────────────────────────────────────────────────

export async function loadMemoryFacts() {
  try {
    const data = await fetch(API.memory).then(r => r.json());
    return data.facts || [];
  } catch { return []; }
}

export async function addMemoryFact(content, category = 'general') {
  const r = await fetch(API.memory, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ content, category }),
  });
  return r.json();
}

export async function deleteMemoryFact(id) {
  const r = await fetch(API.memoryDel, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ id }),
  });
  return r.json();
}

// ── Render panel ──────────────────────────────────────────────

export async function renderMemoryPanel() {
  const panel = $('memoryPanel');
  if (!panel) return;

  const list  = $('memoryList');
  const count = $('memoryCount');
  list.innerHTML = '<div class="mem-loading">Ładowanie…</div>';

  const facts = await loadMemoryFacts();

  if (count) count.textContent = facts.length ? `${facts.length}` : '';

  if (!facts.length) {
    list.innerHTML = '<div class="mem-empty">Brak zapamiętanych faktów.<br>Napisz „zapamiętaj że…" w czacie.</div>';
    return;
  }

  list.innerHTML = '';
  facts.forEach(f => {
    const el = document.createElement('div');
    el.className = 'mem-item';
    el.innerHTML = `
      <span class="mem-tag">${escHtml(f.category)}</span>
      <span class="mem-content">${escHtml(f.content)}</span>
      <button class="mem-del" data-id="${f.id}" title="Usuń fakt">
        <i data-lucide="x" width="11" height="11"></i>
      </button>`;
    el.querySelector('.mem-del').addEventListener('click', async function() {
      this.disabled = true;
      await deleteMemoryFact(f.id);
      renderMemoryPanel();
    });
    list.appendChild(el);
    reinitIcons(el);
  });
}

// ── Add fact form ─────────────────────────────────────────────

export function bindMemoryPanel() {
  const openBtn  = $('memoryBtn');
  const panel    = $('memoryPanel');
  const closeBtn = $('memoryClose');
  const addBtn   = $('memoryAddBtn');
  const addInput = $('memoryAddInput');

  if (!panel) return;

  openBtn?.addEventListener('click', () => {
    panel.classList.toggle('hidden');
    if (!panel.classList.contains('hidden')) renderMemoryPanel();
  });

  closeBtn?.addEventListener('click', () => panel.classList.add('hidden'));

  // Zamknij kliknięciem poza panelem
  document.addEventListener('click', e => {
    if (!panel.classList.contains('hidden') &&
        !panel.contains(e.target) &&
        e.target !== openBtn && !openBtn?.contains(e.target)) {
      panel.classList.add('hidden');
    }
  });

  addBtn?.addEventListener('click', async () => {
    const val = addInput?.value.trim();
    if (!val) return;
    addBtn.disabled = true;
    await addMemoryFact(val);
    addInput.value = '';
    addBtn.disabled = false;
    renderMemoryPanel();
  });

  addInput?.addEventListener('keydown', e => {
    if (e.key === 'Enter') addBtn?.click();
  });
}

// ── Auto-save after send ──────────────────────────────────────

export function checkAutoSave(userText) {
  if (/zapamiętaj|zapamietaj|zapisz|zanotuj/i.test(userText)) {
    // Serwer już zapisuje automatycznie - tylko odśwież widok po chwili
    setTimeout(renderMemoryPanel, 800);
    // Pokaż licznik
    setTimeout(async () => {
      const count = $('memoryCount');
      if (!count) return;
      const facts = await loadMemoryFacts();
      count.textContent = facts.length ? `${facts.length}` : '';
    }, 900);
  }
}
