// ── State ──────────────────────────────────────────────────────────────────
const state = {
  sessionId: null,
  selectedAgent: '',
  messages: [],       // {role, content, taskId, status}
  pollInterval: null,
  pendingTaskId: null,
  agents: {},
  status: {},
  boardTab: 'internal', // 'internal' | 'external'
};

// ── API ────────────────────────────────────────────────────────────────────
const api = {
  async get(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) return res.json();
    return res.text();
  },
  async post(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(errText || `POST ${path} → ${res.status}`);
    }
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) return res.json();
    return res.text();
  },
  async put(path, body) {
    const res = await fetch(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`PUT ${path} → ${res.status}`);
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) return res.json();
    return res.text();
  },
  async del(path) {
    const res = await fetch(path, { method: 'DELETE' });
    if (!res.ok) throw new Error(`DELETE ${path} → ${res.status}`);
    return res.json();
  },
};

// ── Helpers ────────────────────────────────────────────────────────────────
function sanitizeHtml(html) {
  return html.replace(/<script[\s\S]*?<\/script>/gi, '');
}

function renderMarkdown(text) {
  if (!text) return '';
  try {
    return sanitizeHtml(marked.parse(text));
  } catch (e) {
    return `<pre>${escapeHtml(text)}</pre>`;
  }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(ts) {
  if (!ts) return '';
  const d = new Date(typeof ts === 'number' && ts < 2e10 ? ts * 1000 : ts);
  return d.toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function tierLabel(tier) {
  const map = { executive: 'Executive', 'c-suite': 'C-Suite', specialist: 'Specialist', external: 'External' };
  return map[tier] || tier;
}

function stopPolling() {
  if (state.pollInterval) {
    clearInterval(state.pollInterval);
    state.pollInterval = null;
  }
  const input = document.getElementById('chat-input');
  if (input) input.classList.remove('thinking');
}

function downloadText(filename, content) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Router ─────────────────────────────────────────────────────────────────
function navigate(page) {
  const validPages = ['board', 'chat', 'prompts', 'trace'];
  if (!validPages.includes(page)) page = 'board';

  document.querySelectorAll('.nav-link').forEach(link => {
    link.classList.toggle('active', link.dataset.page === page);
  });

  stopPolling();

  const main = document.getElementById('main');
  main.innerHTML = '<div class="empty-state"><div class="spinner"></div></div>';

  switch (page) {
    case 'board':   renderBoard();   break;
    case 'chat':    renderChat();    break;
    case 'prompts': renderPrompts(); break;
    case 'trace':   renderTrace();   break;
  }
}

window.addEventListener('hashchange', () => navigate(location.hash.slice(1) || 'board'));

// ── Views ──────────────────────────────────────────────────────────────────

// ── BOARD VIEW ─────────────────────────────────────────────────────────────
async function renderBoard() {
  const main = document.getElementById('main');

  let workspaceFiles = [];
  let briefings = [];
  try { workspaceFiles = await api.get('/api/workspace'); } catch(e) {}
  try { briefings = await api.get('/api/briefings?limit=5'); } catch(e) {}

  const agents = state.agents;
  const tab = state.boardTab;

  const internalTiers = ['executive', 'c-suite', 'specialist'];
  const filteredAgents = Object.entries(agents).filter(([, meta]) =>
    tab === 'internal' ? internalTiers.includes(meta.tier) : meta.tier === 'external'
  );

  function agentCards() {
    if (!filteredAgents.length) return '<p class="text-muted text-sm">Keine Agenten.</p>';
    return filteredAgents.map(([key, meta]) => `
      <div class="agent-card">
        <div class="agent-card-header">
          <span class="tier-dot tier-${meta.tier}"></span>
          <span class="agent-card-title">${escapeHtml(meta.label)}</span>
          <span class="text-xs text-muted" style="margin-left:auto">${tierLabel(meta.tier)}</span>
        </div>
        <div class="agent-card-desc">${escapeHtml(meta.desc)}</div>
        <div class="tools-row">
          ${meta.tools.map(t => `<span class="tool-badge">${escapeHtml(t)}</span>`).join('')}
        </div>
        <button class="btn btn-sm mt-2" onclick="chatWithAgent('${key}')">Mit ${escapeHtml(meta.label)} chatten</button>
      </div>
    `).join('');
  }

  function workspaceSection() {
    if (!workspaceFiles.length) return '<div class="empty-state">Keine Dateien im Workspace</div>';
    return workspaceFiles.map(f => `
      <div class="file-row">
        <span class="file-name">${escapeHtml(f.filename)}</span>
        <span class="file-size">${formatSize(f.size)}</span>
        <button class="btn btn-sm" onclick="viewWorkspaceFile('${escapeHtml(f.filename)}')">Lesen</button>
        <button class="btn btn-sm" onclick="downloadWorkspaceFile('${escapeHtml(f.filename)}')">↓</button>
        <button class="btn btn-sm btn-danger" onclick="deleteWorkspaceFile('${escapeHtml(f.filename)}')">✕</button>
      </div>
    `).join('');
  }

  function briefingsSection() {
    if (!briefings.length) return '<div class="empty-state">Keine Board-Briefings vorhanden</div>';
    return briefings.map(b => {
      // actions is a dict: { agent_name: task_text, ... }
      const actions = b.actions && typeof b.actions === 'object' ? Object.entries(b.actions) : [];
      const rationale = b.rationale || '';
      const decision = b.decision || 'Board-Briefing';
      const createdAt = b.created_at ? `<span class="text-xs text-muted">${formatDate(b.created_at)}</span>` : '';
      return `
        <div class="briefing-card">
          <div class="briefing-header">
            <div>
              <div class="briefing-title">${escapeHtml(decision)}</div>
              ${createdAt}
            </div>
            <button class="btn btn-sm btn-danger" onclick="deleteBriefing('${escapeHtml(b.id)}')">✕</button>
          </div>
          ${rationale ? `<div class="briefing-excerpt">${escapeHtml(rationale.substring(0, 220))}${rationale.length > 220 ? '…' : ''}</div>` : ''}
          ${actions.length ? `
            <div class="briefing-actions">
              ${actions.map(([agentKey, taskText]) => {
                const agentMeta = state.agents[agentKey];
                const label = agentMeta ? agentMeta.label : agentKey;
                return `<button class="btn btn-sm" onclick="dispatchBriefingAction('${escapeHtml(agentKey)}', ${JSON.stringify(String(taskText))})">
                  ${escapeHtml(label)}
                </button>`;
              }).join('')}
            </div>
          ` : ''}
        </div>
      `;
    }).join('');
  }

  // Org tree — internal hierarchy
  function orgTree() {
    if (tab !== 'internal') return '';
    const cSuiteKeys = ['cfo','coo','cmo','cso','cdo','cto'];
    const specialistKeys = ['legal','hr','ir','customer_success'];
    function node(key, cls) {
      const m = agents[key];
      if (!m) return '';
      return `<div class="org-node ${cls}" onclick="chatWithAgent('${key}')" title="${escapeHtml(m.desc)}">${escapeHtml(m.label)}</div>`;
    }
    return `
      <div class="org-tree mb-6">
        <div class="org-tier">${node('ceo', 'tier-executive-node')}</div>
        <div class="org-connector-v"></div>
        <div class="org-tier" style="position:relative;">
          <div style="position:absolute;top:0;left:12%;right:12%;height:2px;background:#1e2235;"></div>
          ${cSuiteKeys.map(k => `
            <div class="org-node-wrap">
              <div class="org-connector-v"></div>
              ${node(k, 'tier-csuite-node')}
            </div>
          `).join('')}
        </div>
        <div class="org-connector-v"></div>
        <div class="org-tier" style="position:relative;">
          <div style="position:absolute;top:0;left:20%;right:20%;height:2px;background:#1e2235;"></div>
          ${specialistKeys.map(k => `
            <div class="org-node-wrap">
              <div class="org-connector-v"></div>
              ${node(k, 'tier-specialist-node')}
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  main.innerHTML = `
    <div id="board-view">
      <div class="page-title">Agent Board</div>

      <div class="mb-4 flex items-center gap-3">
        <div class="toggle-group">
          <button class="toggle-btn ${tab === 'internal' ? 'active' : ''}" onclick="switchBoardTab('internal')">Internes Board</button>
          <button class="toggle-btn ${tab === 'external' ? 'active' : ''}" onclick="switchBoardTab('external')">Externe Agenten</button>
        </div>
        <div class="flex items-center gap-2" style="margin-left:auto">
          <span class="status-dot ${state.status.worker_alive ? 'status-online' : 'status-offline'}"></span>
          <span class="status-label">Worker ${state.status.worker_alive ? 'online' : 'offline'}</span>
        </div>
      </div>

      ${orgTree()}

      <div class="agents-grid mb-6">${agentCards()}</div>

      <hr class="divider" />

      <div class="mb-4">
        <div class="flex items-center gap-3 mb-3">
          <span class="section-label">Workspace Dateien</span>
          <button class="btn btn-sm btn-ghost" onclick="cleanupWorkspace()" style="margin-left:auto">Aufräumen</button>
        </div>
        <div class="files-card">${workspaceSection()}</div>
      </div>

      <hr class="divider" />

      <div>
        <div class="section-label mb-3">Board Briefings</div>
        ${briefingsSection()}
      </div>
    </div>
  `;
}

window.switchBoardTab = function(tab) {
  state.boardTab = tab;
  renderBoard();
};

window.chatWithAgent = function(agentKey) {
  state.selectedAgent = agentKey;
  location.hash = '#chat';
};

window.viewWorkspaceFile = async function(filename) {
  try {
    const content = await api.get(`/api/workspace/${encodeURIComponent(filename)}`);
    const modal = document.createElement('div');
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:1000;display:flex;align-items:center;justify-content:center;';
    modal.innerHTML = `
      <div style="background:#111320;border:1px solid #1e2235;border-radius:12px;padding:20px;max-width:800px;width:90%;max-height:80vh;display:flex;flex-direction:column;gap:12px;">
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <span style="font-family:monospace;color:#4f8ef7;font-size:0.85rem">${escapeHtml(filename)}</span>
          <button class="btn btn-sm" onclick="this.closest('div[style]').remove()">✕</button>
        </div>
        <div style="flex:1;overflow-y:auto;background:#0a0c18;border-radius:6px;padding:12px;">
          <div style="font-size:0.8rem;color:#a8b4d8;">${renderMarkdown(content)}</div>
        </div>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-sm btn-primary" onclick="downloadText('${escapeHtml(filename)}', ${JSON.stringify(content)})">Download</button>
          <button class="btn btn-sm" onclick="this.closest('div[style]').remove()">Schließen</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
  } catch(e) {
    alert('Datei konnte nicht geladen werden: ' + e.message);
  }
};

window.downloadWorkspaceFile = async function(filename) {
  try {
    const content = await api.get(`/api/workspace/${encodeURIComponent(filename)}`);
    downloadText(filename, content);
  } catch(e) {
    alert('Download fehlgeschlagen: ' + e.message);
  }
};

window.deleteWorkspaceFile = async function(filename) {
  if (!confirm(`Datei "${filename}" wirklich löschen?`)) return;
  try {
    await api.del(`/api/workspace/${encodeURIComponent(filename)}`);
    renderBoard();
  } catch(e) {
    alert('Löschen fehlgeschlagen: ' + e.message);
  }
};

window.cleanupWorkspace = async function() {
  try {
    const r = await api.post('/api/workspace/cleanup', {});
    alert(`Aufgeräumt: ${r.deleted} Datei(en) entfernt`);
    renderBoard();
  } catch(e) {
    alert('Aufräumen fehlgeschlagen: ' + e.message);
  }
};

window.dispatchBriefingAction = async function(agentName, taskText) {
  if (!state.sessionId) return alert('Keine aktive Session');
  try {
    await api.post('/api/briefings/action', {
      session_id: state.sessionId,
      agent_name: agentName,
      task_text: taskText,
    });
    location.hash = '#chat';
  } catch(e) {
    alert('Fehler: ' + e.message);
  }
};

window.deleteBriefing = async function(briefingId) {
  if (!confirm('Briefing wirklich löschen?')) return;
  try {
    await api.del(`/api/briefings/${briefingId}`);
    renderBoard();
  } catch(e) {
    alert('Löschen fehlgeschlagen: ' + e.message);
  }
};

// ── CHAT VIEW ──────────────────────────────────────────────────────────────
function renderChat() {
  const main = document.getElementById('main');

  const agentOptions = Object.entries(state.agents)
    .map(([key, meta]) => `<option value="${key}" ${state.selectedAgent === key ? 'selected' : ''}>${escapeHtml(meta.label)} — ${escapeHtml(meta.desc)}</option>`)
    .join('');

  main.innerHTML = `
    <div id="chat-view">
      <div id="chat-toolbar">
        <span class="status-dot ${state.status.worker_alive ? 'status-online' : 'status-offline'}"></span>
        <span class="status-label">Worker ${state.status.worker_alive ? 'online' : 'offline'}</span>
        <span class="text-muted" style="margin:0 6px">|</span>
        <span class="text-xs text-muted">Session: ${escapeHtml((state.sessionId || '').substring(0, 12))}…</span>
        <div style="margin-left:auto;display:flex;gap:8px;">
          <button class="btn btn-sm" onclick="createBoardBriefing()">Board-Briefing erstellen</button>
          <button class="btn btn-sm btn-danger" onclick="newSession()">Neue Session</button>
        </div>
      </div>
      <div id="chat-messages"></div>
      <div id="chat-input-bar">
        <select id="agent-select">
          <option value="">— Orchestrator (automatisch) —</option>
          ${agentOptions}
        </select>
        <div id="chat-input-row">
          <input type="text" id="chat-input" placeholder="Aufgabe eingeben…" autocomplete="off" />
          <button id="send-btn">➤</button>
        </div>
      </div>
    </div>
  `;

  const agentSelect = document.getElementById('agent-select');
  agentSelect.addEventListener('change', () => { state.selectedAgent = agentSelect.value; });

  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  sendBtn.addEventListener('click', sendMessage);

  loadChatHistory();
}

async function loadChatHistory() {
  if (!state.sessionId) return;
  try {
    const tasks = await api.get(`/api/tasks?session_id=${state.sessionId}&limit=30`);
    const container = document.getElementById('chat-messages');
    if (!container) return;
    container.innerHTML = '';
    for (const task of tasks.reverse()) {
      appendUserMessage(task.task_text, task.id);
      if (task.status === 'done' || task.status === 'failed') {
        appendAssistantMessage(task, false);
      } else if (task.status === 'pending' || task.status === 'running') {
        appendAssistantMessage(task, true);
        startPolling(task.id);
      }
    }
    scrollToBottom();
  } catch(e) {
    console.error('loadChatHistory error', e);
  }
}

function appendUserMessage(text, taskId) {
  const container = document.getElementById('chat-messages');
  if (!container) return;
  const div = document.createElement('div');
  div.className = 'msg-user';
  div.dataset.taskId = taskId || '';
  div.textContent = text;
  container.appendChild(div);
}

function appendAssistantMessage(task, isLoading) {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  const existing = container.querySelector(`.msg-assistant[data-task-id="${task.id}"]`);
  if (existing) {
    updateAssistantMessage(existing, task, isLoading);
    return;
  }

  const div = document.createElement('div');
  div.className = 'msg-assistant';
  div.dataset.taskId = task.id;
  updateAssistantMessage(div, task, isLoading);
  container.appendChild(div);
}

function updateAssistantMessage(el, task, isLoading) {
  const agentMeta = task.agent_name ? state.agents[task.agent_name] : null;
  const agentLabel = agentMeta ? agentMeta.label : (task.agent_name || 'Orchestrator');

  let statusBadge = '';
  if (task.status === 'pending') statusBadge = '<span class="inline-badge badge-pending">ausstehend</span>';
  else if (task.status === 'running') statusBadge = '<span class="inline-badge badge-running">läuft</span>';
  else if (task.status === 'done') statusBadge = '<span class="inline-badge badge-done">fertig</span>';
  else if (task.status === 'failed') statusBadge = '<span class="inline-badge badge-failed">fehler</span>';

  let content = '';

  if (isLoading) {
    content = `
      <div class="msg-meta">${escapeHtml(agentLabel)} ${statusBadge}</div>
      <div class="msg-status"><span class="spinner"></span> Verarbeitung läuft…</div>
    `;
  } else {
    const agentsUsed = task.agents_used || (task.agent_name ? [task.agent_name] : []);
    const agentChips = agentsUsed.length
      ? `<div class="agents-used-row">${agentsUsed.map(a => {
          const m = state.agents[a];
          return `<span class="agent-chip">${m ? m.label : a}</span>`;
        }).join('')}</div>`
      : '';

    const resultHtml = task.result_text ? renderMarkdown(task.result_text) : (task.status === 'failed' ? '<span class="text-red">Fehler bei der Ausführung.</span>' : '');

    // Workspace files referenced in task
    const artifacts = task.artifacts || [];
    const fileBlocks = artifacts.map(filename => `
      <div class="file-content-block" data-filename="${escapeHtml(filename)}">
        <div class="file-content-header">
          <span class="file-content-name">${escapeHtml(filename)}</span>
          <button class="btn btn-sm" onclick="downloadAndShowArtifact('${escapeHtml(filename)}', this)">↓ Download</button>
        </div>
        <div class="file-content-body" id="artifact-${escapeHtml(filename).replace(/[^a-z0-9]/gi, '_')}">
          <span class="text-muted text-xs">Klicke Download um Inhalt zu laden</span>
        </div>
      </div>
    `).join('');

    // Tool calls
    let toolCallsHtml = '';
    const toolCalls = task.tool_calls || [];
    if (toolCalls.length) {
      const callItems = toolCalls.map(tc => `
        <details>
          <summary>🔧 ${escapeHtml(tc.tool || tc.name || 'Tool-Aufruf')}</summary>
          <div class="tool-call-body">${escapeHtml(typeof tc.input === 'object' ? JSON.stringify(tc.input, null, 2) : String(tc.input || ''))}</div>
        </details>
      `).join('');
      toolCallsHtml = `<div class="tool-calls-summary">${callItems}</div>`;
    }

    content = `
      <div class="msg-meta">${escapeHtml(agentLabel)} ${statusBadge} <span class="text-xs text-muted">${formatDate(task.completed_at || task.created_at)}</span></div>
      ${agentChips}
      <div>${resultHtml}</div>
      ${fileBlocks}
      ${toolCallsHtml}
    `;
  }

  el.innerHTML = content;

  // Auto-load artifact content
  const artifacts = task.artifacts || [];
  if (!isLoading && artifacts.length) {
    artifacts.forEach(filename => {
      const safeId = `artifact-${filename.replace(/[^a-z0-9]/gi, '_')}`;
      const bodyEl = el.querySelector(`#${safeId}`);
      if (bodyEl) {
        api.get(`/api/workspace/${encodeURIComponent(filename)}`).then(text => {
          bodyEl.innerHTML = renderMarkdown(text);
        }).catch(() => {
          bodyEl.innerHTML = '<span class="text-muted text-xs">Datei nicht gefunden</span>';
        });
      }
    });
  }
}

window.downloadAndShowArtifact = async function(filename, btn) {
  try {
    const content = await api.get(`/api/workspace/${encodeURIComponent(filename)}`);
    downloadText(filename, content);
    const safeId = `artifact-${filename.replace(/[^a-z0-9]/gi, '_')}`;
    const bodyEl = document.getElementById(safeId);
    if (bodyEl) bodyEl.innerHTML = renderMarkdown(content);
  } catch(e) {
    alert('Download fehlgeschlagen: ' + e.message);
  }
};

function scrollToBottom() {
  const container = document.getElementById('chat-messages');
  if (container) container.scrollTop = container.scrollHeight;
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;
  if (!state.sessionId) return alert('Keine aktive Session');

  input.value = '';
  if (sendBtn) sendBtn.disabled = true;

  const agentSelect = document.getElementById('agent-select');
  const agentName = (agentSelect ? agentSelect.value : '') || state.selectedAgent || '';

  // Optimistic user message
  appendUserMessage(text, null);
  scrollToBottom();

  try {
    const result = await api.post('/api/tasks', {
      task_text: text,
      session_id: state.sessionId,
      agent_name: agentName,
    });
    const taskId = result.id;
    state.pendingTaskId = taskId;

    // Update user message with taskId
    const userMsgs = document.querySelectorAll('.msg-user');
    const last = userMsgs[userMsgs.length - 1];
    if (last && !last.dataset.taskId) last.dataset.taskId = taskId;

    appendAssistantMessage({ id: taskId, agent_name: agentName, status: 'pending', agents_used: [], artifacts: [], tool_calls: [] }, true);
    scrollToBottom();
    startPolling(taskId);
  } catch(e) {
    const container = document.getElementById('chat-messages');
    if (container) {
      const errDiv = document.createElement('div');
      errDiv.className = 'msg-assistant';
      errDiv.innerHTML = `<span class="text-red">Fehler: ${escapeHtml(e.message)}</span>`;
      container.appendChild(errDiv);
      scrollToBottom();
    }
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    if (input) input.focus();
  }
}

function startPolling(taskId) {
  stopPolling();
  const input = document.getElementById('chat-input');
  if (input) input.classList.add('thinking');

  state.pollInterval = setInterval(async () => {
    try {
      const task = await api.get(`/api/tasks/${taskId}`);
      const el = document.querySelector(`.msg-assistant[data-task-id="${taskId}"]`);
      if (!el) { stopPolling(); return; }

      if (task.status === 'done' || task.status === 'failed') {
        stopPolling();
        updateAssistantMessage(el, task, false);
        scrollToBottom();
        // Refresh status
        try { state.status = await api.get('/api/status'); } catch(e) {}
      } else {
        updateAssistantMessage(el, task, true);
      }
    } catch(e) {
      console.error('polling error', e);
    }
  }, 2000);
}

window.newSession = async function() {
  if (!confirm('Neue Session starten? Der aktuelle Chat wird nicht gelöscht, aber du startest eine neue Session.')) return;
  try {
    const r = await api.post('/api/sessions', { label: 'Neue Session' });
    state.sessionId = r.session_id;
    state.messages = [];
    renderChat();
  } catch(e) {
    alert('Fehler: ' + e.message);
  }
};

window.createBoardBriefing = async function() {
  try {
    const b = await api.post('/api/briefings/create', { session_id: state.sessionId });
    alert('Board-Briefing erstellt: ' + (b.decision || 'OK'));
  } catch(e) {
    alert('Fehler: ' + e.message);
  }
};

// ── PROMPTS VIEW ───────────────────────────────────────────────────────────
async function renderPrompts() {
  const main = document.getElementById('main');

  let context = {};
  try { context = await api.get('/api/context'); } catch(e) {}

  const allAgents = [
    { key: 'orchestrator', label: 'Orchestrator', tier: 'system' },
    ...Object.entries(state.agents).map(([key, meta]) => ({ key, label: meta.label, tier: meta.tier })),
  ];

  const promptItems = allAgents.map(a => `
    <div class="prompt-item" id="prompt-item-${a.key}">
      <div class="prompt-header" onclick="togglePrompt('${a.key}')">
        <span class="prompt-title">${escapeHtml(a.label)}</span>
        <span class="text-xs text-muted">${a.tier}</span>
        <span style="margin-left:8px;color:#4a5568">▾</span>
      </div>
      <div class="prompt-body" id="prompt-body-${a.key}">
        <div id="prompt-content-${a.key}"><span class="text-muted text-xs">Wird geladen…</span></div>
        <div style="display:flex;gap:8px;margin-top:8px;" id="prompt-actions-${a.key}">
          <button class="btn btn-sm btn-primary" onclick="editPrompt('${a.key}')">Bearbeiten</button>
        </div>
      </div>
    </div>
  `).join('');

  const contextJson = JSON.stringify(context, null, 2);

  main.innerHTML = `
    <div id="prompts-view">
      <div class="page-title">Prompts & Kontext</div>

      <div class="section-label mb-3">System-Prompts</div>
      <div class="mb-6">${promptItems}</div>

      <hr class="divider" />

      <div class="section-label mb-3">Unternehmenskontext</div>
      <div class="card" id="context-card">
        <div id="context-view">
          <pre style="font-size:0.78rem;color:#a8b4d8;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow-y:auto;">${escapeHtml(contextJson)}</pre>
          <div style="margin-top:10px;">
            <button class="btn btn-sm btn-primary" onclick="editContext()">Bearbeiten</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

window.togglePrompt = async function(key) {
  const body = document.getElementById(`prompt-body-${key}`);
  if (!body) return;
  const isOpen = body.classList.contains('open');
  if (!isOpen) {
    body.classList.add('open');
    const contentEl = document.getElementById(`prompt-content-${key}`);
    if (contentEl && contentEl.querySelector('.text-muted')) {
      try {
        const text = await api.get(`/api/prompts/${key}`);
        contentEl.innerHTML = `<div class="prompt-content-pre">${escapeHtml(text)}</div>`;
      } catch(e) {
        contentEl.innerHTML = `<span class="text-muted text-xs">Prompt nicht gefunden</span>`;
      }
    }
  } else {
    body.classList.remove('open');
  }
};

window.editPrompt = async function(key) {
  const contentEl = document.getElementById(`prompt-content-${key}`);
  const actionsEl = document.getElementById(`prompt-actions-${key}`);
  if (!contentEl || !actionsEl) return;

  let currentText = '';
  try {
    currentText = await api.get(`/api/prompts/${key}`);
  } catch(e) {}

  contentEl.innerHTML = `<textarea class="context-editor w-full" id="prompt-textarea-${key}" style="min-height:200px;">${escapeHtml(currentText)}</textarea>`;
  actionsEl.innerHTML = `
    <button class="btn btn-sm btn-primary" onclick="savePrompt('${key}')">Speichern</button>
    <button class="btn btn-sm" onclick="cancelEditPrompt('${key}', ${JSON.stringify(escapeHtml(currentText))})">Abbrechen</button>
  `;
};

window.savePrompt = async function(key) {
  const ta = document.getElementById(`prompt-textarea-${key}`);
  if (!ta) return;
  try {
    await api.put(`/api/prompts/${key}`, { content: ta.value });
    const contentEl = document.getElementById(`prompt-content-${key}`);
    const actionsEl = document.getElementById(`prompt-actions-${key}`);
    if (contentEl) contentEl.innerHTML = `<div class="prompt-content-pre">${escapeHtml(ta.value)}</div>`;
    if (actionsEl) actionsEl.innerHTML = `<button class="btn btn-sm btn-primary" onclick="editPrompt('${key}')">Bearbeiten</button>`;
  } catch(e) {
    alert('Fehler beim Speichern: ' + e.message);
  }
};

window.cancelEditPrompt = function(key, originalText) {
  const contentEl = document.getElementById(`prompt-content-${key}`);
  const actionsEl = document.getElementById(`prompt-actions-${key}`);
  if (contentEl) contentEl.innerHTML = `<div class="prompt-content-pre">${escapeHtml(originalText)}</div>`;
  if (actionsEl) actionsEl.innerHTML = `<button class="btn btn-sm btn-primary" onclick="editPrompt('${key}')">Bearbeiten</button>`;
};

window.editContext = async function() {
  let current = {};
  try { current = await api.get('/api/context'); } catch(e) {}
  const currentJson = JSON.stringify(current, null, 2);

  const card = document.getElementById('context-card');
  if (!card) return;
  card.innerHTML = `
    <div>
      <textarea class="context-editor w-full" id="context-textarea" style="min-height:300px;">${escapeHtml(currentJson)}</textarea>
      <div style="margin-top:10px;display:flex;gap:8px;">
        <button class="btn btn-sm btn-primary" onclick="saveContext()">Speichern</button>
        <button class="btn btn-sm" onclick="cancelEditContext(${JSON.stringify(escapeHtml(currentJson))})">Abbrechen</button>
      </div>
    </div>
  `;
};

window.saveContext = async function() {
  const ta = document.getElementById('context-textarea');
  if (!ta) return;
  try {
    const parsed = JSON.parse(ta.value);
    await api.put('/api/context', { data: parsed });
    const card = document.getElementById('context-card');
    if (card) card.innerHTML = `
      <div id="context-view">
        <pre style="font-size:0.78rem;color:#a8b4d8;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow-y:auto;">${escapeHtml(JSON.stringify(parsed, null, 2))}</pre>
        <div style="margin-top:10px;"><button class="btn btn-sm btn-primary" onclick="editContext()">Bearbeiten</button></div>
      </div>
    `;
  } catch(e) {
    alert('Ungültiges JSON oder Speicherfehler: ' + e.message);
  }
};

window.cancelEditContext = function(originalJson) {
  const card = document.getElementById('context-card');
  if (!card) return;
  card.innerHTML = `
    <div id="context-view">
      <pre style="font-size:0.78rem;color:#a8b4d8;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow-y:auto;">${escapeHtml(originalJson)}</pre>
      <div style="margin-top:10px;"><button class="btn btn-sm btn-primary" onclick="editContext()">Bearbeiten</button></div>
    </div>
  `;
};

// ── TRACE VIEW ─────────────────────────────────────────────────────────────
async function renderTrace() {
  const main = document.getElementById('main');

  let tasks = [];
  try {
    if (state.sessionId) tasks = await api.get(`/api/tasks?session_id=${state.sessionId}&limit=5`);
  } catch(e) {}

  if (!tasks.length) {
    main.innerHTML = `
      <div id="trace-view">
        <div class="page-title">Denkfluss</div>
        <div class="empty-state">Noch keine Tasks in dieser Session</div>
      </div>
    `;
    return;
  }

  const lastTask = tasks[0];
  const toolCalls = lastTask.tool_calls || [];
  const agentsUsed = lastTask.agents_used || (lastTask.agent_name ? [lastTask.agent_name] : []);

  // Build flow steps from tool calls and agents
  const flowSteps = [];

  // Start with task input
  flowSteps.push({ label: 'Aufgabe', type: 'input' });

  // Add agents involved
  agentsUsed.forEach(a => {
    const m = state.agents[a];
    flowSteps.push({ label: m ? m.label : a, type: 'agent' });
  });

  // Add tool calls as steps
  const uniqueTools = [...new Set(toolCalls.map(tc => tc.tool || tc.name || 'Tool'))];
  uniqueTools.forEach(t => {
    flowSteps.push({ label: t, type: 'tool' });
  });

  flowSteps.push({ label: 'Ergebnis', type: 'output' });

  function stepColor(type) {
    if (type === 'input') return '#4f8ef7';
    if (type === 'agent') return '#7c6af7';
    if (type === 'tool') return '#34d399';
    if (type === 'output') return '#34d399';
    return '#4a5568';
  }

  const flowHtml = flowSteps.map((step, i) => `
    ${i > 0 ? '<span class="trace-arrow">→</span>' : ''}
    <div class="trace-step" style="border-color:${stepColor(step.type)};color:${stepColor(step.type)}">
      ${escapeHtml(step.label)}
    </div>
  `).join('');

  // Detail steps
  const detailsHtml = toolCalls.length ? toolCalls.map((tc, i) => `
    <div class="trace-step-detail">
      <div class="trace-step-name">Schritt ${i + 1}: ${escapeHtml(tc.tool || tc.name || 'Tool-Aufruf')}</div>
      <div class="trace-step-content">${escapeHtml(typeof tc.input === 'object' ? JSON.stringify(tc.input, null, 2) : String(tc.input || ''))}</div>
      ${tc.output ? `<div class="trace-step-content" style="margin-top:6px;color:#34d399;">${escapeHtml(typeof tc.output === 'object' ? JSON.stringify(tc.output, null, 2) : String(tc.output).substring(0, 400))}</div>` : ''}
    </div>
  `).join('') : '<div class="empty-state">Keine Tool-Aufrufe in diesem Task</div>';

  main.innerHTML = `
    <div id="trace-view">
      <div class="page-title">Denkfluss</div>
      <div class="section-label mb-3">Letzter Task: ${escapeHtml((lastTask.task_text || '').substring(0, 60))}${(lastTask.task_text || '').length > 60 ? '…' : ''}</div>

      <div class="trace-flow mb-6">
        ${flowHtml}
      </div>

      <div class="section-label mb-3">Tool-Aufrufe</div>
      ${detailsHtml}
    </div>
  `;
}

// ── Init ───────────────────────────────────────────────────────────────────
async function init() {
  try {
    state.agents = await api.get('/api/agents');
  } catch(e) {
    console.error('Agents laden fehlgeschlagen', e);
    state.agents = {};
  }

  try {
    state.status = await api.get('/api/status');
  } catch(e) {
    state.status = { worker_alive: false };
  }

  try {
    const s = await api.get('/api/sessions/latest');
    state.sessionId = s.session_id;
  } catch(e) {
    console.error('Session laden fehlgeschlagen', e);
  }

  navigate(location.hash.slice(1) || 'board');

  // Periodically refresh status
  setInterval(async () => {
    try { state.status = await api.get('/api/status'); } catch(e) {}
  }, 30000);
}

init();
