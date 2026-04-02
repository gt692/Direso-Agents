"""pages/prompts.py — System-Prompts anzeigen und bearbeiten."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from ui.common import (
    INTERNAL_AGENTS, EXTERNAL_AGENTS, AGENT_META,
    inject_css, init_session_state, render_topbar, section_label,
)

st.set_page_config(page_title="Prompts — DIRESO", page_icon="📝", layout="wide")
inject_css()
init_session_state()
render_topbar()

prompts_dir = Path(__file__).parent.parent / "prompts"

if "editing_prompt" not in st.session_state:
    st.session_state.editing_prompt = None


def render_prompt_entry(agent_name: str, label: str, path: Path) -> None:
    """Zeigt einen Prompt mit View/Edit-Toggle."""
    if not path.exists():
        st.warning(f"⚠ Prompt-Datei fehlt: `{path.relative_to(Path(__file__).parent.parent)}`")
        return

    is_editing = st.session_state.editing_prompt == str(path)
    content = path.read_text(encoding="utf-8")

    with st.expander(label):
        if is_editing:
            new_content = st.text_area(
                "Prompt bearbeiten",
                value=content,
                height=400,
                key=f"edit_{agent_name}",
                label_visibility="collapsed",
            )
            col_save, col_cancel = st.columns([1, 1])
            with col_save:
                if st.button("Speichern", key=f"save_{agent_name}", type="primary", use_container_width=True):
                    path.write_text(new_content, encoding="utf-8")
                    st.session_state.editing_prompt = None
                    st.success("Gespeichert — wirkt ab der nächsten Anfrage.")
                    st.rerun()
            with col_cancel:
                if st.button("Abbrechen", key=f"cancel_{agent_name}", use_container_width=True):
                    st.session_state.editing_prompt = None
                    st.rerun()
        else:
            col_code, col_btn = st.columns([8, 1])
            with col_code:
                # Eigenes HTML statt st.code() — volle Kontrolle über Hover
                escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                st.markdown(
                    f"<pre style='background:#0a0c14;border:1px solid #1e2235;border-radius:6px;"
                    f"padding:14px 16px;color:#e2e8f0;font-size:0.78rem;line-height:1.6;"
                    f"overflow-x:auto;white-space:pre-wrap;word-break:break-word;"
                    f"font-family:\"SF Mono\",\"Fira Code\",monospace'>{escaped}</pre>"
                    f"<div style='font-size:0.7rem;color:#2d3665;margin-top:4px'>"
                    f"{path.relative_to(Path(__file__).parent.parent)}</div>",
                    unsafe_allow_html=True,
                )
            with col_btn:
                if st.button("✏️ Edit", key=f"edit_btn_{agent_name}", use_container_width=True):
                    st.session_state.editing_prompt = str(path)
                    st.rerun()


# ── Interne Agenten ───────────────────────────────────────────────────────────
section_label("Interne Agenten")
for agent_name in INTERNAL_AGENTS:
    meta = AGENT_META[agent_name]
    render_prompt_entry(
        agent_name,
        f"{meta['label']} — {meta['desc']}",
        prompts_dir / "internal" / f"{agent_name}_system.txt",
    )

# ── Orchestrator ──────────────────────────────────────────────────────────────
orch_path = prompts_dir / "orchestrator_system.txt"
if orch_path.exists():
    section_label("Orchestrator Router")
    render_prompt_entry("orchestrator", "Router Prompt", orch_path)

# ── Externe Agenten ───────────────────────────────────────────────────────────
section_label("Externe Agenten")
for agent_name in EXTERNAL_AGENTS:
    meta = AGENT_META[agent_name]
    render_prompt_entry(
        agent_name,
        f"{meta['label']} — {meta['desc']}",
        prompts_dir / "external" / f"{agent_name}_system.txt",
    )

# ── Company Context ───────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
section_label("Company Context")
st.caption("Wird automatisch in jeden Agenten-Call injiziert.")
context_path = Path(__file__).parent.parent / "company_context.json"
if context_path.exists():
    context_data = json.loads(context_path.read_text(encoding="utf-8"))

    if st.session_state.editing_prompt == "company_context":
        edited = st.text_area(
            "Context bearbeiten (JSON)",
            value=json.dumps(context_data, ensure_ascii=False, indent=2),
            height=300,
            label_visibility="collapsed",
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Speichern", type="primary", use_container_width=True):
                try:
                    parsed = json.loads(edited)
                    context_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
                    st.session_state.editing_prompt = None
                    st.success("Gespeichert.")
                    st.rerun()
                except json.JSONDecodeError as e:
                    st.error(f"Ungültiges JSON: {e}")
        with c2:
            if st.button("Abbrechen", use_container_width=True):
                st.session_state.editing_prompt = None
                st.rerun()
    else:
        col_json, col_btn = st.columns([8, 1])
        with col_json:
            st.json(context_data)
        with col_btn:
            if st.button("✏️ Edit", key="edit_context", use_container_width=True):
                st.session_state.editing_prompt = "company_context"
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        col_a, col_b = st.columns([3, 1])
        with col_a:
            new_p = st.text_input("Priorität hinzufügen", placeholder="z.B. FZulG-Antrag Q2 2026", label_visibility="collapsed")
        with col_b:
            if st.button("Hinzufügen", use_container_width=True):
                if new_p:
                    context_data.setdefault("current_priorities", []).append(new_p)
                    context_path.write_text(json.dumps(context_data, ensure_ascii=False, indent=2), encoding="utf-8")
                    st.success("Gespeichert.")
                    st.rerun()
