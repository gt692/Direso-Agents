"""
pages/chat.py — Chat mit Task-Queue-Backend.

Tasks werden in SQLite eingestellt und vom Worker-Prozess ausgeführt.
Der Browser kann geschlossen werden — der Worker arbeitet weiter.
"""
from __future__ import annotations

import json
import time

import streamlit as st

from memory.store import store
from orchestrator.orchestrator import orchestrator
from ui.common import (
    AGENT_META, ALL_AGENTS,
    inject_css, init_session_state, render_topbar, section_label,
    tier_color,
)
from config import settings

st.set_page_config(page_title="Chat — DIRESO", page_icon="💬", layout="wide")
inject_css()
st.markdown("""
<style>
[data-testid="stAppViewBlockContainer"] { padding-top: 1rem !important; }

/* ── Chat-Input: statischer Rahmen, kein Pulsieren ───────────────────────── */
[data-testid="stChatInput"] textarea {
    border-color: #ef4444 !important;
}
/* AI denkt nach — etwas stärkerer roter Rahmen als Indikator */
body.ai-thinking [data-testid="stChatInput"] textarea {
    border-color: #ef4444 !important;
    box-shadow: 0 0 0 2px rgba(239,68,68,0.18) !important;
}

/* ── Chat-Avatar Weißfleck entfernen ─────────────────────────────────────── */
[data-testid="stChatMessage"] > div:first-child,
[data-testid="stChatMessage"] [data-testid*="avatar"],
[data-testid="stChatMessage"] [data-testid*="Avatar"] {
    background: transparent !important;
    background-color: transparent !important;
}
</style>
""", unsafe_allow_html=True)
init_session_state()
if "tts_enabled" not in st.session_state:
    st.session_state.tts_enabled = False
if "tts_last_spoken_id" not in st.session_state:
    st.session_state.tts_last_spoken_id = None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='padding:16px 0 8px 0'>"
        "<span style='font-size:1.1rem;font-weight:600;color:#e2e8f0'>◈ DIRESO</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    section_label("Routing")
    agent_options = ["Auto — Orchestrator"] + [
        f"{AGENT_META[a]['label']} — {AGENT_META[a]['desc']}" for a in ALL_AGENTS
    ]
    _pre = st.session_state.selected_agent
    _default = (ALL_AGENTS.index(_pre) + 1) if _pre in ALL_AGENTS else 0
    selected_idx = st.selectbox(
        "Agent",
        options=range(len(agent_options)),
        index=_default,
        format_func=lambda i: agent_options[i],
        label_visibility="collapsed",
    )
    selected_agent = None if selected_idx == 0 else ALL_AGENTS[selected_idx - 1]
    st.session_state.selected_agent = selected_agent

    if selected_agent:
        meta = AGENT_META[selected_agent]
        tc = tier_color(meta["tier"])
        st.markdown(
            f"<div style='padding:8px 12px;background:#111320;border:1px solid #1e2235;"
            f"border-radius:6px;margin-top:4px'>"
            f"<span style='width:6px;height:6px;border-radius:50%;background:{tc};"
            f"display:inline-block;margin-right:6px'></span>"
            f"<span style='font-size:0.8rem;color:#e2e8f0;font-weight:600'>{meta['label']}</span>"
            f"<div style='font-size:0.72rem;color:#4a5568;margin-top:2px'>{meta['desc']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    section_label("Aktionen")

    if st.button("Board-Briefing erstellen", use_container_width=True):
        tasks = store.get_recent_tasks(st.session_state.session_id, limit=1)
        last_result = tasks[0]["result_text"] if tasks else ""
        if last_result:
            with st.spinner("CEO erstellt Briefing..."):
                briefing = orchestrator.create_board_briefing(
                    last_result, session_id=st.session_state.session_id
                )
            st.success(f"{briefing['decision'][:50]}...")
        else:
            st.warning("Erst eine Aufgabe ausführen.")

    if "confirm_new_session" not in st.session_state:
        st.session_state.confirm_new_session = False

    if not st.session_state.confirm_new_session:
        if st.button("Neue Session", use_container_width=True):
            st.session_state.confirm_new_session = True
            st.rerun()
    else:
        st.warning("Chat-Verlauf wird gelöscht. Sicher?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Ja, löschen", type="primary", use_container_width=True):
                st.session_state.session_id = store.create_session(label="Neue Session")
                st.session_state.last_trace = []
                st.session_state.last_agents_used = []
                st.session_state.pending_task_id = None
                st.session_state.chat_messages = []
                st.session_state.confirm_new_session = False
                st.rerun()
        with c2:
            if st.button("Abbrechen", use_container_width=True):
                st.session_state.confirm_new_session = False
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    section_label("Tool-Status")

    def _pill(label: str, live: bool) -> str:
        cls = "live" if live else "offline"
        return f'<div class="tool-status {cls}">{"●" if live else "○"} {label}</div>'

    st.markdown(
        _pill("Web-Suche", settings.is_search_configured()) +
        _pill("E-Mail", settings.is_email_configured()) +
        _pill("Social Media", settings.is_social_configured()),
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    section_label("Sprache")
    st.session_state.tts_enabled = st.toggle(
        "Sprachausgabe", value=st.session_state.tts_enabled
    )
    st.caption("Mikrofon-Button erscheint neben Eingabefeld. Nur Chrome/Edge.")

    st.markdown("<br>", unsafe_allow_html=True)
    section_label("Worker")
    # Prüfe ob Worker-Prozess läuft (via PID-Datei)
    import os
    from pathlib import Path as _Path
    _pid_file = _Path(__file__).parent.parent / "worker.pid"
    _worker_alive = False
    if _pid_file.exists():
        try:
            _pid = int(_pid_file.read_text().strip())
            os.kill(_pid, 0)  # Kein Signal — nur Existenz-Check
            _worker_alive = True
        except (OSError, ValueError):
            _worker_alive = False
    _worker_dot = "<span style='color:#34d399'>⬤</span> Online" if _worker_alive else "<span style='color:#ef4444'>⬤</span> Offline"
    recent = store.get_recent_tasks(st.session_state.session_id, limit=20)
    n_running = sum(1 for t in recent if t["status"] in ("pending", "running"))
    n_done    = sum(1 for t in recent if t["status"] == "done")
    st.markdown(
        f"<div style='font-size:0.75rem;color:#4a5568;line-height:1.8'>"
        f"{_worker_dot}<br>"
        f"<span style='color:#f59e0b'>⬤</span> {n_running} laufend &nbsp; "
        f"<span style='color:#34d399'>⬤</span> {n_done} abgeschlossen</div>",
        unsafe_allow_html=True,
    )

# ── Hauptbereich: Chat ────────────────────────────────────────────────────────
tasks_all = store.get_recent_tasks(st.session_state.session_id, limit=30)
tasks_by_id = {t["id"]: t for t in tasks_all}

# Chat-Verlauf aus DB wiederherstellen wenn session_state leer aber Tasks vorhanden
if not st.session_state.chat_messages and tasks_all:
    restored = []
    for task in reversed(tasks_all):
        restored.append({"role": "user", "content": task["task_text"]})
        restored.append({"role": "assistant", "task_id": task["id"], "content": ""})
    st.session_state.chat_messages = restored

# Nachrichten rendern
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            task_id = msg.get("task_id")
            task = tasks_by_id.get(task_id) if task_id else None

            if task and task["status"] in ("pending", "running"):
                st.markdown(
                    "<div class='task-running'>"
                    "<span style='color:#4f8ef7;font-size:0.8rem'>⟳ Agent arbeitet im Hintergrund...</span><br>"
                    "<span style='color:#2d3665;font-size:0.72rem'>Du kannst den Browser schließen — der Task läuft weiter.</span>"
                    "</div>",
                    unsafe_allow_html=True,
                )
            elif task and task["status"] == "done":
                agents = task.get("agents_used", [])
                if agents:
                    chain = " → ".join(
                        f"<span style='color:#4f8ef7;font-weight:600'>{a.upper()}</span>"
                        for a in agents
                    )
                    st.markdown(f"<div style='font-size:0.72rem;color:#2d3665;margin-bottom:10px'>{chain}</div>", unsafe_allow_html=True)

                # Workspace-Dateien direkt anzeigen (haben die echte Analyse)
                ws_files = task.get("workspace_files", [])
                if ws_files:
                    for filename in ws_files:
                        fp = settings.workspace_dir / filename
                        # Glob-Fallback: Datei mit Datumspräfix suchen
                        if not fp.exists():
                            matches = sorted(
                                settings.workspace_dir.glob(f"*{filename}"),
                                key=lambda p: p.stat().st_mtime,
                                reverse=True,
                            )
                            fp = matches[0] if matches else fp
                        if fp.exists():
                            content = fp.read_text(encoding="utf-8")
                            actual_name = fp.name
                            col_name, col_dl = st.columns([5, 1])
                            with col_name:
                                st.markdown(
                                    f"<div style='font-size:0.72rem;color:#34d399;margin-bottom:6px'>"
                                    f"📄 {actual_name}</div>",
                                    unsafe_allow_html=True,
                                )
                            with col_dl:
                                st.download_button(
                                    "↓",
                                    data=content,
                                    file_name=actual_name,
                                    mime="text/markdown",
                                    key=f"chat_dl_{task['id']}_{filename}",
                                )
                            st.markdown(content)
                            st.markdown("---")
                        else:
                            st.markdown(task["result_text"])
                else:
                    # Keine Datei — direkte Antwort anzeigen
                    st.markdown(task["result_text"])

                # Tool-Calls eingeklappt
                if task.get("tool_calls"):
                    with st.expander(f"🔧 {len(task['tool_calls'])} Tool-Call(s) — Details"):
                        for tc in task["tool_calls"]:
                            inp = json.dumps(tc.get("input", {}), ensure_ascii=False)[:80]
                            out = tc.get("output", "")[:200]
                            st.markdown(
                                f"<div style='background:#0a0c14;border:1px solid #1e2235;border-radius:6px;"
                                f"padding:8px 12px;margin-bottom:6px;font-family:monospace;font-size:0.75rem'>"
                                f"<span style='color:#4f8ef7'>{tc['tool']}</span>"
                                f"<span style='color:#4a5568'>({inp})</span><br>"
                                f"<span style='color:#6af7c8'>→</span> "
                                f"<span style='color:#94a3b8'>{out}</span>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )
            elif task and task["status"] == "failed":
                st.markdown(f"<div class='task-failed'>✗ Fehler: {task.get('error','')[:100]}</div>", unsafe_allow_html=True)
            else:
                st.markdown(msg.get("content", ""))
        else:
            st.markdown(msg["content"])

# ── AI Thinking state merken für kombinierten Component ──────────────────────
_is_thinking = bool(st.session_state.pending_task_id)

# Polling für laufende Tasks + Auto-Recover falls Task already done
if st.session_state.pending_task_id:
    task = store.get_task(st.session_state.pending_task_id)
    if task and task["status"] in ("pending", "running"):
        time.sleep(2)
        st.rerun()
    elif task and task["status"] in ("done", "failed"):
        st.session_state.last_agents_used = task.get("agents_used", [])
        st.session_state.last_trace = task.get("trace", [])
        st.session_state.pending_task_id = None
        st.rerun()
else:
    # Prüfe ob es noch unangezeigte done-Tasks gibt (z.B. nach Tab-Inaktivität)
    for msg in st.session_state.chat_messages:
        if msg.get("task_id"):
            t = tasks_by_id.get(msg["task_id"])
            if t and t["status"] == "done" and msg.get("content") == "":
                msg["content"] = "shown"  # markieren damit kein Loop
                st.rerun()

# ── TTS: letzten Text für kombinierten Component vorbereiten ─────────────────
_tts_json = "null"
if st.session_state.tts_enabled:
    last_done = next(
        (tasks_by_id[m["task_id"]] for m in reversed(st.session_state.chat_messages)
         if m.get("task_id") and tasks_by_id.get(m["task_id"], {}).get("status") == "done"),
        None,
    )
    if last_done and last_done["id"] != st.session_state.tts_last_spoken_id:
        st.session_state.tts_last_spoken_id = last_done["id"]
        _tts_json = json.dumps(last_done["result_text"][:1500])

# ── Kombinierter Component: AI-Klasse + TTS + Mikrofon ───────────────────────
# Ein einziger iframe statt drei — kein weißer Fleck mehr neben dem Input.
st.components.v1.html(f"""
<style>
html, body {{ background: transparent !important; margin: 0; padding: 0; overflow: hidden; }}
#mic-btn {{
    position: fixed; bottom: 22px; right: 22px;
    width: 48px; height: 48px; border-radius: 50%;
    background: #1e2235; border: 1.5px solid #4f8ef7;
    color: #4f8ef7; font-size: 20px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    z-index: 9999; transition: all 0.2s;
    box-shadow: 0 2px 12px rgba(79,142,247,0.15);
}}
#mic-btn:hover {{ background: #141f35; }}
#mic-btn.listening {{
    background: #2d0f0f; border-color: #ef4444; color: #ef4444;
    animation: pulse 1s infinite;
}}
@keyframes pulse {{
    0%   {{ box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }}
    70%  {{ box-shadow: 0 0 0 10px rgba(239,68,68,0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(239,68,68,0); }}
}}
#mic-status {{
    position: fixed; bottom: 76px; right: 16px;
    font-size: 11px; color: #4a5568; background: #0d0f1a;
    padding: 3px 8px; border-radius: 10px;
    border: 1px solid #1e2235; display: none; z-index: 9999;
}}
</style>
<button id="mic-btn" title="Spracheingabe (Chrome/Edge)">🎤</button>
<div id="mic-status">Höre zu...</div>
<script>
(function() {{
    var doc = window.parent.document;

    // AI-Thinking-Klasse
    if ({'true' if _is_thinking else 'false'}) {{
        doc.body.classList.add('ai-thinking');
    }} else {{
        doc.body.classList.remove('ai-thinking');
    }}

    // TTS
    var ttsText = {_tts_json};
    if (ttsText && window.speechSynthesis) {{
        window.speechSynthesis.cancel();
        var u = new SpeechSynthesisUtterance(ttsText);
        u.lang = 'de-DE'; u.rate = 1.05; u.pitch = 1.0;
        var voices = window.speechSynthesis.getVoices();
        var deVoice = voices.find(function(v) {{ return v.lang.startsWith('de'); }});
        if (deVoice) u.voice = deVoice;
        window.speechSynthesis.speak(u);
    }}

    // Mikrofon
    var btn = document.getElementById('mic-btn');
    var status = document.getElementById('mic-status');
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {{ btn.style.opacity = '0.3'; btn.title = 'Nur Chrome/Edge'; return; }}
    var recognition = new SR();
    recognition.lang = 'de-DE'; recognition.continuous = false; recognition.interimResults = false;
    var listening = false;
    btn.addEventListener('click', function() {{ listening ? recognition.stop() : recognition.start(); }});
    recognition.onstart = function() {{ listening = true; btn.classList.add('listening'); btn.textContent = '⏹'; status.style.display = 'block'; }};
    recognition.onend = function() {{ listening = false; btn.classList.remove('listening'); btn.textContent = '🎤'; status.style.display = 'none'; }};
    recognition.onerror = function(e) {{ listening = false; btn.classList.remove('listening'); btn.textContent = '🎤'; status.style.display = 'none'; }};
    recognition.onresult = function(event) {{
        var transcript = event.results[0][0].transcript;
        var textareas = doc.querySelectorAll('textarea');
        for (var i = 0; i < textareas.length; i++) {{
            var ta = textareas[i];
            if (ta.placeholder && ta.placeholder.indexOf('eingeben') !== -1) {{
                Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(ta, transcript);
                ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
                ta.focus(); break;
            }}
        }}
    }};
}})();
</script>
""", height=0)

# ── Chat Input — auf Page-Ebene = sticky am unteren Rand ─────────────────────
if prompt := st.chat_input("Aufgabe eingeben..."):
    st.session_state.chat_messages.append({"role": "user", "content": prompt})

    task_id = store.enqueue_task(
        task_text=prompt,
        session_id=st.session_state.session_id,
        agent_name=selected_agent or "",
    )
    st.session_state.pending_task_id = task_id
    st.session_state.chat_messages.append({
        "role": "assistant",
        "task_id": task_id,
        "content": "",
    })
    st.rerun()
