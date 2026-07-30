import os
import streamlit as st
from utils.database import log_google_login

SECRETS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".streamlit", "secrets.toml")


def configure_auth_from_env():
    """Tulis .streamlit/secrets.toml dari nilai .env, supaya Streamlit
    membaca kredensial login lewat mekanisme resminya (baca file),
    bukan lewat suntik memori yang rawan masalah timing dengan on_click."""
    os.makedirs(os.path.dirname(SECRETS_PATH), exist_ok=True)

    content = f'''[auth]
redirect_uri = "{os.getenv("REDIRECT_URI", "http://localhost:8501/oauth2callback")}"
cookie_secret = "{os.getenv("COOKIE_SECRET", "")}"
client_id = "{os.getenv("GOOGLE_CLIENT_ID", "")}"
client_secret = "{os.getenv("GOOGLE_CLIENT_SECRET", "")}"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
'''

    # Hanya tulis ulang kalau isinya beda, supaya tidak trigger reload berlebihan
    existing = ""
    if os.path.exists(SECRETS_PATH):
        with open(SECRETS_PATH, "r") as f:
            existing = f.read()

    if existing.strip() != content.strip():
        with open(SECRETS_PATH, "w") as f:
            f.write(content)


def require_login():
    configure_auth_from_env()
    if not st.user.is_logged_in:
        st.warning("⚠️ Silakan login terlebih dahulu lewat halaman utama.")
        st.stop()

    allowed_raw = os.getenv("ALLOWED_EMAILS", "").strip()
    allowed = [e.strip() for e in allowed_raw.split(",") if e.strip()]
    if allowed and st.user.email not in allowed:
        st.error("Akun Google kamu belum diberi akses ke sistem ini.")
        st.button("Logout", on_click=st.logout)
        st.stop()

    try:
        log_google_login(st.user.email, getattr(st.user, "name", ""))
    except Exception:
        pass


def logout():
    st.logout()