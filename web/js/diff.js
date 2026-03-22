/** diff.js – parser i renderer unified diff (kolorowanie + accept/reject) */

import { escHtml, reinitIcons } from './utils.js';

/**
 * Wykrywa bloki unified diff w tekście i zwraca HTML z renderowanym diffem.
 * Wzorzec: linie zaczynające się od --- / +++ / @@ / +liniadodana / -liniaUsunięta
 */
export function renderDiffBlocks(text) {
  // Szukaj bloków diff (--- a/plik ... +++ b/plik ... @@ ...)
  const diffRegex = /^(---\s+.+\n\+\+\+\s+.+\n(?:@@.+?@@\n(?:[+\- @\\].*\n?)*)+)/gm;
  return text.replace(diffRegex, (match) => buildDiffHtml(match));
}

function buildDiffHtml(raw) {
  const lines  = raw.split('\n');
  const chunks = parseChunks(lines);
  const id     = 'diff-' + Math.random().toString(36).slice(2, 8);

  const header = lines.slice(0, 2).join('\n');
  const headerHtml = `<div class="diff-header">${escHtml(header)}</div>`;

  const chunksHtml = chunks.map((chunk, ci) => buildChunkHtml(id, ci, chunk)).join('');

  return `<div class="diff-block" id="${id}">${headerHtml}${chunksHtml}</div>`;
}

function parseChunks(lines) {
  const chunks = [];
  let current  = null;
  for (const line of lines) {
    if (line.startsWith('@@')) {
      if (current) chunks.push(current);
      current = { header: line, lines: [] };
    } else if (current) {
      current.lines.push(line);
    }
  }
  if (current) chunks.push(current);
  return chunks;
}

function buildChunkHtml(diffId, chunkIdx, chunk) {
  const linesHtml = chunk.lines.map(line => {
    if (line.startsWith('+') && !line.startsWith('+++')) {
      return `<div class="diff-line diff-add"><span class="diff-sign">+</span>${escHtml(line.slice(1))}</div>`;
    }
    if (line.startsWith('-') && !line.startsWith('---')) {
      return `<div class="diff-line diff-del"><span class="diff-sign">-</span>${escHtml(line.slice(1))}</div>`;
    }
    return `<div class="diff-line diff-ctx"><span class="diff-sign"> </span>${escHtml(line.slice(1) || line)}</div>`;
  }).join('');

  const chunkId = `${diffId}-c${chunkIdx}`;

  return `
<div class="diff-chunk" id="${chunkId}" data-chunk-idx="${chunkIdx}" data-diff-id="${diffId}">
  <div class="diff-chunk-header">
    <span class="diff-hunk-info">${escHtml(chunk.header)}</span>
    <div class="diff-actions">
      <button class="diff-btn diff-accept" data-action="accept" data-chunk="${chunkId}"
              title="Akceptuj tę zmianę">
        <i data-lucide="check" width="12" height="12"></i> Akceptuj
      </button>
      <button class="diff-btn diff-reject" data-action="reject" data-chunk="${chunkId}"
              title="Odrzuć tę zmianę">
        <i data-lucide="x" width="12" height="12"></i> Odrzuć
      </button>
    </div>
  </div>
  <div class="diff-lines">${linesHtml}</div>
</div>`;
}

// ── Bindowanie przycisków accept/reject ───────────────────────────────────────

export function bindDiffActions(container) {
  container.addEventListener('click', async e => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const action  = btn.dataset.action;   // "accept" | "reject"
    const chunkId = btn.dataset.chunk;
    const chunkEl = document.getElementById(chunkId);
    if (!chunkEl) return;

    if (action === 'accept') {
      chunkEl.classList.add('diff-accepted');
      chunkEl.querySelector('.diff-actions').innerHTML =
        '<span class="diff-status accepted"><i data-lucide="check-circle" width="12" height="12"></i> Zaakceptowano</span>';
    } else {
      chunkEl.classList.add('diff-rejected');
      chunkEl.querySelector('.diff-actions').innerHTML =
        '<span class="diff-status rejected"><i data-lucide="x-circle" width="12" height="12"></i> Odrzucono</span>';
      // Powiadom AI o odrzuceniu (opcjonalne - można rozbudować)
      const { appendMessage } = await import('./messages.js');
      appendMessage('system', `Zmiana z chunka ${chunkId} odrzucona.`);
    }
    reinitIcons(chunkEl);
  });
}
