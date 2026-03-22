/** input.js - input box: auto-resize, wysyłanie wiadomości */

import { API, state }                            from './config.js';
import { appendMessage, appendTyping, removeTyping } from './messages.js';
import { ensureActiveChat, saveActiveChat }       from './chats.js';
import { checkAutoSave }                          from './memory.js';
import { loadWorkspaceTree }                      from './sandbox.js';

const $ = id => document.getElementById(id);

function getInput()   { return $('msgInput'); }
function getSendBtn() { return $('sendBtn');  }

// ── Auto-resize textarea ──────────────────────────────────────

function resizeInput() {
  const inp = getInput();
  inp.style.height = 'auto';
  inp.style.height = Math.min(inp.scrollHeight, 200) + 'px';
}

function updateSendBtn() {
  getSendBtn().disabled = !getInput().value.trim() || state.generating;
}

// ── Wysłanie do AI (eksportowane dla sandbox.js) ──────────────

export async function sendToAI(text, { silent = false } = {}) {
  if (!text || state.generating) return;

  state.generating = true;
  getSendBtn().disabled = true;

  ensureActiveChat();

  if (!silent) {
    const userMsg = { role: 'user', content: text };
    state.activeMessages.push(userMsg);
    const meta = state.chats.find(c => c.id === state.activeChatId);
    if (meta && !meta.title) meta.title = text.slice(0, 50);
    appendMessage('user', text);
  }

  appendTyping();
  await saveActiveChat();

  try {
    const resp = await fetch(API.chat, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        model:      state.activeModel,
        messages:   state.activeMessages.slice(-20),
        session_id: state.activeChatId || '',  // sandbox context
      }),
    });

    removeTyping();

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
      appendMessage('error', err.error || `Błąd serwera (${resp.status})`);
      if (!silent) state.activeMessages.pop();
    } else {
      const data  = await resp.json();
      const reply = data.message || data.content || data.response || '(brak odpowiedzi)';
      state.activeMessages.push({ role: 'assistant', content: reply });
      appendMessage('assistant', reply);
      await saveActiveChat();
      if (!silent) checkAutoSave(text);
      // Odśwież drzewo workspace po każdej odpowiedzi AI (mogło coś zmienić)
      if (state.activeChatId) loadWorkspaceTree(state.activeChatId);
    }
  } catch (err) {
    removeTyping();
    appendMessage('error', `Błąd połączenia: ${err.message}`);
    if (!silent) state.activeMessages.pop();
  }

  state.generating = false;
  updateSendBtn();
}

// ── Send (z pola input) ───────────────────────────────────────

async function sendMessage() {
  const inp  = getInput();
  const text = inp.value.trim();
  if (!text || state.generating) return;

  inp.value = '';
  resizeInput();
  await sendToAI(text);
}

// ── Bind ──────────────────────────────────────────────────────

export function bindInput() {
  const inp  = getInput();
  const send = getSendBtn();

  inp.addEventListener('input', () => { resizeInput(); updateSendBtn(); });

  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!send.disabled) sendMessage();
    }
  });

  send.addEventListener('click', sendMessage);

  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      inp.value = chip.dataset.p;
      inp.dispatchEvent(new Event('input'));
      sendMessage();
    });
  });
}
