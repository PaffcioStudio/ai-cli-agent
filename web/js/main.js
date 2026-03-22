/** main.js - punkt wejścia, spina wszystkie moduły */

import { state }                                       from './config.js';
import { initTheme, bindThemeToggle }                  from './theme.js';
import { loadModels, bindModelPicker }                 from './models.js';
import { loadChatList, startNewChat }                  from './chats.js';
import { bindInput }                                   from './input.js';
import { bindSettings }                                from './settings.js';
import { checkStatus }                                 from './status.js';
import { showWelcome }                                 from './view.js';
import { bindMemoryPanel, loadMemoryFacts }            from './memory.js';
import { bindUpload, bindDownloadLinks,
         loadSessionUploads, loadWorkspaceTree,
         renderUploadedFiles }                         from './sandbox.js';

const $ = id => document.getElementById(id);

async function init() {
  initTheme();
  bindThemeToggle('themeToggle');

  $('sidebarToggle').addEventListener('click', () =>
    $('sidebar').classList.toggle('collapsed'));

  $('newChatBtn').addEventListener('click', () => startNewChat());

  bindModelPicker();
  bindInput();
  bindSettings(() => checkStatus());
  bindUpload();
  bindDownloadLinks();

  // Download workspace ZIP (przycisk w topbarze)
  $('downloadWorkspaceBtn')?.addEventListener('click', () => {
    if (state.activeChatId) {
      const a = document.createElement('a');
      a.href = `/api/download/${state.activeChatId}/workspace.zip`;
      a.download = 'workspace.zip';
      a.click();
    }
  });

  // Odśwież drzewo workspace ręcznie
  $('treeRefreshBtn')?.addEventListener('click', () => {
    if (state.activeChatId) loadWorkspaceTree(state.activeChatId);
  });

  showWelcome();

  await checkStatus();
  await loadModels();
  await loadChatList();

  setInterval(checkStatus, 30_000);

  // Pamięć
  bindMemoryPanel();
  const facts = await loadMemoryFacts();
  const cnt   = $('memoryCount');
  if (cnt && facts.length) cnt.textContent = facts.length;

  // Załaduj sandbox aktywnej sesji jeśli jest
  if (state.activeChatId) {
    await loadSessionUploads(state.activeChatId);
    await loadWorkspaceTree(state.activeChatId);
    updateSandboxUI();
  }

  if (window.lucide) lucide.createIcons();
}

// Pokaż/ukryj elementy sandbox w sidebarze
export function updateSandboxUI() {
  const hasSession = !!state.activeChatId;
  const label      = $('sandboxSectionLabel');
  const sep        = $('sandboxSep');
  const tree       = $('workspaceTree');
  const dlBtn      = $('downloadWorkspaceBtn');

  if (label) label.style.display = hasSession ? 'flex' : 'none';
  if (sep)   sep.style.display   = hasSession ? 'block' : 'none';
  if (tree)  tree.classList.toggle('hidden', !hasSession);
  if (dlBtn) dlBtn.classList.toggle('hidden', !hasSession);
}

init();
