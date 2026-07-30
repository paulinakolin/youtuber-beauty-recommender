"""
utils/styling.py
Tema visual konsisten: perpaduan PINK (utama) + BIRU MUDA (aksen sekunder).
Import inject_css() di SETIAP halaman (app.py & semua file pages/) supaya
tampilannya seragam.
"""

import streamlit as st

PINK = "#F45B9E"
PINK_DARK = "#C23E7A"
PINK_LIGHT = "#FDEAF3"
BLUE = "#4FC3E8"
BLUE_DARK = "#2E9FC7"
BLUE_LIGHT = "#EAF7FD"
TEXT_DARK = "#3A3653"
BG = "#FFF9FC"
SUCCESS = "#4CAF87"
WARNING = "#F2A93B"
DANGER = "#E85C6E"


def inject_css():
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
        html, body, [class*="css"] {{ font-family: 'Poppins', sans-serif; }}

        .stApp {{ background: {BG}; }}

        h1, h2, h3 {{ color: {PINK_DARK}; font-weight: 700; }}

        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {PINK} 0%, {BLUE} 100%);
        }}
        section[data-testid="stSidebar"] * {{ color: white !important; }}
        section[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.3); }}

        /* Override supaya teks di dalam kotak input sidebar tetap gelap & terbaca,
        karena background kotak input-nya putih (bukan pink/biru seperti sidebar) */
        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] textarea {{
            color: {TEXT_DARK} !important;
            background-color: white !important;
            caret-color: {TEXT_DARK} !important;
        }}
        section[data-testid="stSidebar"] input::placeholder,
        section[data-testid="stSidebar"] textarea::placeholder {{
            color: #9A96A8 !important;
            opacity: 1;
        }}
        section[data-testid="stSidebar"] div[data-baseweb="select"] * {{
            color: {TEXT_DARK} !important;
        }}
        section[data-testid="stSidebar"] div[data-baseweb="select"] {{
            background-color: white !important;
        }}

        .stButton > button {{
            background: linear-gradient(90deg, {PINK}, {BLUE});
            color: white; border: none; border-radius: 22px;
            padding: 0.5rem 1.6rem; font-weight: 600; transition: 0.2s;
        }}
        .stButton > button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(244,91,158,0.35);
        }}

        div[data-testid="stMetric"] {{
            background: white; border-radius: 14px; padding: 1rem;
            box-shadow: 0 2px 10px rgba(244,91,158,0.10);
            border-left: 4px solid {PINK};
        }}

        .main-header {{
            background: linear-gradient(120deg, {PINK} 0%, {BLUE} 100%);
            padding: 2rem; border-radius: 18px; color: white;
            text-align: center; margin-bottom: 1.6rem;
        }}
        .main-header p {{ color: white !important; opacity: 0.95; }}

        .card {{
            background: white; border-radius: 16px; padding: 1.2rem 1.4rem;
            box-shadow: 0 2px 12px rgba(79,195,232,0.12);
            border-top: 3px solid {PINK}; margin-bottom: 1rem; transition: 0.2s;
        }}
        .card:hover {{ transform: translateY(-2px); box-shadow: 0 6px 18px rgba(244,91,158,0.15); }}

        .badge-positif {{ background:#e3f6ee; color:{SUCCESS}; padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:600; }}
        .badge-netral  {{ background:{BLUE_LIGHT}; color:{BLUE_DARK}; padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:600; }}
        .badge-negatif {{ background:#fde8ea; color:{DANGER}; padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:600; }}
        .badge-warning {{ background:#fdf1e0; color:{WARNING}; padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:600; }}

        .login-box {{
        max-width: 430px; margin: 0 auto; background: white; border-radius: 22px;
        padding: 2.4rem; box-shadow: 0 10px 40px rgba(79,195,232,0.20);
        }}

        /* Kartu login (st.container(border=True)) — dibuat senada dengan .login-box */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius: 22px !important;
            border: none !important;
            box-shadow: 0 10px 40px rgba(79,195,232,0.20);
            background: white;
        }}

        div[data-testid="stExpander"] {{
            border: 1px solid {BLUE_LIGHT}; border-radius: 14px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="main-header">
            <h1 style="color:white;margin-bottom:4px;">{title}</h1>
            <p style="margin:0;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sentiment_badge(label: str) -> str:
    label = (label or "").lower()
    if label == "positif":
        return '<span class="badge-positif">Positif</span>'
    if label == "negatif":
        return '<span class="badge-negatif">Negatif</span>'
    return '<span class="badge-netral">Netral</span>'


def rank_medal(rank: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
