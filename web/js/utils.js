/** utils.js - małe helpery używane w całej apce */

export function uid() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

export function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function getModelTag(name) {
  const n = name.toLowerCase();
  if (n.includes(':cloud') || n.endsWith('-cloud'))                            return 'cloud';
  if (n.includes('embed') || n.includes('bge') || n.includes('nomic'))        return 'embed';
  if (n.includes('vl') || n.includes('vision') || n.includes('llava'))        return 'vision';
  if (n.includes('coder') || n.includes('code') || n.includes('starcoder'))   return 'coder';
  return 'chat';
}

export function getTagClass(tag) {
  return (
    { cloud: 'tag-cloud', vision: 'tag-vision', embed: 'tag-embed', coder: 'tag-coder', chat: 'tag-chat' }[tag]
    || 'tag-chat'
  );
}

export function formatSize(bytes) {
  if (!bytes) return '';
  if (bytes >= 1e9) return (bytes / 1e9).toFixed(1) + ' GB';
  if (bytes >= 1e6) return (bytes / 1e6).toFixed(0) + ' MB';
  return bytes + ' B';
}

/** Reinicjuje ikony Lucide w danym kontenerze (lub całym dokumencie). */
export function reinitIcons(container) {
  if (!window.lucide) return;
  if (container) {
    lucide.createIcons({ nodes: [container] });
  } else {
    lucide.createIcons();
  }
}
