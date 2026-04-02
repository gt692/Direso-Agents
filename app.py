"""
app.py — DIRESO Agent Board Entry Point

Definiert die Navigation und startet die richtige Page.
Start: streamlit run app.py
"""
import streamlit as st

board  = st.Page("pages/board.py",   title="Board",     icon="🏢")
chat   = st.Page("pages/chat.py",    title="Chat",      icon="💬")
prompts = st.Page("pages/prompts.py", title="Prompts",   icon="📝")
trace  = st.Page("pages/trace.py",   title="Denkfluss", icon="🔀")

pg = st.navigation([board, chat, prompts, trace], position="sidebar")
pg.run()
