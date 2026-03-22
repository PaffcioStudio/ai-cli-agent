/** config.js - endpointy API + współdzielony stan aplikacji */

export const API = {
  status:    '/api/status',
  config:    '/api/config',
  prompt:    '/api/prompt',
  models:    '/api/models',
  chat:      '/api/chat',
  chats:     '/api/chats',
  chatGet:   id => `/api/chats/${id}`,
  chatDel:   id => `/api/chats/${id}/delete`,
  memory:    '/api/memory',
  memoryDel: '/api/memory/delete',
  logs:      '/api/logs',
  logsClear: '/api/logs/clear',
  // Sandbox
  upload:       id => `/api/upload/${id}`,
  sandboxTree:  id => `/api/sandbox/${id}/tree`,
  sandboxUploads: id => `/api/sandbox/${id}/uploads`,
  download:     (id, file) => `/api/download/${id}/${encodeURIComponent(file)}`,
  downloadWorkspace: id => `/api/download/${id}/workspace.zip`,
  sessionDel:   id => `/api/session/${id}/delete`,
};

export const state = {
  chats:          [],     // metadane konwersacji (serwer)
  activeChatId:   null,
  activeMessages: [],     // wiadomości aktywnej rozmowy (serwer)
  models:         [],
  activeModel:    localStorage.getItem('ai-model') || null,
  configModel:    null,   // chat_model z config.json (domyślny)
  generating:     false,
  // Sandbox
  sessionUploads: [],     // lista wgranych plików aktywnej sesji
  sandboxTree:    [],     // drzewo workspace aktywnej sesji
};
