/** messages.js - renderowanie wiadomości, bloki kodu, typing indicator */

import { escHtml, reinitIcons } from './utils.js';
import { showMessages, scrollBottom } from './view.js';
import { renderDiffBlocks, bindDiffActions } from './diff.js';
import { processDownloadLinks, makeDownloadButton } from './sandbox.js';

const $ = id => document.getElementById(id);

// ── Markdown + highlight.js setup ────────────────────────────

marked.setOptions({ breaks: true, gfm: true });

const renderer = new marked.Renderer();

renderer.code = (code, lang) => {
  const language = lang || 'text';
  let highlighted = escHtml(code);
  try {
    highlighted = hljs.getLanguage(language)
      ? hljs.highlight(code, { language }).value
      : hljs.highlightAuto(code).value;
  } catch {}

  const safeCode = escHtml(code);
  return `
<div class="code-block">
  <div class="code-header">
    <span class="code-lang">${escHtml(language)}</span>
    <button class="copy-btn" data-code="${safeCode}">
      <i data-lucide="copy" width="12" height="12"></i> Kopiuj
    </button>
  </div>
  <pre><code class="hljs language-${escHtml(language)}">${highlighted}</code></pre>
</div>`;
};

marked.use({ renderer });

// ── Kopiowanie kodu ───────────────────────────────────────────

function bindCopyCode(wrap) {
  wrap.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      const code = this.dataset.code
        .replace(/&amp;/g, '&').replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>').replace(/&quot;/g, '"');
      navigator.clipboard.writeText(code).then(() => {
        const orig = this.innerHTML;
        this.innerHTML = '<i data-lucide="check" width="12" height="12"></i> Skopiowano';
        this.classList.add('copied');
        reinitIcons(this);
        setTimeout(() => { this.innerHTML = orig; this.classList.remove('copied'); reinitIcons(this); }, 2000);
      });
    });
  });
}

// ── Kopiowanie całej odpowiedzi AI ────────────────────────────

function bindCopyMessage(btn, content) {
  btn.addEventListener('click', function () {
    navigator.clipboard.writeText(content).then(() => {
      this.innerHTML = '<i data-lucide="check" width="13" height="13"></i>';
      reinitIcons(this);
      setTimeout(() => {
        this.innerHTML = '<i data-lucide="copy" width="13" height="13"></i>';
        reinitIcons(this);
      }, 2000);
    });
  });
}

// ── Append message ────────────────────────────────────────────

export function appendMessage(role, content) {
  showMessages();

  const wrap = document.createElement('div');
  wrap.className = `msg msg-${role === 'assistant' ? 'ai' : role}`;

  if (role === 'user') {
    wrap.innerHTML = `
      <div class="msg-avatar user-avatar">
        <i data-lucide="user" width="15" height="15"></i>
      </div>
      <div class="msg-body">
        <div class="msg-user-bubble">${escHtml(content)}</div>
      </div>`;

  } else if (role === 'error') {
    wrap.innerHTML = `
      <div class="msg-avatar err-avatar">
        <i data-lucide="alert-triangle" width="15" height="15"></i>
      </div>
      <div class="msg-body">
        <div class="msg-error">${escHtml(content)}</div>
      </div>`;

  } else if (role === 'system-upload') {
    const [filename, sizeBytes, isZip] = Array.isArray(content)
      ? content : [content, 0, false];
    const fmt = (b) => {
      if (!b)              return null;
      if (b < 1024)        return b + ' B';
      if (b < 1024*1024)   return (b/1024).toFixed(1) + ' KB';
      return (b/1024/1024).toFixed(2) + ' MB';
    };
    const sizeStr = fmt(sizeBytes);
    wrap.innerHTML = `
      <div class="msg-avatar sys-avatar">
        <i data-lucide="${isZip ? 'file-archive' : 'file-up'}" width="15" height="15"></i>
      </div>
      <div class="msg-body">
        <div class="msg-upload-notice">
          <strong>${escHtml(String(filename))}</strong>
          ${sizeStr ? `<span class="upload-size-tag">${sizeStr}</span>` : ''}
          ${isZip ? '<span class="zip-tag">ZIP</span>' : ''}
        </div>
      </div>`;

  } else {
    // assistant
    const parsed  = renderDiffBlocks(marked.parse(content));
    wrap.innerHTML = `
      <div class="msg-avatar ai-avatar">⬡</div>
      <div class="msg-body">
        <div class="msg-content">${parsed}</div>
        <div class="msg-actions">
          <button class="msg-action-btn copy-msg-btn" title="Kopiuj odpowiedź">
            <i data-lucide="copy" width="13" height="13"></i>
          </button>
        </div>
      </div>`;
    bindCopyMessage(wrap.querySelector('.copy-msg-btn'), content);
    // Post-process: zamień surowe /api/download/... linki na przyciski
    processDownloadLinks(wrap);
    // Bind przycisków accept/reject w diffach
    bindDiffActions(wrap);
  }

  $('messages').appendChild(wrap);
  reinitIcons(wrap);
  bindCopyCode(wrap);
  scrollBottom();
  return wrap;
}

// Wariant dla appendMessage('system-upload', [filename, sizeMb, isZip])
export function appendUploadNotice(filename, sizeMb, isZip) {
  return appendMessage('system-upload', [filename, sizeMb, isZip]);
}

// ── Typing indicator ──────────────────────────────────────────

export function appendTyping() {
  showMessages();
  const wrap = document.createElement('div');
  wrap.className = 'msg msg-ai';
  wrap.id = 'typing-indicator';
  wrap.innerHTML = `
    <div class="msg-avatar ai-avatar">⬡</div>
    <div class="msg-body">
      <div class="typing"><span></span><span></span><span></span></div>
    </div>`;
  $('messages').appendChild(wrap);
  scrollBottom();
}

export function removeTyping() {
  $('typing-indicator')?.remove();
}
