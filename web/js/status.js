/** status.js - polling statusu Ollama */

import { API } from './config.js';

const $ = id => document.getElementById(id);

export async function checkStatus() {
  try {
    const d = await fetch(API.status).then(r => r.json());
    if (d.ollama_available) {
      $('statusDot').className  = 'status-dot ok';
      $('statusText').textContent = 'Ollama online';
    } else {
      $('statusDot').className  = 'status-dot err';
      $('statusText').textContent = 'Ollama offline';
    }
  } catch {
    $('statusDot').className  = 'status-dot err';
    $('statusText').textContent = 'Brak połączenia';
  }
}
