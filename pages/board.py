"""pages/board.py — Board-Ansicht mit Org-Tree und Agent-Cards."""
from __future__ import annotations

import streamlit as st

from config import settings
from memory.store import store
from ui.common import (
    AGENT_META, INTERNAL_AGENTS, EXTERNAL_AGENTS,
    inject_css, init_session_state, render_topbar,
    render_agent_card, section_label,
)

st.set_page_config(page_title="Board — DIRESO", page_icon="◈", layout="wide")
inject_css()
init_session_state()
render_topbar()

active_agents = set(st.session_state.last_agents_used)
if "preview_open" not in st.session_state:
    st.session_state.preview_open = None
recent_artifacts = store.get_recent_artifacts(limit=50)
artifacts_by_agent: dict[str, list[str]] = {}
for a in recent_artifacts:
    artifacts_by_agent.setdefault(a["agent_name"], []).append(a["filename"])

# ── View Toggle ───────────────────────────────────────────────────────────────
col_toggle, _ = st.columns([2, 5])
with col_toggle:
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Internes Board", use_container_width=True,
                     type="primary" if st.session_state.board_view == "internal" else "secondary"):
            st.session_state.board_view = "internal"
            st.rerun()
    with c2:
        if st.button("Externe Agenten", use_container_width=True,
                     type="primary" if st.session_state.board_view == "external" else "secondary"):
            st.session_state.board_view = "external"
            st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.board_view == "internal":

    section_label("Organisation — Internes Board")
    st.graphviz_chart("""digraph {
    graph [bgcolor="#0d0f1a", pad="0.5", ranksep="0.8", nodesep="0.5"]
    node  [fontname="Inter, Arial", fontsize=10, shape=box, style="filled,rounded", color="#1e2235", penwidth=1.2]
    edge  [color="#1e2235", arrowsize=0.6]
    ceo  [label="CEO\\nCo-CEO & Strategie",     fillcolor="#0d1828", fontcolor="#60a5fa", color="#4f8ef7", penwidth=2]
    cfo  [label="CFO\\nFinanzen & Förderung",    fillcolor="#12102a", fontcolor="#a78bfa", color="#6366f1"]
    coo  [label="COO\\nProzesse & Effizienz",    fillcolor="#12102a", fontcolor="#a78bfa", color="#6366f1"]
    cmo  [label="CMO\\nMarketing & Social",       fillcolor="#12102a", fontcolor="#a78bfa", color="#6366f1"]
    cso  [label="CSO\\nSales & CRM",              fillcolor="#12102a", fontcolor="#a78bfa", color="#6366f1"]
    cdo  [label="CDO\\nWebsite & Digital",        fillcolor="#12102a", fontcolor="#a78bfa", color="#6366f1"]
    cto  [label="CTO\\nTechnologie & Code",       fillcolor="#12102a", fontcolor="#a78bfa", color="#6366f1"]
    legal[label="Legal\\nDSGVO & Compliance",     fillcolor="#0f1c18", fontcolor="#6ee7b7", color="#34d399"]
    hr   [label="HR\\nPersonal",                  fillcolor="#0f1c18", fontcolor="#6ee7b7", color="#34d399"]
    ir   [label="IR\\nInvestor Relations",        fillcolor="#0f1c18", fontcolor="#6ee7b7", color="#34d399"]
    cs   [label="CS\\nCustomer Success",          fillcolor="#0f1c18", fontcolor="#6ee7b7", color="#34d399"]
    ceo -> {cfo coo cmo cso cdo cto}
    ceo -> {legal hr ir cs}
    {rank=same; cfo coo cmo cso cdo cto}
    {rank=same; legal hr ir cs}
}""")

    st.markdown("<br>", unsafe_allow_html=True)
    section_label("Executive")
    render_agent_card("ceo", "ceo" in active_agents, artifacts_by_agent.get("ceo", []))

    section_label("C-Suite")
    cols = st.columns(3)
    for i, ag in enumerate(["cfo", "coo", "cmo", "cso", "cdo", "cto"]):
        with cols[i % 3]:
            render_agent_card(ag, ag in active_agents, artifacts_by_agent.get(ag, []))

    section_label("Specialists")
    cols = st.columns(4)
    for i, ag in enumerate(["legal", "hr", "ir", "customer_success"]):
        with cols[i]:
            render_agent_card(ag, ag in active_agents, artifacts_by_agent.get(ag, []))

# ══════════════════════════════════════════════════════════════════════════════
else:
    section_label("Plattform-Agenten — Externe Nutzer")
    st.graphviz_chart("""digraph {
    graph [bgcolor="#0d0f1a", pad="0.5", ranksep="0.9", nodesep="0.8"]
    node  [fontname="Inter, Arial", fontsize=10, shape=box, style="filled,rounded", color="#374151", penwidth=1.2]
    edge  [color="#252a40", arrowsize=0.6]
    platform [label="DIRESO Plattform\\nKundenportal", fillcolor="#0d1424", fontcolor="#60a5fa", color="#4f8ef7", penwidth=2]
    port [label="Portfolio-Assistent\\nPortfolio-Analyse & Empfehlungen", fillcolor="#141414", fontcolor="#9ca3af", color="#374151"]
    rep  [label="Report-Generator\\nAutomatische Berichte & Exports",    fillcolor="#141414", fontcolor="#9ca3af", color="#374151"]
    platform -> port
    platform -> rep
}""")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<div style='background:#0d1424;border:1px solid #1a2f50;border-radius:8px;padding:12px 16px;"
        "margin-bottom:16px;font-size:0.78rem;color:#4a5568'>Externe Agenten werden direkt von "
        "Plattform-Kunden genutzt — kein Zugriff auf interne Unternehmensdaten.</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(3)
    for i, ag in enumerate(EXTERNAL_AGENTS):
        with cols[i]:
            render_agent_card(ag, ag in active_agents, artifacts_by_agent.get(ag, []))

# ── Workspace-Dateien ─────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)

col_ws_label, col_ws_btn = st.columns([4, 1])
with col_ws_label:
    section_label("Workspace — produzierte Dateien")
with col_ws_btn:
    if "confirm_cleanup" not in st.session_state:
        st.session_state.confirm_cleanup = False
    if not st.session_state.confirm_cleanup:
        if st.button("🗑 Aufräumen", use_container_width=True):
            st.session_state.confirm_cleanup = True
            st.rerun()
    else:
        st.warning("Leere und verwaiste DB-Einträge bereinigen?")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("Ja, bereinigen", type="primary", use_container_width=True, key="confirm_cleanup_yes"):
                deleted = 0
                # Nur leere Dateien (0 Bytes) entfernen
                for f in settings.workspace_dir.glob("*"):
                    if f.is_file() and f.stat().st_size == 0:
                        store.delete_artifact(f.name)
                        f.unlink()
                        deleted += 1
                # DB-Einträge ohne zugehörige Datei bereinigen
                all_artifacts = store.get_recent_artifacts(limit=200)
                for a in all_artifacts:
                    fp = settings.workspace_dir / a["filename"]
                    matches = list(settings.workspace_dir.glob(f"*{a['filename']}"))
                    if not fp.exists() and not matches:
                        store.delete_artifact(a["filename"])
                        deleted += 1
                st.session_state.confirm_cleanup = False
                st.success(f"{deleted} Einträge bereinigt.")
                st.rerun()
        with cc2:
            if st.button("Abbrechen", use_container_width=True, key="confirm_cleanup_no"):
                st.session_state.confirm_cleanup = False
                st.rerun()
if recent_artifacts:
    for artifact in recent_artifacts[:10]:
        fp = settings.workspace_dir / artifact["filename"]
        # Fallback: Datei mit Datumspräfix suchen
        if not fp.exists():
            matches = list(settings.workspace_dir.glob(f"*{artifact['filename']}"))
            fp = matches[0] if matches else fp
        content = fp.read_text(encoding="utf-8") if fp.exists() else None
        is_open = st.session_state.get("preview_open") == artifact["id"]

        st.markdown(
            f"<div style='display:flex;align-items:center;justify-content:space-between;"
            f"padding:10px 14px;background:#111320;border:1px solid #1e2235;border-radius:8px;margin-bottom:6px'>"
            f"<div>"
            f"<span style='color:#e2e8f0;font-family:monospace;font-size:0.82rem'>{artifact['filename']}</span>"
            f"&nbsp;&nbsp;<span style='color:#4a5568;font-size:0.72rem'>{artifact['agent_name'].upper()}</span>"
            f"&nbsp;&nbsp;<span style='color:#2d3665;font-size:0.72rem'>{str(artifact['created_at'])[:16]}</span>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if content:
            col_a, col_b, col_c, col_d = st.columns([5, 1, 1, 1])
            with col_b:
                if st.button("👁 Lesen", key=f"view_{artifact['id']}", use_container_width=True):
                    st.session_state.preview_open = None if is_open else artifact["id"]
                    st.rerun()
            with col_c:
                st.download_button("↓", data=content, file_name=fp.name,
                                   mime="text/markdown", key=f"dl_{artifact['id']}", use_container_width=True)
            with col_d:
                if st.button("🗑", key=f"del_{artifact['id']}", use_container_width=True):
                    store.delete_artifact(artifact["filename"])
                    if fp.exists():
                        fp.unlink()
                    st.rerun()

        if content and is_open:
            st.markdown(content)
            st.divider()
else:
    st.markdown("<span style='color:#2d3665;font-size:0.82rem'>Noch keine Dateien produziert.</span>", unsafe_allow_html=True)

# ── Board-Briefings ───────────────────────────────────────────────────────────
briefings = store.get_briefings(limit=5)
if briefings:
    st.markdown("<br>", unsafe_allow_html=True)
    section_label("Board-Briefings")
    for b in briefings:
        actions = b.get("actions") or {}
        pc = {"high": "#ef4444", "medium": "#f59e0b", "low": "#34d399"}.get(str(b.get("priority","")).lower(), "#4a5568")
        st.markdown(f"""
        <div class="briefing-card">
            <div style="display:flex;justify-content:space-between;align-items:flex-start">
                <div class="briefing-title">{b['decision']}</div>
                <span style="font-size:0.68rem;color:{pc};font-weight:600;text-transform:uppercase;padding:2px 8px;border:1px solid {pc}22;border-radius:10px;white-space:nowrap;margin-left:12px">{b.get('priority','')}</span>
            </div>
            <div class="briefing-meta">{b.get('rationale','')}</div>
            <div class="briefing-meta" style="margin-top:8px">{str(b['created_at'])[:16]}</div>
        </div>
        """, unsafe_allow_html=True)

        # Aktions-Buttons: Jede Agent-Aufgabe direkt in Chat senden
        if actions:
            st.markdown(
                "<div style='font-size:0.72rem;color:#4a5568;margin:-4px 0 6px 2px'>Aufgaben direkt an Agenten senden:</div>",
                unsafe_allow_html=True,
            )
            btn_cols = st.columns(min(len(actions), 4))
            for col_i, (ag, ag_task) in enumerate(actions.items()):
                with btn_cols[col_i % len(btn_cols)]:
                    if st.button(
                        f"{ag.upper()} → ausführen",
                        key=f"brief_{b['id']}_{ag}",
                        use_container_width=True,
                    ):
                        from memory.store import store as _store
                        _store.enqueue_task(
                            task_text=ag_task,
                            session_id=st.session_state.session_id,
                            agent_name=ag,
                        )
                        st.session_state.selected_agent = ag
                        st.switch_page("pages/chat.py")
