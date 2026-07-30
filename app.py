from dotenv import load_dotenv
load_dotenv()

import datetime
import streamlit as st
import plotly.graph_objects as go
from utils.auth import configure_auth_from_env, require_login, logout
from utils.database import (
    get_dashboard_summary, get_top_content_categories,
    get_negative_keywords, get_smart_alerts,
)
from utils.temp_channels import get_temp_channels
from utils.styling import (
    inject_css, page_header, SUCCESS, WARNING, DANGER, BLUE, BLUE_LIGHT, PINK,
)

st.set_page_config(
    page_title="Beauty Youtuber Recommender",
    page_icon="💄",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
configure_auth_from_env()

# =============================================
# HALAMAN LOGIN (kalau belum login, HANYA ini yang tampil)
# =============================================
if not st.user.is_logged_in:
    st.markdown("""
    <div class="main-header">
        <h1>💄 Beauty Youtuber Recommender</h1>
        <p>Sistem Rekomendasi YouTube Creator Kecantikan Indonesia</p>
        <p style="font-size:0.85rem;">Menggunakan IndoBERTweet · Sentence-BERT · TOPSIS</p>
    </div>
    """, unsafe_allow_html=True)

    st.write("")
    col1, col2, col3 = st.columns([1, 1.3, 1])
    with col2:
        with st.container(border=True):
            st.markdown("""
                <div style="text-align:center;padding:0.6rem 0 1rem 0;">
                    <div style="font-size:2.6rem;">🔐</div>
                    <h3 style="margin:0.4rem 0 0.3rem 0;color:#C23E7A;">Masuk ke Sistem</h3>
                    <p style="color:#8A8798;font-size:0.9rem;margin-bottom:0;">
                        Gunakan akun Google kamu untuk melanjutkan
                    </p>
                </div>
            """, unsafe_allow_html=True)
            st.write("")
            st.button("Login dengan Google", use_container_width=True, on_click=st.login, type="primary")
    st.stop()

require_login()

from utils.nav import render_sidebar
render_sidebar()

# =============================================
# HALAMAN UTAMA DASHBOARD
# =============================================
page_header("💄 Beauty Youtuber Recommender", "Selamat datang! Pilih menu di sidebar untuk mulai")


def _format_update(ts) -> str:
    if ts is None:
        return "Belum pernah"
    ts_naive = ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts
    delta_days = (datetime.datetime.utcnow() - ts_naive).days
    if delta_days <= 0:
        return "Hari ini"
    if delta_days == 1:
        return "Kemarin"
    return f"{delta_days} hari lalu"


def _metric_card(label: str, value, bg: str, fg: str):
    st.markdown(f"""
    <div style="background:{bg};border-radius:14px;padding:1rem;
                box-shadow:0 2px 10px rgba(0,0,0,0.06);height:100%;">
        <div style="font-size:0.8rem;color:{fg};opacity:0.9;">{label}</div>
        <div style="font-size:1.6rem;font-weight:700;color:{fg};margin-top:2px;">{value}</div>
    </div>
    """, unsafe_allow_html=True)


def _merge_temp_into_summary(base: dict, temp: dict) -> dict:
    """Gabungkan angka dari YouTuber tambahan (sesi ini) ke ringkasan dashboard."""
    if not temp:
        return base

    merged = dict(base)
    n_old = base["total_influencer"]
    n_temp = len(temp)
    n_new = n_old + n_temp

    total_video_temp = sum(len(d["videos"]) for d in temp.values())
    total_comment_temp = sum(len(d["comments"]) for d in temp.values())

    pos_temp = sum(int((d["comments"]["sentiment_label"] == "positif").sum()) for d in temp.values() if not d["comments"].empty)
    net_temp = sum(int((d["comments"]["sentiment_label"] == "netral").sum()) for d in temp.values() if not d["comments"].empty)
    neg_temp = sum(int((d["comments"]["sentiment_label"] == "negatif").sum()) for d in temp.values() if not d["comments"].empty)

    total_reputation_new = base["avg_reputation"] * n_old + sum(d["reputation_score"] for d in temp.values())
    total_subscriber_new = base["avg_subscriber"] * n_old + sum(d["info"]["subscriber_count"] for d in temp.values())
    total_engagement_new = (base["avg_engagement"] / 100) * n_old + sum(d["engagement_rate"] for d in temp.values())

    merged["total_influencer"] = n_new
    merged["total_video"] = base["total_video"] + total_video_temp
    merged["total_comment"] = base["total_comment"] + total_comment_temp
    merged["avg_reputation"] = (total_reputation_new / n_new) if n_new else 0
    merged["avg_subscriber"] = (total_subscriber_new / n_new) if n_new else 0
    merged["avg_engagement"] = (total_engagement_new / n_new * 100) if n_new else 0
    merged["positif"] = base["positif"] + pos_temp
    merged["netral"] = base["netral"] + net_temp
    merged["negatif"] = base["negatif"] + neg_temp
    return merged


ringkasan = get_dashboard_summary()
kategori_konten = get_top_content_categories(top_n=4)
kata_negatif = get_negative_keywords(top_n=3)
alerts = get_smart_alerts()
n_alert_channel = len({a["channel_name"] for a in alerts})

temp_channels = get_temp_channels()
ringkasan = _merge_temp_into_summary(ringkasan, temp_channels)

if temp_channels:
    st.info(
        f"🆕 {len(temp_channels)} YouTuber tambahan sedang aktif di sesi kamu — "
        "angka di halaman ini sudah termasuk data mereka. "
        "*(Kategori Konten & Peringatan di bawah masih dari 54 YouTuber tetap saja.)*"
    )

# =============================================
# BARIS 1 — statistik dasar
# =============================================
c1, c2, c3, c4 = st.columns(4)
with c1:
    _metric_card("👥 Total Youtuber", ringkasan["total_influencer"], "white", "#3A3653")
with c2:
    _metric_card("🎬 Video Dianalisis", f'{ringkasan["total_video"]:,}', "white", "#3A3653")
with c3:
    _metric_card("💬 Komentar Dianalisis", f'{ringkasan["total_comment"]:,}', "white", "#3A3653")
with c4:
    _metric_card("🕐 Update Terakhir", _format_update(ringkasan["last_update"]), "white", "#3A3653")

st.write("")

# =============================================
# BARIS 2 — skor & peringatan ringkas
# =============================================
c5, c6, c7, c8 = st.columns(4)
with c5:
    _metric_card("⭐ Rata-rata Reputasi", f'{ringkasan["avg_reputation"]:.3f}', "white", "#3A3653")
with c6:
    _metric_card("📈 Rata-rata Engagement", f'{ringkasan["avg_engagement"]:.1f}%', "white", "#3A3653")
with c7:
    _metric_card("👤 Rata-rata Subscriber", f'{ringkasan["avg_subscriber"]:,.0f}', "#E3F6EE", SUCCESS)
with c8:
    if n_alert_channel > 0:
        _metric_card("⚠️ Perlu Perhatian", f"{n_alert_channel} Youtuber", "#FDF1E0", WARNING)
    else:
        _metric_card("⚠️ Perlu Perhatian", "0 Youtuber", "#E3F6EE", SUCCESS)

st.markdown("---")

# =============================================
# DISTRIBUSI SENTIMEN & KATEGORI KONTEN
# =============================================
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 🎨 Distribusi Sentimen")
    if ringkasan["total_comment"] > 0:
        st.caption(f'{ringkasan["total_comment"]:,} komentar dianalisis')
        fig = go.Figure(data=[go.Pie(
            labels=["Positif", "Netral", "Negatif"],
            values=[ringkasan["positif"], ringkasan["netral"], ringkasan["negatif"]],
            hole=0.6, marker_colors=[SUCCESS, BLUE, DANGER],
        )])
        fig.update_layout(height=280, paper_bgcolor="rgba(0,0,0,0)", showlegend=True,
                           margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
        if kata_negatif:
            st.caption(f'Kata sering muncul di komentar negatif: {", ".join(kata_negatif)}')
    else:
        st.info("Belum ada data komentar bersentimen.")

with col_right:
    st.markdown("#### 🏷️ Kategori Konten Terpopuler")
    st.caption("Dihitung otomatis dari tags & judul video — menyesuaikan niche Youtuber yang di-scrape")
    if not kategori_konten.empty:
        for _, row in kategori_konten.iterrows():
            st.markdown(f"""
            <div style="margin-bottom:0.7rem;">
                <div style="display:flex;justify-content:space-between;font-size:0.9rem;">
                    <span>{str(row['kategori']).title()}</span><span><b>{row['persentase']:.0f}%</b></span>
                </div>
                <div style="background:{BLUE_LIGHT};border-radius:20px;height:8px;margin-top:3px;">
                    <div style="background:{PINK};width:{row['persentase']}%;height:8px;border-radius:20px;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Belum ada data tags/judul video untuk dianalisis.")

st.markdown("---")

# =============================================
# PERINGATAN OTOMATIS — Perlu Perhatian
# =============================================
st.subheader("⚠️ Peringatan — Perlu Perhatian")
if alerts:
    for a in alerts:
        color = DANGER if a["level"] == "danger" else WARNING
        bg = "#fde8ea" if a["level"] == "danger" else "#fdf1e0"
        st.markdown(f"""
        <div style="background:{bg};border-left:4px solid {color};padding:0.7rem 1.1rem;
                    border-radius:8px;margin:0.4rem 0;">
            <b>{a['channel_name']}</b> — {a['message']}
        </div>
        """, unsafe_allow_html=True)
else:
    st.success("✅ Tidak ada Youtuber dengan status waspada saat ini.")