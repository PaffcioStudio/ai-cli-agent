/** view.js - przełączanie widoków (welcome / messages) + scroll */

const $ = id => document.getElementById(id);

export function showWelcome() {
  $('welcome').style.display = 'flex';
  $('messages').classList.add('hidden');
}

export function showMessages() {
  $('welcome').style.display = 'none';
  $('messages').classList.remove('hidden');
}

export function scrollBottom() {
  requestAnimationFrame(() => {
    const area = $('chatArea');
    if (area) area.scrollTo({ top: area.scrollHeight, behavior: 'smooth' });
  });
}
