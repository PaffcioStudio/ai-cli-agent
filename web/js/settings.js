/** settings.js - modal ustawień (Ollama host/port + system prompt + logi) */

import { API } from './config.js';

const $ = id => document.getElementById(id);

// Zapamiętuje ostatnio załadowane dane z serwera (do autozapisu przy zmianie trybu)
let _lastPromptData = { cli_content: '', web_content: '' };

export function bindSettings(onSaved) {
  $('settingsBtn').addEventListener('click', openSettings);
  $('closeSettings').addEventListener('click', closeSettings);
  $('cancelSettings').addEventListener('click', closeSettings);
  $('settingsOverlay').addEventListener('click', e => {
    if (e.target === $('settingsOverlay')) closeSettings();
  });

  // Przełącznik trybu - autozapis wpisu web prompt przed przełączeniem
  $('promptModeSelect')?.addEventListener('change', async e => {
    const newMode  = e.target.value;
    const prevMode = e.target.dataset.prevMode || 'disabled';

    // Autozapis: jeśli poprzedni tryb był 'web' - zapisz aktualną treść textarea
    if (prevMode === 'web') {
      const content = $('cfgPrompt').value;
      _lastPromptData.web_content = content;
      try {
        await fetch(API.prompt, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content, mode: 'web' }),
        });
      } catch {}
    }

    // Załaduj odpowiednią treść dla nowego trybu
    if (newMode === 'web') {
      $('cfgPrompt').value = _lastPromptData.web_content || '';
    }
    // cli/disabled - textarea jest ukryta, nie dotykamy jej treści

    e.target.dataset.prevMode = newMode;
    updatePromptModeUI();
  });

  // Zakładki
  $('settingsTabMain')?.addEventListener('click', () => switchTab('main'));
  $('settingsTabLogs')?.addEventListener('click', () => switchTab('logs'));

  // Logi
  $('logsRefreshBtn')?.addEventListener('click', loadLogs);
  $('logsClearBtn')?.addEventListener('click', clearLogs);

  $('saveSettings').addEventListener('click', async () => {
    try {
      const cfgRes = await fetch(API.config).then(r => r.json());
      const config = {
        ...(cfgRes.config || {}),
        ollama_host: $('cfgHost').value.trim(),
        ollama_port: parseInt($('cfgPort').value) || 11434,
      };

      const mode = $('promptModeSelect')?.value || 'disabled';
      // Treść tylko gdy tryb web - nigdy nie wysyłamy cli_content z powrotem
      const content = mode === 'web' ? $('cfgPrompt').value : '';

      await Promise.all([
        fetch(API.config, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ config }),
        }),
        fetch(API.prompt, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content, mode }),
        }),
      ]);
      closeSettings();
      onSaved?.();
    } catch (e) {
      alert('Blad zapisu: ' + e.message);
    }
  });
}

function switchTab(tab) {
  const isMain = tab === 'main';
  $('settingsTabMain')?.classList.toggle('active', isMain);
  $('settingsTabLogs')?.classList.toggle('active', !isMain);
  $('settingsBodyMain')?.classList.toggle('hidden', !isMain);
  $('settingsBodyLogs')?.classList.toggle('hidden', isMain);
  if (!isMain) loadLogs();
}

function updatePromptModeUI() {
  const mode = $('promptModeSelect')?.value || 'disabled';
  const wrap = $('cfgPromptWrap');
  const hint = $('cfgPromptHint');
  if (!wrap) return;

  wrap.classList.toggle('hidden', mode !== 'web');

  if (hint) {
    if (mode === 'cli')      hint.textContent = 'Uzywany prompt z ~/.config/ai/prompt.txt (wspolny z CLI).';
    else if (mode === 'web') hint.textContent = 'Wlasny prompt dla web panelu zapisany w prompt-web.txt.';
    else                     hint.textContent = 'Zaden system prompt nie bedzie uzyty w web panelu.';
  }
}

async function openSettings() {
  $('settingsOverlay').classList.remove('hidden');
  switchTab('main');
  $('cfgPromptWrap')?.classList.add('hidden');

  try {
    const [cfgRes, prmRes] = await Promise.all([
      fetch(API.config).then(r => r.json()),
      fetch(API.prompt).then(r => r.json()),
    ]);
    $('cfgHost').value = cfgRes.config?.ollama_host || '127.0.0.1';
    $('cfgPort').value = cfgRes.config?.ollama_port || 11434;

    const mode = prmRes.mode || 'disabled';

    // Zapamiętaj obie wersje osobno - cli_content nigdy nie trafia do textarea
    _lastPromptData = {
      cli_content: prmRes.cli_content || '',
      web_content: prmRes.web_content || '',
    };

    const sel = $('promptModeSelect');
    if (sel) {
      sel.value = mode;
      sel.dataset.prevMode = mode;
    }

    // W textarea tylko web prompt (pusty gdy nigdy nie zapisany) - NIGDY cli_content
    $('cfgPrompt').value = mode === 'web' ? _lastPromptData.web_content : '';

    updatePromptModeUI();
  } catch {
    updatePromptModeUI();
  }
}

function closeSettings() {
  $('settingsOverlay').classList.add('hidden');
}

async function loadLogs() {
  const box = $('logsBox');
  if (!box) return;
  box.textContent = 'Ladowanie...';
  try {
    const d = await fetch(API.logs).then(r => r.json());
    if (d.error) { box.textContent = 'Blad: ' + d.error; return; }
    box.textContent = d.logs || '(brak logow)';
    box.scrollTop   = box.scrollHeight;
  } catch (e) {
    box.textContent = 'Blad polaczenia: ' + e.message;
  }
}

async function clearLogs() {
  if (!confirm('Usunac wszystkie logi?')) return;
  try {
    const d = await fetch(API.logsClear, { method: 'POST' }).then(r => r.json());
    if (d.success) loadLogs();
    else alert('Blad: ' + (d.error || 'nieznany'));
  } catch (e) {
    alert('Blad: ' + e.message);
  }
}
