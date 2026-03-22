/** theme.js - zarządzanie motywem jasny/ciemny */

const HLJS_DARK  = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css';
const HLJS_LIGHT = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css';

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('ai-theme', theme);
  const link = document.getElementById('hljs-theme');
  if (link) link.href = theme === 'dark' ? HLJS_DARK : HLJS_LIGHT;
}

export function initTheme() {
  applyTheme(localStorage.getItem('ai-theme') || 'dark');
}

export function bindThemeToggle(btnId) {
  document.getElementById(btnId)?.addEventListener('click', () => {
    const cur = document.documentElement.getAttribute('data-theme');
    applyTheme(cur === 'dark' ? 'light' : 'dark');
  });
}
