/** models.js - model picker: ładowanie, wyświetlanie, przełączanie */

import { API, state }                    from './config.js';
import { escHtml, getModelTag, getTagClass, formatSize } from './utils.js';

const $ = id => document.getElementById(id);

export function setActiveModel(name) {
  state.activeModel = name;
  localStorage.setItem('ai-model', name);

  const tag = getModelTag(name);
  $('modelBadge').textContent    = tag.toUpperCase();
  $('modelName').textContent     = name;
  $('topbarModel').textContent   = name;
  $('welcomeModel').textContent  = name;

  document.querySelectorAll('.model-item').forEach(item =>
    item.classList.toggle('active', item.dataset.name === name)
  );
}

export function renderModelList(models) {
  const list = $('modelList');
  list.innerHTML = '';

  if (!models.length) {
    list.innerHTML = '<div class="model-empty">Brak wyników</div>';
    return;
  }

  const frag = document.createDocumentFragment();
  models.forEach(m => {
    const tag  = getModelTag(m.name);
    const cls  = getTagClass(tag);
    const size = formatSize(m.size);
    const div  = document.createElement('div');

    // Oznacz model z konfiguracji gwiazdką
    const isDefault = m.name === state.configModel;
    div.className  = 'model-item' + (m.name === state.activeModel ? ' active' : '');
    div.dataset.name = m.name;
    div.innerHTML  = `
      <span class="model-item-name">${escHtml(m.name)}${isDefault ? ' <span class="model-default-star" title="Domyślny model z konfiguracji">★</span>' : ''}</span>
      <span class="model-item-tag ${cls}">${tag}</span>
      ${size ? `<span class="model-item-size">${size}</span>` : ''}`;

    div.addEventListener('click', () => {
      setActiveModel(m.name);
      closeModelDropdown();
    });
    frag.appendChild(div);
  });
  list.appendChild(frag);
}

function closeModelDropdown() {
  $('modelDropdown').classList.add('hidden');
  $('modelPicker').classList.remove('open');
}

export async function loadModels() {
  try {
    let models     = [];
    let configModel = null;

    // Pobierz status - zawiera chat_model z config.json
    try {
      const s   = await fetch(API.status).then(r => r.json());
      configModel = s.chat_model || null;
      state.configModel = configModel;
    } catch {}

    // Lista modeli przez /api/models (proxy)
    try {
      const r = await fetch(API.models);
      if (r.ok) { const d = await r.json(); models = d.models || []; }
    } catch {}

    // Fallback: bezpośrednio Ollama
    if (!models.length) {
      try {
        const s = await fetch(API.status).then(r => r.json());
        const r = await fetch(`http://${s.ollama_host || '127.0.0.1'}:${s.ollama_port || 11434}/api/tags`);
        const d = await r.json();
        models  = (d.models || []).map(m => ({ name: m.name, size: m.size || 0 }));
      } catch {}
    }

    state.models = models;
    renderModelList(models);

    // Priorytet wyboru modelu:
    // 1. Zapisany w localStorage (użytkownik ręcznie wybrał)
    // 2. chat_model z config.json (domyślny skonfigurowany przez użytkownika)
    // 3. Pierwszy dostępny model chat/coder
    const savedModel  = state.activeModel;
    const savedExists = savedModel && models.find(m => m.name === savedModel);

    if (savedExists) {
      setActiveModel(savedModel);
    } else if (configModel && models.find(m => m.name === configModel)) {
      setActiveModel(configModel);
    } else if (models.length) {
      const best = models.find(m => !['embed'].includes(getModelTag(m.name))) || models[0];
      setActiveModel(best.name);
    } else {
      $('modelName').textContent  = 'brak modeli';
      $('modelBadge').textContent = '—';
    }
  } catch {}
}

export function bindModelPicker() {
  const picker   = $('modelPicker');
  const current  = $('modelCurrent');
  const dropdown = $('modelDropdown');
  const search   = $('modelSearch');

  current.addEventListener('click', () => {
    const isOpen = !dropdown.classList.contains('hidden');
    dropdown.classList.toggle('hidden', isOpen);
    picker.classList.toggle('open', !isOpen);
    if (!isOpen) {
      search.value = '';
      renderModelList(state.models);
      search.focus();
    }
  });

  search.addEventListener('input', () => {
    const q = search.value.toLowerCase();
    renderModelList(state.models.filter(m => m.name.toLowerCase().includes(q)));
  });

  document.addEventListener('click', e => {
    if (!picker.contains(e.target)) {
      dropdown.classList.add('hidden');
      picker.classList.remove('open');
    }
  });
}
