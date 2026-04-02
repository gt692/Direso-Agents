"""
ui/common.py

Geteilte Komponenten: CSS, Agent-Metadaten, Topbar, Session-State-Init.
Alle Pages importieren dieses Modul.
"""
from __future__ import annotations

import streamlit as st

from config import settings
from memory.store import store

# ── Agent-Metadaten ───────────────────────────────────────────────────────────
AGENT_META: dict[str, dict] = {
    "ceo":              {"label": "CEO",       "desc": "Co-CEO & Strategie",          "tools": ["workspace", "web"],                   "tier": "executive"},
    "cfo":              {"label": "CFO",       "desc": "Finanzen & Fördergelder",      "tools": ["workspace", "web"],                   "tier": "c-suite"},
    "coo":              {"label": "COO",       "desc": "Prozesse & Effizienz",         "tools": ["workspace", "web"],                   "tier": "c-suite"},
    "cmo":              {"label": "CMO",       "desc": "Marketing & Social Media",     "tools": ["workspace", "web", "email", "social"],"tier": "c-suite"},
    "cso":              {"label": "CSO",       "desc": "Sales & CRM",                  "tools": ["workspace", "web", "email"],          "tier": "c-suite"},
    "cdo":              {"label": "CDO",       "desc": "Website & Digital",            "tools": ["workspace", "web", "file", "browser"],"tier": "c-suite"},
    "cto":              {"label": "CTO",       "desc": "Technologie & Code",           "tools": ["workspace", "web", "file"],           "tier": "c-suite"},
    "legal":            {"label": "Legal",     "desc": "DSGVO & Compliance",           "tools": ["workspace", "web"],                   "tier": "specialist"},
    "hr":               {"label": "HR",        "desc": "Personal & Recruiting",        "tools": ["workspace", "web", "email"],          "tier": "specialist"},
    "ir":               {"label": "IR",        "desc": "Investor Relations",           "tools": ["workspace", "web", "email"],          "tier": "specialist"},
    "customer_success": {"label": "CS",        "desc": "Customer Success",             "tools": ["workspace", "web", "email"],          "tier": "specialist"},
    "portfolio_assistant": {"label": "Portfolio", "desc": "Portfolio-Assistent",       "tools": ["workspace", "web"],                   "tier": "external"},
    "report_generator":    {"label": "Reports",   "desc": "Report-Generator",          "tools": ["workspace", "web"],                   "tier": "external"},
}

INTERNAL_AGENTS = ["ceo", "cfo", "coo", "cmo", "cso", "cdo", "cto", "legal", "hr", "ir", "customer_success"]
EXTERNAL_AGENTS = ["portfolio_assistant", "report_generator"]
ALL_AGENTS = INTERNAL_AGENTS + EXTERNAL_AGENTS

TOOL_COLORS = {
    "workspace": "#3d4663",
    "web":       "#2d4a3e",
    "email":     "#3d3040",
    "social":    "#3d4020",
    "file":      "#2d3d50",
    "browser":   "#3d2d20",
}
TOOL_LABELS = {
    "workspace": "workspace",
    "web":       "web search",
    "email":     "e-mail",
    "social":    "social",
    "file":      "file read",
    "browser":   "browser",
}


def tier_color(tier: str) -> str:
    return {
        "executive":  "#4f8ef7",
        "c-suite":    "#7c6af7",
        "specialist": "#6af7c8",
        "external":   "#4a5568",
    }.get(tier, "#4a5568")


def tool_badges_html(tools: list[str]) -> str:
    badges = "".join(
        f'<span class="tool-badge" style="background:{TOOL_COLORS.get(t,"#2d3665")}">'
        f'{TOOL_LABELS.get(t, t)}</span>'
        for t in tools
    )
    return f'<div class="tools">{badges}</div>'


# ── Session State Init ────────────────────────────────────────────────────────
def init_session_state() -> None:
    import json as _json

    if "session_id" not in st.session_state:
        # Session mit dem neuesten Task laden (nicht einfach die letzte Session)
        conn = store._connect()
        row = conn.execute(
            "SELECT session_id FROM tasks ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row and row["session_id"]:
            st.session_state.session_id = row["session_id"]
        else:
            st.session_state.session_id = store.create_session(label="Neue Session")

    if "last_trace" not in st.session_state:
        st.session_state.last_trace = []
    if "last_agents_used" not in st.session_state:
        st.session_state.last_agents_used = []

    # Trace + Agents aus DB wiederherstellen falls leer (z.B. nach Browser-Reload)
    if not st.session_state.last_trace and st.session_state.get("session_id"):
        conn = store._connect()
        row = conn.execute(
            "SELECT trace, agents_used FROM tasks WHERE session_id=? AND status='done' "
            "ORDER BY completed_at DESC LIMIT 1",
            (st.session_state.session_id,),
        ).fetchone()
        conn.close()
        if row:
            try:
                st.session_state.last_trace = _json.loads(row["trace"] or "[]")
                st.session_state.last_agents_used = _json.loads(row["agents_used"] or "[]")
            except Exception:
                pass

    if "board_view" not in st.session_state:
        st.session_state.board_view = "internal"
    if "selected_agent" not in st.session_state:
        st.session_state.selected_agent = None
    if "pending_task_id" not in st.session_state:
        st.session_state.pending_task_id = None
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []


# ── Global CSS ────────────────────────────────────────────────────────────────
DARK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [data-testid="stApp"] {
    background-color: #0d0f1a !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
[data-testid="stHeader"], [data-testid="stSidebarHeader"] { background: transparent !important; }
#MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #080a12 !important;
    border-right: 1px solid #1e2235 !important;
}
[data-testid="stSidebarNav"] a {
    color: #64748b !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    border-radius: 6px !important;
    padding: 6px 12px !important;
}
[data-testid="stSidebarNav"] a:hover { color: #94a3b8 !important; background: #111320 !important; }
[data-testid="stSidebarNav"] a[aria-current="page"] {
    color: #4f8ef7 !important;
    background: #0d1828 !important;
}

/* ── Inputs ───────────────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] > div,
[data-baseweb="select"] > div,
textarea {
    background: #141626 !important;
    border: 1px solid #1e2235 !important;
    color: #ffffff !important;
    border-radius: 6px !important;
}
[data-testid="stTextInput"] input::placeholder,
textarea::placeholder { color: #4a5568 !important; }
[data-baseweb="select"] span, [data-baseweb="select"] div { color: #ffffff !important; }
[data-testid="stChatInput"] textarea {
    background: #141626 !important;
    border: 1px solid #252a40 !important;
    color: #ffffff !important;
    border-radius: 8px !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: #4a5568 !important; }
[data-testid="stChatInput"] textarea:focus { border-color: #4f8ef7 !important; box-shadow: 0 0 0 2px rgba(79,142,247,0.12) !important; }

/* ── Buttons ──────────────────────────────────────────────────────────────── */
[data-testid="stButton"] > button {
    background: #141626 !important;
    border: 1px solid #252a40 !important;
    color: #94a3b8 !important;
    border-radius: 6px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    transition: all 0.15s !important;
}
[data-testid="stButton"] > button:hover { border-color: #4f8ef7 !important; color: #4f8ef7 !important; background: #141f35 !important; }
[data-testid="stButton"] > button[kind="primary"] { background: #4f8ef7 !important; border-color: #4f8ef7 !important; color: #fff !important; }
[data-testid="stButton"] > button[kind="secondary"] { background: #111320 !important; border-color: #1e2235 !important; color: #4a5568 !important; }
[data-testid="stButton"] > button[kind="secondary"]:hover { border-color: #2d3665 !important; color: #94a3b8 !important; }

/* ── Expander ─────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] { border: 1px solid #1e2235 !important; border-radius: 8px !important; background: #111320 !important; }
[data-testid="stExpander"] summary { color: #94a3b8 !important; font-size: 0.85rem !important; background: #111320 !important; }
[data-testid="stExpander"] summary:hover { background: #141626 !important; color: #e2e8f0 !important; }
[data-testid="stExpander"] > div { background: #111320 !important; }
[data-testid="stExpander"] details { background: #111320 !important; }
/* Code innerhalb Expander */
[data-testid="stExpander"] [data-testid="stCode"],
[data-testid="stExpander"] [data-testid="stCode"] > div,
[data-testid="stExpander"] pre { background: #0a0c14 !important; color: #e2e8f0 !important; }

/* ── Code ─────────────────────────────────────────────────────────────────── */
[data-testid="stCode"],
[data-testid="stCode"] > div,
[data-testid="stCode"] pre,
[data-testid="stCode"] code,
.stCode {
    background: #0a0c14 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 6px !important;
    color: #e2e8f0 !important;
}
/* Hover-Stabilisierung — verhindert transparenten Hintergrund */
[data-testid="stCode"]:hover,
[data-testid="stCode"]:hover > div,
[data-testid="stCode"]:hover pre,
[data-testid="stCode"]:hover code,
[data-testid="stCode"] pre:hover,
[data-testid="stCode"] code:hover,
[data-testid="stCode"] div:hover {
    background: #0a0c14 !important;
    background-color: #0a0c14 !important;
    color: #e2e8f0 !important;
}
[data-testid="stCode"] button { background: #1e2235 !important; color: #94a3b8 !important; border: none !important; }
[data-testid="stCode"] button:hover { background: #252a40 !important; color: #e2e8f0 !important; }

/* Markdown-Code-Blöcke (Pygments Syntax-Highlighter) — alle Token-Farben überschreiben */
[data-testid="stMarkdownContainer"] pre,
[data-testid="stMarkdownContainer"] pre code,
[data-testid="stMarkdownContainer"] .highlight,
[data-testid="stMarkdownContainer"] .highlight pre,
[data-testid="stMarkdownContainer"] .highlight pre code {
    background: #0a0c14 !important;
    background-color: #0a0c14 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 6px !important;
    color: #e2e8f0 !important;
}
/* Alle Pygments-Span-Elemente lesbar machen */
[data-testid="stMarkdownContainer"] .highlight span,
[data-testid="stMarkdownContainer"] pre code span,
[data-testid="stMarkdownContainer"] pre span {
    color: #cbd5e1 !important;
    background: transparent !important;
}
/* Hover — Code-Block darf nicht transparent werden */
[data-testid="stMarkdownContainer"] pre:hover,
[data-testid="stMarkdownContainer"] pre:hover *,
[data-testid="stMarkdownContainer"] .highlight:hover,
[data-testid="stMarkdownContainer"] .highlight:hover * {
    background: #0a0c14 !important;
    background-color: #0a0c14 !important;
}

/* ── Expander Hover ──────────────────────────────────────────────────────────*/
[data-testid="stExpander"] details,
[data-testid="stExpander"] details > div,
[data-testid="stExpander"] details:hover,
[data-testid="stExpander"] details > div:hover {
    background: #111320 !important;
    background-color: #111320 !important;
}
[data-testid="stExpander"] summary { background: #111320 !important; color: #94a3b8 !important; }
[data-testid="stExpander"] summary:hover { background: #141626 !important; color: #e2e8f0 !important; }

/* ── Download-Button — wie reguläre Buttons ──────────────────────────────── */
[data-testid="stDownloadButton"] > button {
    background: #141626 !important;
    border: 1px solid #252a40 !important;
    color: #94a3b8 !important;
    border-radius: 6px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    transition: all 0.15s !important;
}
[data-testid="stDownloadButton"] > button:hover {
    border-color: #4f8ef7 !important;
    color: #4f8ef7 !important;
    background: #141f35 !important;
}

/* ── Alle anderen Container — kein Weiß beim Hover ──────────────────────────*/
/* Gezielt nur die problematischen Wrapper-Divs — keine Code-Blöcke */
[data-testid="stVerticalBlock"] > div:hover,
[data-testid="stHorizontalBlock"] > div:hover,
.element-container:not([data-testid="stCode"]):hover,
[data-testid="stElementContainer"]:not([data-testid="stCode"]):hover,
section[data-testid="stSidebar"] *:not(button):not(pre):not(code):hover,
[data-testid="stMarkdownContainer"]:hover,
[data-testid="stChatMessage"] > div:hover {
    background-color: transparent !important;
    background: transparent !important;
}

/* ── Chat ─────────────────────────────────────────────────────────────────── */
[data-testid="stChatMessage"] { background: #111320 !important; border: 1px solid #1e2235 !important; border-radius: 10px !important; padding: 12px 16px !important; margin-bottom: 8px !important; }
/* Avatar-Fleck entfernen */
[data-testid="stChatMessage"] > div:first-child { background: transparent !important; background-color: transparent !important; }
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] { background: #1e2235 !important; }
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatMessage"] h1,
[data-testid="stChatMessage"] h2,
[data-testid="stChatMessage"] h3,
[data-testid="stChatMessage"] h4,
[data-testid="stChatMessage"] span,
[data-testid="stChatMessage"] div { color: #e2e8f0 !important; }
[data-testid="stChatMessage"] strong { color: #ffffff !important; }
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 { color: #e2e8f0 !important; }
/* ── Chat Input Bereich — vollständig abdunkeln ───────────────────────────── */
[data-testid="stBottom"],
[data-testid="stBottom"] > div,
[data-testid="stBottom"] > div > div,
[data-testid="stChatInputContainer"],
[data-testid="stChatInputContainer"] > div,
[data-testid="stChatInputContainer"] > div > div,
[data-testid="stChatInput"],
[data-testid="stChatInput"] > div,
[data-testid="stChatInput"] > div > div,
[data-testid="stChatInput"] > div > div > div {
    background: #0d0f1a !important;
    background-color: #0d0f1a !important;
}
[data-testid="stBottom"] { border-top: 1px solid #1e2235 !important; }
[data-testid="stChatInput"] textarea {
    background: #141626 !important;
    border: 1px solid #ef4444 !important;
    color: #ffffff !important;
    border-radius: 8px !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: #4a5568 !important; }
[data-testid="stChatInputSubmitButton"],
[data-testid="stChatInputSubmitButton"] > button,
[data-testid="stChatInputSubmitButton"] span,
[data-testid="stChatInputSubmitButton"] svg {
    background: transparent !important;
    background-color: transparent !important;
    color: #4f8ef7 !important;
    fill: #4f8ef7 !important;
}

/* ── Alerts ───────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] { background: #111320 !important; border: 1px solid #1e2235 !important; border-radius: 8px !important; }
hr { border-color: #1e2235 !important; }

/* ── Agent Cards ──────────────────────────────────────────────────────────── */
.agent-card { background: #111320; border: 1px solid #1e2235; border-radius: 10px; padding: 14px 16px; margin-bottom: 8px; position: relative; transition: border-color 0.15s; min-height: 110px; }
.agent-card:hover { border-color: #2d3665; }
.agent-card.active { border-color: #4f8ef7; background: #0d1828; }
.agent-card.selected { border-color: #7c6af7; background: #100d28; }
.tier-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; margin-right: 6px; vertical-align: middle; }
.agent-label { font-size: 0.9rem; font-weight: 600; color: #e2e8f0; letter-spacing: 0.02em; }
.agent-desc { font-size: 0.75rem; color: #4a5568; margin-top: 3px; margin-bottom: 8px; }
.tools { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.tool-badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 0.68rem; font-weight: 500; color: #94a3b8; letter-spacing: 0.03em; }
.card-status { position: absolute; top: 12px; right: 14px; font-size: 0.68rem; color: #2d3665; font-weight: 500; letter-spacing: 0.06em; text-transform: uppercase; }
.agent-card.active .card-status { color: #4f8ef7; }
.agent-card.selected .card-status { color: #7c6af7; }
.card-files { margin-top: 6px; font-size: 0.7rem; color: #4a5568; }

/* ── Section labels ───────────────────────────────────────────────────────── */
.section-label { font-size: 0.7rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #4a5568; margin-bottom: 12px; margin-top: 4px; padding-bottom: 6px; border-bottom: 1px solid #1e2235; }

/* ── Topbar ───────────────────────────────────────────────────────────────── */
.topbar { display: flex; align-items: center; justify-content: space-between; padding: 0 0 20px 0; }
.logo-mark { font-size: 1.4rem; color: #4f8ef7; font-weight: 700; letter-spacing: -0.02em; }
.logo-name { font-size: 1.1rem; font-weight: 600; color: #e2e8f0; letter-spacing: 0.02em; }
.logo-sub { font-size: 0.72rem; color: #4a5568; font-weight: 400; }
.topbar-meta { font-size: 0.72rem; color: #2d3665; text-align: right; line-height: 1.6; }
.topbar-meta span { color: #4a5568; }

/* ── Tool status pills ────────────────────────────────────────────────────── */
.tool-status { display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; border-radius: 20px; font-size: 0.72rem; font-weight: 500; margin-bottom: 4px; }
.tool-status.live { background: #0d2018; border: 1px solid #1a4030; color: #34d399; }
.tool-status.offline { background: #1a1520; border: 1px solid #2a1f30; color: #4a5568; }

/* ── Briefing card ────────────────────────────────────────────────────────── */
.briefing-card { background: #0d1828; border: 1px solid #1a2f50; border-radius: 10px; padding: 16px; margin-bottom: 10px; }
.briefing-title { font-size: 0.88rem; font-weight: 600; color: #60a5fa; margin-bottom: 6px; }
.briefing-meta { font-size: 0.72rem; color: #4a5568; }

/* ── Task status ──────────────────────────────────────────────────────────── */
.task-running { background: #0d1828; border: 1px solid #1a3a5c; border-radius: 8px; padding: 12px 16px; margin: 8px 0; }
.task-done { background: #0d1f18; border: 1px solid #1a4030; border-radius: 8px; padding: 2px 8px; display: inline-block; font-size: 0.72rem; color: #34d399; }
.task-failed { background: #1f0d0d; border: 1px solid #401a1a; border-radius: 8px; padding: 2px 8px; display: inline-block; font-size: 0.72rem; color: #f87171; }

/* ── Komponenten-iframes — kein weißer Fleck ─────────────────────────────── */
[data-testid="stCustomComponentV1"] {
    line-height: 0 !important;
    font-size: 0 !important;
    background: transparent !important;
}
[data-testid="stCustomComponentV1"] iframe {
    background: transparent !important;
}

/* ── Trace steps ──────────────────────────────────────────────────────────── */
.trace-step { display: flex; align-items: flex-start; gap: 12px; padding: 8px 12px; border-radius: 6px; background: #111320; border: 1px solid #1e2235; margin-bottom: 4px; }
.step-num { font-size: 0.7rem; color: #2d3665; font-weight: 600; min-width: 20px; padding-top: 2px; }
.step-actor { font-size: 0.78rem; font-weight: 600; color: #4f8ef7; min-width: 80px; }
.step-action { font-size: 0.78rem; color: #4a5568; min-width: 100px; }
.step-output { font-size: 0.78rem; color: #64748b; flex: 1; word-break: break-word; }
</style>
"""


def inject_css() -> None:
    st.markdown(DARK_CSS, unsafe_allow_html=True)


def render_topbar() -> None:
    search_icon = "✓" if settings.is_search_configured() else "·"
    email_icon  = "✓" if settings.is_email_configured()  else "·"
    social_icon = "✓" if settings.is_social_configured() else "·"
    st.markdown(f"""
    <div class="topbar">
        <div style="display:flex;align-items:center;gap:12px">
            <span class="logo-mark">◈</span>
            <div>
                <div class="logo-name">DIRESO Agent Board</div>
                <div class="logo-sub">Multi-Agent Intelligence System</div>
            </div>
        </div>
        <div class="topbar-meta">
            <span>{settings.anthropic_model}</span> &nbsp;·&nbsp; Session <span>{st.session_state.get('session_id','')[:8]}</span><br>
            web {search_icon} &nbsp; email {email_icon} &nbsp; social {social_icon}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_agent_card(agent_name: str, is_active: bool, files: list[str], show_chat_btn: bool = True) -> None:
    meta = AGENT_META[agent_name]
    tc = tier_color(meta["tier"])
    is_selected = st.session_state.get("selected_agent") == agent_name
    classes = "agent-card" + (" active" if is_active else "") + (" selected" if is_selected else "")
    status = "ACTIVE" if is_active else ("SELECTED" if is_selected else meta["tier"].upper())
    files_html = ""
    if files:
        files_html = '<div class="card-files">' + " · ".join(f"📄 {f}" for f in files[:2]) + "</div>"
    st.markdown(f"""
    <div class="{classes}">
        <span class="card-status">{status}</span>
        <div><span class="tier-dot" style="background:{tc}"></span><span class="agent-label">{meta['label']}</span></div>
        <div class="agent-desc">{meta['desc']}</div>
        {tool_badges_html(meta['tools'])}
        {files_html}
    </div>
    """, unsafe_allow_html=True)
    if show_chat_btn:
        if st.button(f"Mit {meta['label']} chatten", key=f"card_{agent_name}", use_container_width=True):
            st.session_state.selected_agent = agent_name
            st.switch_page("pages/chat.py")


def section_label(text: str) -> None:
    st.markdown(f'<div class="section-label">{text}</div>', unsafe_allow_html=True)
