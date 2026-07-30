from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.auth import require_login, configure_auth_from_env
from utils.styling import inject_css, page_header
from utils.nav import render_sidebar
from utils.database import get_all_influencers, get_influencer_detail
from utils.temp_channels import get_temp_channels

st.set_page_config(page_title="Detail Profil", page_icon="👤", layout="wide")
inject_css()
configure_auth_from_env()
require_login()
render_sidebar()

page_header("👤 Detail Profil Youtuber", "Pilih youtuber untuk melihat skor, tren sentimen, dan status peringatan.")


def _info_box(icon_label: str, value: str):
    st.markdown(f"""
    <div style="border:1px solid #F4C0D1;border-radius:12px;padding:0.6rem 0.9rem;
                margin-bottom:0.8rem;background:white;">
        <div style="font-size:0.75rem;color:#8A8798;">{icon_label}</div>
        <div style="font-size:1.15rem;font-weight:700;color:#3A3653;margin-top:2px;">{value}</div>
    </div>
    """, unsafe_allow_html=True)


df_inf = get_all_influencers()
temp_channels = get_temp_channels()

if df_inf.empty and not temp_channels:
    st.info("Belum ada data youtuber di database.")
    st.stop()

semua_opsi = df_inf["channel_id"].tolist() + list(temp_channels.keys())


def _label(cid):
    if cid in temp_channels:
        return f"🆕 {temp_channels[cid]['info']['channel_name']} (sementara)"
    return df_inf[df_inf["channel_id"] == cid]["channel_name"].values[0]


pilihan = st.selectbox("Pilih youtuber:", options=semua_opsi, format_func=_label)

if pilihan:
    if pilihan in temp_channels:
        data = temp_channels[pilihan]
        info = data["info"]
        row = pd.Series({
            "channel_name": info["channel_name"],
            "profile_picture_url": info["profile_picture_url"],
            "subscriber_count": info["subscriber_count"],
            "total_video_count": info["total_video_count"],
            "total_view_count": info["total_view_count"],
            "reputation_score": data["reputation_score"],
            "relevance_score": None,
            "topsis_score": None,
        })
        videos = data["videos"] if not data["videos"].empty else pd.DataFrame(
            columns=["title", "view_count", "like_count", "comment_count", "published_at"]
        )
        comments_df = data["comments"]
        if not comments_df.empty:
            sentimen = comments_df.groupby("sentiment_label").size().reset_index(name="jumlah")
        else:
            sentimen = pd.DataFrame(columns=["sentiment_label", "jumlah"])
        st.info("🆕 Ini data sementara (sesi kamu saja) — tidak tersimpan permanen di database.")
    else:
        channel, sentimen, videos = get_influencer_detail(pilihan)
        if len(channel) == 0:
            st.error("Data tidak ditemukan")
            st.stop()
        row = channel.iloc[0]

    # =============================================
    # HITUNG METRIK TAMBAHAN DARI DATA VIDEO
    # =============================================
    videos_calc = videos.copy()
    videos_calc["published_at_dt"] = pd.to_datetime(videos_calc["published_at"], utc=True, errors="coerce")

    total_views = videos_calc["view_count"].fillna(0).sum()
    total_likes = videos_calc["like_count"].fillna(0).sum()
    total_comments = videos_calc["comment_count"].fillna(0).sum() if "comment_count" in videos_calc else 0
    avg_engagement = ((total_likes + total_comments) / total_views * 100) if total_views > 0 else 0

    if videos_calc["published_at_dt"].notna().any():
        last_upload_str = videos_calc["published_at_dt"].max().strftime("%d %b %Y")
    else:
        last_upload_str = "Belum ada data"

    subscriber_count = row.get("subscriber_count", 0) or 0
    rasio_penonton = (videos_calc["view_count"].fillna(0).mean() / subscriber_count) if subscriber_count > 0 else 0

    cutoff_3bln = pd.Timestamp.utcnow() - pd.Timedelta(days=90)
    frekuensi_upload_3bln = videos_calc[videos_calc["published_at_dt"] >= cutoff_3bln].shape[0]

    topsis_display = f"{row.get('topsis_score'):.4f}" if row.get("topsis_score") is not None else "-"

    # =============================================
    # FOTO (lebih besar) + NAMA + GRID METRIK 3x3
    # =============================================
    col_foto, col_info = st.columns([1, 3])

    with col_foto:
        if row.get("profile_picture_url"):
            st.image(row["profile_picture_url"], width=220)
        else:
            st.markdown('<div style="font-size:7rem;text-align:center;">👤</div>', unsafe_allow_html=True)

        rep = row.get("reputation_score", 0) or 0
        if rep < 0.4:
            st.markdown('<span class="badge-warning">⚠️ Status: Waspada</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge-positif">✅ Status: Normal</span>', unsafe_allow_html=True)

    with col_info:
        st.markdown(f"### {row['channel_name']}")

        r1c1, r1c2, r1c3 = st.columns(3)
        with r1c1: _info_box("👥 Subscriber", f"{int(subscriber_count):,}")
        with r1c2: _info_box("🎬 Total Video", f"{int(row.get('total_video_count', 0)):,}")
        with r1c3: _info_box("🕐 Terakhir Upload", last_upload_str)

        r2c1, r2c2, r2c3 = st.columns(3)
        with r2c1: _info_box("⭐ Skor Reputasi", f"{rep:.4f}")
        with r2c2: _info_box("📌 Skor Relevansi", f"{row.get('relevance_score', 0) or 0:.4f}")
        with r2c3: _info_box("📈 Rata-rata Engagement", f"{avg_engagement:.2f}%")

        r3c1, r3c2, r3c3 = st.columns(3)
        with r3c1: _info_box("👁️ Rasio Penonton", f"{rasio_penonton:.4f}")
        with r3c2: _info_box("📅 Frekuensi Upload (3 bulan)", f"{frekuensi_upload_3bln} video")
        with r3c3: _info_box("🏆 Skor TOPSIS", topsis_display)

    st.markdown("---")

    # =============================================
    # DISTRIBUSI SENTIMEN & VIDEO TERBARU
    # =============================================
    col_pie, col_vid = st.columns([3, 2])
    with col_pie:
        st.markdown("#### 🎨 Distribusi Sentimen Komentar")
        if len(sentimen) > 0:
            fig = go.Figure(data=[go.Pie(
                labels=sentimen["sentiment_label"], values=sentimen["jumlah"],
                hole=0.5, marker_colors=["#4CAF87", "#4FC3E8", "#E85C6E"],
            )])
            fig.update_layout(
                height=420,
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
                margin=dict(t=10, b=10, l=10, r=10),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Data sentimen belum tersedia")

    with col_vid:
        st.markdown("#### 🎬 Video Terbaru")
        if len(videos) > 0:
            for _, v in videos.head(5).iterrows():
                st.markdown(f"""
                <div style="background:#EAF7FD;border-radius:8px;padding:0.6rem 1rem;
                            margin:0.3rem 0;border-left:3px solid #F45B9E;">
                    <div style="font-weight:500;font-size:0.9rem;">{str(v['title'])[:60]}...</div>
                    <div style="font-size:0.8rem;color:#666;margin-top:0.2rem;">
                        👁️ {int(v['view_count'] or 0):,} views &nbsp;|&nbsp; ❤️ {int(v['like_count'] or 0):,} likes
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Data video tidak tersedia")