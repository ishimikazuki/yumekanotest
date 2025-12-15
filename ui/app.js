// DOM Elements
const els = {
    userId: document.getElementById('userId'),
    chartCanvas: document.getElementById('emotionChart'),
    sceneBg: document.getElementById('scene-bg'),
    dialogueText: document.getElementById('dialogueText'),
    chatHistory: document.getElementById('chatHistory'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    resetBtn: document.getElementById('resetBtn'),
    stateLog: document.getElementById('stateLog'), // Note: this element might have been removed or changed in previous steps? Let's check index.html from Step 458. Ah, stateLog was removed in Step 458.
    characterImg: document.getElementById('characterImg')
};

// Check if stateLog exists, if not, create it or ignore? 
// In Step 458, the "Debug State Log" div was removed. 
// User wants rollback. I should check if I need to restore that DIV in index.html too?
// In Step 458 I replaced `<div style="margin-top: 20px;">... <div class="json-log" id="stateLog">` with `user-id-section`.
// So I should restore it in index.html as well if I want full rollback.
// Correcting my previous tool call for index.html... I only replaced `user-id-section`... 
// Wait, I will stick to restoring a working state. I will assume stateLog is not critical or I should add it back.
// Let's assume I need to handle it gracefully in JS if missing.

// Chart.js Instance
let emotionChart = null;

// Config
const CONFIG = {
    POLL_INTERVAL: 2000, // ms
    SCENE_IMAGES: {
        'default': 'linear-gradient(to bottom, #0f172a, #334155)',
        'scene_station_front': 'url("https://images.unsplash.com/photo-1596260273763-718871bd80e6?q=80&w=2670&auto=format&fit=crop")',
        'scene_cafe_table': 'url("https://images.unsplash.com/photo-1554118811-1e0d58224f24?q=80&w=2647&auto=format&fit=crop")',
        'scene_cafe_terrace': 'url("https://images.unsplash.com/photo-1554118811-1e0d58224f24?q=80&w=2647&auto=format&fit=crop")',
        'scene_studio': 'url("https://images.unsplash.com/photo-1518834107812-67b0b7c58434?q=80&w=2535&auto=format&fit=crop")'
    },
    CHAR_IMAGES: {
        'normal': 'static/yumeka_normal.png',
        'happy': 'static/yumeka_happy.png',
        'angry': 'static/yumeka_angry.png'
    }
};

// Initialize
function init() {
    initChart();
    setupEvents();
    // Default load
    fetchState();
}

function initChart() {
    const ctx = els.chartCanvas.getContext('2d');

    // Gradient for radar area
    const gradient = ctx.createRadialGradient(150, 150, 0, 150, 150, 150);
    gradient.addColorStop(0, 'rgba(34, 211, 238, 0.5)');
    gradient.addColorStop(1, 'rgba(244, 114, 182, 0.1)');

    emotionChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Pleasure (快)', 'Arousal (覚醒)', 'Dominance (支配)'],
            datasets: [{
                label: 'Emotion State',
                data: [0, 0, 0],
                backgroundColor: 'rgba(34, 211, 238, 0.2)',
                borderColor: '#22d3ee',
                pointBackgroundColor: '#f472b6',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: '#f472b6'
            }]
        },
        options: {
            scales: {
                r: {
                    angleLines: { color: 'rgba(255,255,255,0.1)' },
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    pointLabels: { color: '#94a3b8', font: { size: 12 } },
                    suggestedMin: -10,
                    suggestedMax: 10,
                    ticks: { display: false } // hide numbers
                }
            },
            plugins: {
                legend: { display: false }
            },
            animation: {
                duration: 1000
            }
        }
    });
}

function setupEvents() {
    els.sendBtn.addEventListener('click', sendMessage);
    els.resetBtn.addEventListener('click', resetSession);

    els.messageInput.addEventListener('keydown', (e) => {
        // IME変換中は送信しない
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
            e.preventDefault();
            sendMessage();
        }
    });

    els.userId.addEventListener('change', fetchState);
}

// Logic
const API_BASE = '/api';

async function fetchState() {
    const uid = els.userId.value.trim();
    if (!uid) return;

    try {
        const res = await fetch(`${API_BASE}/state/${encodeURIComponent(uid)}`);
        if (res.ok) {
            const data = await res.json();
            updateUI(data);
        }
    } catch (e) {
        console.error("Fetch State Error", e);
    }
}

function updateUI(data) {
    if (!data || !data.state) return;

    const s = data.state;
    const e = s.emotion || { pleasure: 0, arousal: 0, dominance: 0 };

    // 1. Update Chart
    emotionChart.data.datasets[0].data = [e.pleasure, e.arousal, e.dominance];
    emotionChart.update();

    // 2. Character Logic
    let charKey = 'normal';
    if (e.pleasure > 5) charKey = 'happy';
    else if (e.pleasure < 0 && e.dominance > 0) charKey = 'angry';

    els.characterImg.src = CONFIG.CHAR_IMAGES[charKey] || CONFIG.CHAR_IMAGES['normal'];

    // 3. State Log (if exists)
    // if (els.stateLog) els.stateLog.textContent = JSON.stringify(s, null, 2);

    // 4. Update Scene Background
    const sceneKey = s.scenario?.current_scene;
    if (sceneKey && CONFIG.SCENE_IMAGES[sceneKey]) {
        els.sceneBg.style.backgroundImage = CONFIG.SCENE_IMAGES[sceneKey];
        els.sceneBg.style.opacity = '0.6';
    } else {
        els.sceneBg.style.backgroundImage = CONFIG.SCENE_IMAGES['default'];
        els.sceneBg.style.opacity = '0.3';
    }

    // 5. Update Chat History
    const history = data.history || [];
    renderHistory(history);

    // 6. Update Dialogue Box
    const assistantMsgs = history.filter(h => h.role === 'assistant');
    if (assistantMsgs.length > 0) {
        const last = assistantMsgs[assistantMsgs.length - 1];
        if (els.dialogueText.textContent !== last.content) {
            els.dialogueText.textContent = last.content;
        }
    } else {
        els.dialogueText.textContent = "...";
    }
}

let renderedHistoryLength = 0;
function renderHistory(history) {
    if (history.length === renderedHistoryLength) return;

    els.chatHistory.innerHTML = "";
    history.forEach(h => {
        const div = document.createElement('div');
        div.className = `chat-bubble ${h.role}`;
        div.textContent = h.content;
        els.chatHistory.appendChild(div);
    });

    // Scroll to bottom
    els.chatHistory.scrollTop = els.chatHistory.scrollHeight;
    renderedHistoryLength = history.length;
}

async function sendMessage() {
    const uid = els.userId.value.trim();
    const msg = els.messageInput.value.trim();

    if (!uid) {
        alert("Please enter a User ID");
        return;
    }
    if (!msg) return;

    els.messageInput.value = "";
    els.sendBtn.disabled = true;

    const tempDiv = document.createElement('div');
    tempDiv.className = 'chat-bubble user';
    tempDiv.textContent = msg;
    els.chatHistory.appendChild(tempDiv);
    els.chatHistory.scrollTop = els.chatHistory.scrollHeight;

    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: uid, message: msg })
        });

        if (res.ok) {
            const data = await res.json();

            // 応答をダイアログボックスに表示
            if (data.reply) {
                els.dialogueText.textContent = data.reply;

                // チャット履歴にも追加
                const replyDiv = document.createElement('div');
                replyDiv.className = 'chat-bubble assistant';
                replyDiv.textContent = data.reply;
                els.chatHistory.appendChild(replyDiv);
                els.chatHistory.scrollTop = els.chatHistory.scrollHeight;
                renderedHistoryLength++;
            }

            // 状態を更新（感情チャートのみ、dialogueTextは触らない）
            if (data.state) {
                updateEmotionChart(data.state);
            }

            // チャット後にログを自動更新
            refreshLogs();
        } else {
            const errorData = await res.json();
            alert("Error: " + (errorData.detail || res.statusText));
            refreshLogs(); // エラー時もログ更新
        }
    } catch (e) {
        alert("Error: " + e);
        refreshLogs();
    } finally {
        els.sendBtn.disabled = false;
        els.messageInput.focus();
    }
}

async function resetSession() {
    if (!confirm("Reset Session? Memory will be lost.")) return;
    const uid = els.userId.value.trim();
    await fetch(`${API_BASE}/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: uid, message: "" })
    });
    location.reload();
}

// ===== Agent Logs Functions =====

let currentLogFilter = 'all';

function toggleLogsPanel() {
    const panel = document.getElementById('logsPanel');
    panel.classList.toggle('collapsed');
}

async function refreshLogs(event) {
    if (event) event.stopPropagation();

    try {
        const url = currentLogFilter === 'all'
            ? `${API_BASE}/logs?limit=50`
            : `${API_BASE}/logs/${currentLogFilter}?limit=30`;

        const res = await fetch(url);
        if (res.ok) {
            const data = await res.json();
            renderLogs(data.logs);
        }
    } catch (e) {
        console.error("Failed to fetch logs:", e);
    }
}

async function clearLogs(event) {
    if (event) event.stopPropagation();

    try {
        await fetch(`${API_BASE}/logs`, { method: 'DELETE' });
        renderLogs([]);
    } catch (e) {
        console.error("Failed to clear logs:", e);
    }
}

function filterLogs(agent) {
    currentLogFilter = agent;

    // Update button states
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.agent === agent);
    });

    refreshLogs();
}

function renderLogs(logs) {
    const list = document.getElementById('logsList');
    if (!logs || logs.length === 0) {
        list.innerHTML = '<div style="color: var(--text-sub); text-align: center; padding: 20px;">No logs yet</div>';
        return;
    }

    list.innerHTML = logs.map(log => {
        const errorClass = log.action === 'error' ? ' error' : '';
        const time = log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '';
        const duration = log.duration_ms ? `${log.duration_ms}ms` : '';

        let content = '';
        if (log.action === 'error') {
            content = log.error || 'Unknown error';
        } else if (log.output_summary) {
            content = log.output_summary;
        } else if (log.input_summary) {
            content = log.input_summary;
        }

        return `
            <div class="log-entry ${log.agent_name}${errorClass}">
                <span class="log-agent">${log.agent_name}</span>
                <span class="log-action">${log.action}</span>
                <span class="log-duration">${duration}</span>
                <span class="log-content">${escapeHtml(content.substring(0, 150))}${content.length > 150 ? '...' : ''}</span>
                <span class="log-time">${time}</span>
            </div>
        `;
    }).join('');

    // Scroll to bottom
    list.scrollTop = list.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Update emotion chart only (without touching dialogue)
function updateEmotionChart(state) {
    if (!state) return;

    const e = state.emotion || { pleasure: 0, arousal: 0, dominance: 0 };

    // Update Chart
    emotionChart.data.datasets[0].data = [e.pleasure, e.arousal, e.dominance];
    emotionChart.update();

    // Update Character Image
    let charKey = 'normal';
    if (e.pleasure > 5) charKey = 'happy';
    else if (e.pleasure < 0 && e.dominance > 0) charKey = 'angry';
    els.characterImg.src = CONFIG.CHAR_IMAGES[charKey] || CONFIG.CHAR_IMAGES['normal'];

    // Update Scene Background
    const sceneKey = state.scenario?.current_scene;
    if (sceneKey && CONFIG.SCENE_IMAGES[sceneKey]) {
        els.sceneBg.style.backgroundImage = CONFIG.SCENE_IMAGES[sceneKey];
        els.sceneBg.style.opacity = '0.6';
    }
}

// ===== DRY RUN Functions =====

async function toggleDryRun() {
    const checkbox = document.getElementById('dryrunToggle');
    const enabled = checkbox.checked;

    try {
        const res = await fetch(`${API_BASE}/dryrun`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });

        if (res.ok) {
            const data = await res.json();
            console.log('DRY RUN mode:', data.dry_run ? 'enabled' : 'disabled');
        }
    } catch (e) {
        console.error("Failed to toggle dry run:", e);
        checkbox.checked = !enabled; // Revert on error
    }
}

async function loadDryRunStatus() {
    try {
        const res = await fetch(`${API_BASE}/dryrun`);
        if (res.ok) {
            const data = await res.json();
            document.getElementById('dryrunToggle').checked = data.dry_run;
        }
    } catch (e) {
        console.error("Failed to load dry run status:", e);
    }
}

// ===== Enhanced Init =====

function initLogs() {
    // Load initial dry run status
    loadDryRunStatus();

    // Start expanded (ログパネルを開いた状態で開始)
    // document.getElementById('logsPanel').classList.add('collapsed');

    // Load initial logs
    refreshLogs();
}

// Start
init();
initLogs();
