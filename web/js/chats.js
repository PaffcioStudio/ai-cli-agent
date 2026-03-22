/** chats.js - historia konwersacji (zapis/odczyt na serwerze) */

import { API, state }     from './config.js';
import { uid, escHtml, reinitIcons } from './utils.js';
import { appendMessage }  from './messages.js';
import { showWelcome, showMessages, scrollBottom } from './view.js';

const $ = id => document.getElementById(id);

// ── Lista chatów ──────────────────────────────────────────────

export async function loadChatList() {
  try {
    const d     = await fetch(API.chats).then(r => r.json());
    state.chats = d.chats || [];
  } catch {
    state.chats = [];
  }
  renderChatList();
}

export function renderChatList() {
  const list = $('chatList');
  list.innerHTML = '';

  if (!state.chats.length) {
    list.innerHTML = '<div class="chat-empty">Brak historii</div>';
    return;
  }

  const frag = document.createDocumentFragment();
  state.chats.forEach(chat => {
    const div   = document.createElement('div');
    div.className  = 'chat-item' + (chat.id === state.activeChatId ? ' active' : '');
    div.dataset.id = chat.id;
    const label = chat.title || '(nowy chat)';

    div.innerHTML = `
      <i data-lucide="message-square" width="13" height="13" class="chat-icon"></i>
      <span class="chat-item-text">${escHtml(label)}</span>
      <button class="chat-item-del" title="Usuń konwersację" data-id="${chat.id}">
        <i data-lucide="trash-2" width="12" height="12"></i>
      </button>`;

    div.addEventListener('click', e => {
      if (!e.target.closest('.chat-item-del')) loadChat(chat.id);
    });
    div.querySelector('.chat-item-del').addEventListener('click', e => {
      e.stopPropagation();
      deleteChat(chat.id);
    });
    frag.appendChild(div);
  });

  list.appendChild(frag);
  reinitIcons(list);
}

export function updateChatListActive() {
  document.querySelectorAll('.chat-item').forEach(item =>
    item.classList.toggle('active', item.dataset.id === state.activeChatId)
  );
}

// ── Operacje na pojedynczym chacie ────────────────────────────

export async function loadChat(id) {
  try {
    const d = await fetch(API.chatGet(id)).then(r => r.json());
    if (d.error) return;
    const chat            = d.chat;
    state.activeChatId    = chat.id;
    state.activeMessages  = chat.messages || [];
    // Wyczyść poprzedni sandbox przed załadowaniem nowego
    state.sessionUploads  = [];
    state.sandboxTree     = [];
    $('messages').innerHTML = '';
    state.activeMessages.forEach(m => appendMessage(m.role, m.content, false));
    showMessages();
    updateChatListActive();
    scrollBottom();

    // Załaduj sandbox tej sesji
    const { loadSessionUploads, loadWorkspaceTree, renderUploadedFiles, renderWorkspaceTree } = await import('./sandbox.js');
    const { updateSandboxUI } = await import('./main.js');
    renderUploadedFiles();    // najpierw wyczyść widok
    renderWorkspaceTree();    // j.w.
    await loadSessionUploads(id);
    await loadWorkspaceTree(id);
    updateSandboxUI();
  } catch (e) {
    console.error('loadChat', e);
  }
}

export async function deleteChat(id) {
  try {
    await fetch(API.chatDel(id), { method: 'POST' });
    if (state.activeChatId === id) {
      startNewChat();
    } else {
      state.chats = state.chats.filter(c => c.id !== id);
      renderChatList();
    }
  } catch {}
}

export async function saveActiveChat() {
  if (!state.activeChatId) return;
  const meta    = state.chats.find(c => c.id === state.activeChatId);
  const payload = {
    id:       state.activeChatId,
    title:    meta?.title || '',
    model:    state.activeModel || '',
    messages: state.activeMessages,
    created:  meta?.created || Date.now(),
  };
  try {
    await fetch(API.chats, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ chat: payload }),
    });
    await loadChatList();
  } catch {}
}

export function ensureActiveChat() {
  if (state.activeChatId) return;
  const id = uid();
  state.activeChatId   = id;
  state.activeMessages = [];
  state.chats.unshift({
    id, title: '', model: state.activeModel,
    created: Date.now(), updated: Date.now(), msg_count: 0,
  });
  renderChatList();
}

export async function startNewChat() {
  state.activeChatId   = null;
  state.activeMessages = [];
  state.sessionUploads = [];
  state.sandboxTree    = [];
  $('messages').innerHTML = '';
  showWelcome();
  updateChatListActive();

  // Wyczyść widok sandbox
  const { renderUploadedFiles, renderWorkspaceTree } = await import('./sandbox.js');
  const { updateSandboxUI } = await import('./main.js');
  renderUploadedFiles();
  renderWorkspaceTree();
  updateSandboxUI();
}
