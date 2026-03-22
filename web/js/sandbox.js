/** sandbox.js – upload plików, panel workspace, przycisk pobierania */

import { API, state } from './config.js';
import { escHtml, reinitIcons } from './utils.js';

const $ = id => document.getElementById(id);

// ── Upload ────────────────────────────────────────────────────────────────────

export async function uploadFile(file, sessionId) {
  if (!sessionId) {
    console.error('uploadFile: brak sessionId - nie można wgrać pliku');
    return null;
  }
  const form = new FormData();
  form.append('file', file);
  try {
    const r = await fetch(API.upload(sessionId), { method: 'POST', body: form });
    return await r.json();
  } catch (e) {
    console.error('upload error', e);
    return null;
  }
}

export function bindUpload() {
  const btn   = $('uploadBtn');
  const input = $('uploadInput');
  if (!btn || !input) return;

  btn.addEventListener('click', () => input.click());

  input.addEventListener('change', async () => {
    for (const file of input.files) await handleFileSelected(file);
    input.value = '';
  });

  // Drag & drop na cały obszar chatu
  const area = $('chatArea');
  if (area) {
    area.addEventListener('dragover', e => { e.preventDefault(); area.classList.add('drag-over'); });
    area.addEventListener('dragleave', () => area.classList.remove('drag-over'));
    area.addEventListener('drop', async e => {
      e.preventDefault();
      area.classList.remove('drag-over');
      for (const file of e.dataTransfer.files) await handleFileSelected(file);
    });
  }
}

async function handleFileSelected(file) {
  // Upewnij się że sesja istnieje przed uploadem
  if (!state.activeChatId) {
    const { ensureActiveChat } = await import('./chats.js');
    ensureActiveChat();
    // Odśwież sandbox UI po stworzeniu sesji
    const { updateSandboxUI } = await import('./main.js');
    updateSandboxUI();
  }

  if (!state.activeChatId) {
    console.error('Brak aktywnego chatu - nie można uploadować');
    showUploadError('Nie można wgrać pliku - brak aktywnej sesji');
    return;
  }

  // Pokaż pasek postępu
  showUploadProgress(file.name);

  const result = await uploadFile(file, state.activeChatId);
  hideUploadProgress();

  if (!result || result.error) {
    showUploadError(result?.error || 'Błąd uploadu');
    return;
  }

  // Zaktualizuj listę wgranych plików
  state.sessionUploads = [...(state.sessionUploads || []), {
    name:       result.filename,
    size_mb:    result.size_mb,
    size_bytes: result.size_bytes ?? Math.round(result.size_mb * 1024 * 1024),
    is_zip:     result.is_zip,
  }];
  renderUploadedFiles();

  // Wstrzyknij kontekst jako wiadomość systemową do AI
  if (result.ai_context) {
    const { appendUploadNotice }     = await import('./messages.js');
    const { saveActiveChat }         = await import('./chats.js');
    const { sendToAI }               = await import('./input.js');

    // Ustaw tytuł chatu na nazwę pliku (zamiast pierwszej linii ai_context)
    const meta = state.chats.find(c => c.id === state.activeChatId);
    if (meta && !meta.title) meta.title = result.filename;

    // Pokaż powiadomienie w UI z poprawnym rozmiarem
    const sizeBytes = result.size_bytes ?? Math.round((result.size_mb || 0) * 1024 * 1024);
    appendUploadNotice(result.filename, sizeBytes, result.is_zip);

    // Dodaj kontekst do historii (jako user - AI go otrzyma)
    state.activeMessages.push({ role: 'user', content: result.ai_context });
    await saveActiveChat();

    // Wyślij do AI (silent=true - nie pokazuje bańki użytkownika ponownie)
    await sendToAI(result.ai_context, { silent: true });
  }
}

// ── Panel wgranych plików ─────────────────────────────────────────────────────

function formatSize(bytes) {
  if (bytes === 0 || bytes == null) return '0 B';
  if (bytes < 1024)                 return bytes + ' B';
  if (bytes < 1024 * 1024)          return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024)   return (bytes / 1024 / 1024).toFixed(2) + ' MB';
  return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB';
}

export function renderUploadedFiles() {
  const panel = $('uploadedFiles');
  if (!panel) return;
  const files = state.sessionUploads || [];
  if (!files.length) {
    panel.innerHTML = '';
    panel.classList.add('hidden');
    return;
  }
  panel.classList.remove('hidden');
  panel.innerHTML = files.map(f => {
    const bytes = f.size_bytes ?? Math.round((f.size_mb || 0) * 1024 * 1024);
    return `
    <div class="upload-item">
      <i data-lucide="${f.is_zip ? 'file-archive' : 'file'}" width="13" height="13"></i>
      <span class="upload-name">${escHtml(f.name)}</span>
      <span class="upload-size">${formatSize(bytes)}</span>
    </div>`;
  }).join('');
  reinitIcons(panel);
}

export async function loadSessionUploads(sessionId) {
  if (!sessionId) return;
  try {
    const r = await fetch(API.sandboxUploads(sessionId));
    const d = await r.json();
    state.sessionUploads = d.uploads || [];
    renderUploadedFiles();
  } catch {}
}

// ── Drzewo workspace (file browser) ──────────────────────────────────────────

export async function loadWorkspaceTree(sessionId) {
  if (!sessionId) return;
  try {
    const r = await fetch(API.sandboxTree(sessionId));
    const d = await r.json();
    state.sandboxTree = d.tree || [];
    renderWorkspaceTree();
  } catch {}
}

export function renderWorkspaceTree() {
  const panel = $('workspaceTree');
  if (!panel) return;
  const tree = state.sandboxTree || [];
  if (!tree.length) {
    panel.innerHTML = '<div class="tree-empty">Workspace pusty</div>';
    return;
  }
  panel.innerHTML = tree.map(item => {
    const indent = '  '.repeat(item.depth);
    const icon   = item.is_dir ? 'folder' : 'file-text';
    const size   = !item.is_dir && item.size > 0
      ? `<span class="tree-size">${formatBytes(item.size)}</span>` : '';
    return `<div class="tree-item" style="padding-left:${item.depth * 14}px">
      <i data-lucide="${icon}" width="12" height="12"></i>
      <span class="tree-name">${escHtml(item.name)}</span>${size}
    </div>`;
  }).join('');
  reinitIcons(panel);
}

// ── Download ──────────────────────────────────────────────────────────────────

export function bindDownloadLinks() {
  // Wykrywa linki /api/download/ w wiadomościach AI i zamienia na przyciski
  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-download-url]');
    if (!btn) return;
    const url = btn.dataset.downloadUrl;
    const a   = document.createElement('a');
    a.href = url;
    a.download = '';
    a.click();
  });
}

export function makeDownloadButton(url, label = 'Pobierz') {
  const filename = url.split('/').pop();
  return `<button class="download-btn" data-download-url="${escHtml(url)}" title="Pobierz ${escHtml(filename)}">
    <i data-lucide="download" width="13" height="13"></i> ${escHtml(label)}
  </button>`;
}

// Wywołaj po renderowaniu wiadomości AI żeby zamienić surowe linki na przyciski
export function processDownloadLinks(msgEl) {
  const content = msgEl.querySelector('.msg-content');
  if (!content) return;
  // Zamień /api/download/... na klikalny przycisk
  content.innerHTML = content.innerHTML.replace(
    /(?:href=&quot;|&quot;|')?(\/api\/download\/[^\s<&"']+)/g,
    (match, url) => makeDownloadButton(url, 'Pobierz plik')
  );
  reinitIcons(content);
}

// ── Progress / error UI ───────────────────────────────────────────────────────

function showUploadProgress(name) {
  let el = $('uploadProgress');
  if (!el) {
    el = document.createElement('div');
    el.id = 'uploadProgress';
    el.className = 'upload-progress';
    $('inputWrap')?.prepend(el);
  }
  el.innerHTML = `<i data-lucide="loader" width="13" height="13" class="spin"></i> Wgrywam: ${escHtml(name)}`;
  el.classList.remove('hidden');
  reinitIcons(el);
}

function hideUploadProgress() {
  $('uploadProgress')?.classList.add('hidden');
}

function showUploadError(msg) {
  const { appendMessage } = import('./messages.js').then(m => {
    m.appendMessage('error', `Upload: ${msg}`);
  });
}

// ── Utils ─────────────────────────────────────────────────────────────────────

function formatBytes(b) {
  if (b >= 1e6) return (b / 1e6).toFixed(1) + ' MB';
  if (b >= 1e3) return (b / 1e3).toFixed(0) + ' KB';
  return b + ' B';
}
