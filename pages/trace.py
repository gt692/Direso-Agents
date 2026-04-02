"""pages/trace.py — Denkfluss / Ausführungsvisualisierung."""
from __future__ import annotations

import streamlit as st

from ui.common import (
    INTERNAL_AGENTS, EXTERNAL_AGENTS, AGENT_META,
    inject_css, init_session_state, render_topbar, section_label, tier_color,
)

st.set_page_config(page_title="Denkfluss — DIRESO", page_icon="◈", layout="wide")
inject_css()
init_session_state()
render_topbar()

if not st.session_state.last_trace:
    st.markdown(
        "<div style='color:#2d3665;font-size:0.85rem;padding:40px 0'>"
        "Noch keine Interaktion. Starte eine Aufgabe im Chat.</div>",
        unsafe_allow_html=True,
    )
else:
    trace = st.session_state.last_trace

    section_label("Ausführungsfluss")

    dot_lines = [
        "digraph {",
        '    graph [bgcolor="#0d0f1a", pad="0.4", rankdir="LR"]',
        '    node [fontname="Inter, Arial", fontsize=9, shape=box, style="filled,rounded", color="#1e2235", penwidth=1]',
        '    edge [color="#252a40", arrowsize=0.5]',
    ]
    for step in trace:
        actor = step["actor"]
        label = f"{actor}\\n{step['action'].replace(chr(34), chr(39))}"
        node_id = f"s{step['step']}"
        tier = AGENT_META.get(actor, {}).get("tier", "")
        if actor == "router":
            fc, fc2 = "#0d1424", "#4f8ef7"
        elif tier == "external":
            fc, fc2 = "#111111", "#374151"
        elif actor in INTERNAL_AGENTS:
            fc, fc2 = "#12102a", "#6366f1"
        else:
            fc, fc2 = "#0f1a1a", "#34d399"
        dot_lines.append(f'    {node_id} [label="{label}", fillcolor="{fc}", fontcolor="{fc2}", color="{fc2}"];')

    for i in range(len(trace) - 1):
        dot_lines.append(f'    s{trace[i]["step"]} -> s{trace[i+1]["step"]};')
    dot_lines.append("}")
    st.graphviz_chart("\n".join(dot_lines))

    st.markdown("<br>", unsafe_allow_html=True)
    section_label("Schritt-Details")
    for step in trace:
        out = step["output"][:140] + ("..." if len(step["output"]) > 140 else "")
        st.markdown(f"""
        <div class="trace-step">
            <span class="step-num">{step['step']}</span>
            <span class="step-actor">{step['actor']}</span>
            <span class="step-action">{step['action']}</span>
            <span class="step-output">{out}</span>
        </div>
        """, unsafe_allow_html=True)
