// ===================================
// API Configuration
// ===================================
const API_BASE = '/api';

// ===================================
// Monaco Editor Instance
// ===================================
let monacoEditor = null;

// ===================================
// Theme Management
// ===================================
function initTheme() {
    const savedTheme = localStorage.getItem('ai-panel-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    // Update Monaco if exists
    if (monacoEditor) {
        updateMonacoTheme(savedTheme);
    }
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('ai-panel-theme', newTheme);
    
    // Update Monaco if exists
    if (monacoEditor) {
        updateMonacoTheme(newTheme);
    }
}

function updateMonacoTheme(theme) {
    if (monacoEditor) {
        monaco.editor.setTheme(theme === 'dark' ? 'vs-dark' : 'vs');
    }
}

// ===================================
// Monaco Editor Initialization
// ===================================
function initMonacoEditor() {
    require.config({ 
        paths: { 
            'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' 
        }
    });

    require(['vs/editor/editor.main'], function() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        
        monacoEditor = monaco.editor.create(document.getElementById('config-editor-container'), {
            value: '',
            language: 'json',
            theme: currentTheme === 'dark' ? 'vs-dark' : 'vs',
            automaticLayout: true,
            minimap: { enabled: true },
            scrollBeyondLastLine: false,
            fontSize: 14,
            lineNumbers: 'on',
            renderWhitespace: 'selection',
            tabSize: 2,
            formatOnPaste: true,
            formatOnType: true,
            folding: true,
            bracketPairColorization: {
                enabled: true
            }
        });
    });
}

// ===================================
// DOM Elements
// ===================================
const tabs = document.querySelectorAll('.tab');
const tabContents = document.querySelectorAll('.tab-content');
const themeToggle = document.getElementById('theme-toggle');

// ===================================
// Event Listeners - Theme
// ===================================
themeToggle.addEventListener('click', toggleTheme);

// ===================================
// Event Listeners - Tabs
// ===================================
tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const targetTab = tab.dataset.tab;
        
        // Update active tab
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        
        // Update active content
        tabContents.forEach(content => content.classList.remove('active'));
        document.getElementById(`tab-${targetTab}`).classList.add('active');
        
        // Load data for tab
        loadTabData(targetTab);
    });
});

// ===================================
// Tab Data Loading
// ===================================
function loadTabData(tabName) {
    switch(tabName) {
        case 'status':
            loadStatus();
            break;
        case 'config':
            loadConfig();
            break;
        case 'prompt':
            loadPrompt();
            break;
        case 'logs':
            loadLogs();
            break;
    }
}

// ===================================
// STATUS TAB
// ===================================
async function loadStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();
        
        // Update version and mode
        updateElement('version', data.version || 'unknown');
        updateElement('mode', data.mode || 'project');
        updateElement('chat-model', data.chat_model || 'unknown');
        updateElement('embed-model', data.embed_model || 'unknown');
        updateElement('ollama-host', `${data.ollama_host}:${data.ollama_port}`);
        
        // Ollama status with icon
        const ollamaStatus = document.getElementById('ollama-status');
        if (data.ollama_available) {
            ollamaStatus.innerHTML = '<i data-lucide="check-circle" style="width:16px;height:16px;color:var(--success);"></i> Dostępna';
            ollamaStatus.style.color = 'var(--success)';
        } else {
            ollamaStatus.innerHTML = '<i data-lucide="x-circle" style="width:16px;height:16px;color:var(--danger);"></i> Niedostępna';
            ollamaStatus.style.color = 'var(--danger)';
        }
        
        // Capabilities
        loadCapabilities(data.capabilities || {});
        
        // Re-render icons
        lucide.createIcons();
        
    } catch (error) {
        console.error('Error loading status:', error);
        showNotification('Nie udało się załadować statusu', 'error');
    }
}

function updateElement(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function loadCapabilities(capabilities) {
    const container = document.getElementById('capabilities-list');
    container.innerHTML = '';
    
    const descriptions = {
        'allow_execute': 'Wykonywanie komend systemowych i otwieranie plików',
        'allow_delete': 'Usuwanie i przenoszenie plików',
        'allow_git': 'Operacje Git (commit, add, push)',
        'allow_network': 'Dostęp do sieci (fetch, API calls)'
    };
    
    const icons = {
        'allow_execute': 'terminal',
        'allow_delete': 'trash-2',
        'allow_git': 'git-branch',
        'allow_network': 'wifi'
    };
    
    for (const [name, enabled] of Object.entries(capabilities)) {
        const div = document.createElement('div');
        div.className = 'capability';
        
        div.innerHTML = `
            <div>
                <div class="capability-name">
                    <i data-lucide="${icons[name] || 'shield'}" style="width:16px;height:16px;display:inline;margin-right:8px;"></i>
                    ${name}
                </div>
                <div class="capability-desc">${descriptions[name] || ''}</div>
            </div>
            <span class="capability-status ${enabled ? 'enabled' : 'disabled'}">
                ${enabled ? 'Włączone' : 'Wyłączone'}
            </span>
        `;
        
        container.appendChild(div);
    }
    
    // Re-render icons
    lucide.createIcons();
}

// ===================================
// CONFIG TAB
// ===================================
async function loadConfig() {
    // Initialize Monaco if not done
    if (!monacoEditor) {
        initMonacoEditor();
        
        // Wait for Monaco to initialize
        const waitForMonaco = setInterval(() => {
            if (monacoEditor) {
                clearInterval(waitForMonaco);
                fetchAndLoadConfig();
            }
        }, 100);
    } else {
        fetchAndLoadConfig();
    }
}

async function fetchAndLoadConfig() {
    try {
        const response = await fetch(`${API_BASE}/config`);
        const data = await response.json();
        
        if (monacoEditor) {
            monacoEditor.setValue(JSON.stringify(data.config, null, 2));
        }
    } catch (error) {
        showMessage('config', 'error', 'Nie udało się załadować konfiguracji');
        console.error(error);
    }
}

document.getElementById('save-config').addEventListener('click', async () => {
    if (!monacoEditor) return;
    
    const configText = monacoEditor.getValue();
    
    try {
        const config = JSON.parse(configText);
        
        const response = await fetch(`${API_BASE}/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage('config', 'success', result.message || 'Konfiguracja zapisana pomyślnie');
            showNotification('Konfiguracja zapisana', 'success');
        } else {
            showMessage('config', 'error', result.error || 'Błąd zapisu');
            showNotification(result.error || 'Błąd zapisu', 'error');
        }
    } catch (error) {
        showMessage('config', 'error', 'Nieprawidłowy JSON: ' + error.message);
        showNotification('Nieprawidłowy JSON', 'error');
    }
});

document.getElementById('reload-config').addEventListener('click', loadConfig);

document.getElementById('format-config').addEventListener('click', () => {
    if (!monacoEditor) return;
    
    monacoEditor.getAction('editor.action.formatDocument').run();
    showNotification('Kod sformatowany', 'success');
});

// ===================================
// PROMPT TAB
// ===================================
async function loadPrompt() {
    try {
        const response = await fetch(`${API_BASE}/prompt`);
        const data = await response.json();
        
        document.getElementById('prompt-editor').value = data.content || '';
        document.getElementById('prompt-exists').textContent = data.exists ? 'Aktywny' : 'Nieaktywny';
        document.getElementById('prompt-modified').textContent = data.modified || 'Nigdy';
        
        // Re-render icons
        lucide.createIcons();
        
    } catch (error) {
        showMessage('prompt', 'error', 'Nie udało się załadować promptu');
        console.error(error);
    }
}

document.getElementById('save-prompt').addEventListener('click', async () => {
    const content = document.getElementById('prompt-editor').value;
    
    try {
        const response = await fetch(`${API_BASE}/prompt`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage('prompt', 'success', 'System prompt zapisany pomyślnie');
            showNotification('Prompt zapisany', 'success');
            loadPrompt();
        } else {
            showMessage('prompt', 'error', result.error || 'Błąd zapisu');
            showNotification(result.error || 'Błąd zapisu', 'error');
        }
    } catch (error) {
        showMessage('prompt', 'error', 'Błąd połączenia: ' + error.message);
        console.error(error);
    }
});

document.getElementById('reload-prompt').addEventListener('click', loadPrompt);

document.getElementById('clear-prompt').addEventListener('click', async () => {
    if (!confirm('Czy na pewno chcesz wyczyścić system prompt?')) {
        return;
    }
    
    document.getElementById('prompt-editor').value = '';
    
    try {
        const response = await fetch(`${API_BASE}/prompt`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: '' })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage('prompt', 'success', 'System prompt wyczyszczony');
            showNotification('Prompt wyczyszczony', 'success');
            loadPrompt();
        }
    } catch (error) {
        showMessage('prompt', 'error', 'Błąd: ' + error.message);
        console.error(error);
    }
});

// ===================================
// LOGS TAB
// ===================================
async function loadLogs() {
    try {
        const response = await fetch(`${API_BASE}/logs`);
        const data = await response.json();
        
        const logsViewer = document.getElementById('logs-viewer');
        logsViewer.textContent = data.logs || 'Brak logów';
        
        // Auto-scroll to bottom
        logsViewer.scrollTop = logsViewer.scrollHeight;
        
    } catch (error) {
        document.getElementById('logs-viewer').textContent = 'Nie udało się załadować logów';
        console.error(error);
    }
}

document.getElementById('reload-logs').addEventListener('click', loadLogs);

document.getElementById('copy-logs').addEventListener('click', () => {
    const logs = document.getElementById('logs-viewer').textContent;
    navigator.clipboard.writeText(logs).then(() => {
        showNotification('Logi skopiowane do schowka', 'success');
    }).catch(() => {
        showNotification('Nie udało się skopiować', 'error');
    });
});

document.getElementById('download-logs').addEventListener('click', () => {
    const logs = document.getElementById('logs-viewer').textContent;
    const blob = new Blob([logs], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ai-cli-logs-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showNotification('Logi pobrane', 'success');
});

// ===================================
// UTILITIES
// ===================================
function showMessage(section, type, text) {
    const messageEl = document.getElementById(`${section}-message`);
    if (!messageEl) return;
    
    messageEl.className = `message ${type}`;
    messageEl.textContent = text;
    messageEl.style.display = 'flex';
    
    setTimeout(() => {
        messageEl.style.display = 'none';
    }, 5000);
}

function showNotification(text, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i data-lucide="${type === 'success' ? 'check-circle' : 'alert-circle'}" style="width:20px;height:20px;"></i>
        <span>${text}</span>
    `;
    
    // Style
    Object.assign(notification.style, {
        position: 'fixed',
        top: '2rem',
        right: '2rem',
        background: type === 'success' ? 'var(--success-bg)' : 'var(--danger-bg)',
        border: `2px solid ${type === 'success' ? 'var(--success)' : 'var(--danger)'}`,
        color: type === 'success' ? 'var(--success)' : 'var(--danger)',
        padding: '1rem 1.5rem',
        borderRadius: '12px',
        boxShadow: 'var(--shadow-xl)',
        zIndex: '10000',
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        fontWeight: '600',
        animation: 'slideInRight 0.4s cubic-bezier(0.4, 0, 0.2, 1)'
    });
    
    document.body.appendChild(notification);
    lucide.createIcons();
    
    // Remove after 3s
    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// ===================================
// INITIALIZATION
// ===================================
document.addEventListener('DOMContentLoaded', () => {
    // Initialize theme
    initTheme();
    
    // Initialize Lucide icons
    lucide.createIcons();
    
    // Load initial tab
    loadStatus();
});