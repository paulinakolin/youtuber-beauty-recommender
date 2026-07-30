from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd
import plotly.express as px
from utils.auth import require_login, configure_auth_from_env
from utils.styling import inject_css, page_header
from utils.nav import render_sidebar
from utils.database import get_criteria_matrix
from utils.topsis import hitung_topsis, bobot_slider_ui
from utils.temp_channels import get_temp_channels, get_temp_criteria_df

st.set_page_config(page_title="Ranking", page_icon="🏆", layout="wide")
inject_css()
configure_auth_from_env()
require_login()
render_sidebar()

page_header("🏆 Ranking Youtuber", "Daftar ranking youtuber berdasarkan skor TOPSIS dengan 5 kriteria AHP.")

df = get_criteria_matrix()

temp_channels = get_temp_channels()
if temp_channels:
    df = pd.concat([df, get_temp_criteria_df()], ignore_index=True)
    st.caption(
        f"🆕 {len(temp_channels)} YouTuber tambahan (sesi ini) ikut ditampilkan. "
        "Relevansi mereka diset 0 di halaman ini karena belum ada query brand (isi di halaman Rekomendasi)."
    )

if df.empty:
    st.info("Belum ada data influencer di database. Jalankan scraping terlebih dahulu.")
    st.stop()

# =============================================
# ATUR BOBOT KRITERIA (AHP) — bisa diubah manual
# =============================================
with st.expander("⚙️ Atur Bobot Kepentingan Kriteria (AHP)", expanded=False):
    bobot_manual = bobot_slider_ui(st, key_prefix="ranking")

df["topsis_score"] = hitung_topsis(df, bobot_manual)
df = df.sort_values("topsis_score", ascending=False).reset_index(drop=True)

st.markdown("---")

# =============================================
# FILTER + JUMLAH CHANNEL DITAMPILKAN
# =============================================
col1, col2, col3 = st.columns(3)
with col1:
    min_sub = st.number_input("Minimum Subscriber:", value=0, step=10000)
with col2:
    min_rep = st.slider("Minimum Reputasi:", 0.0, 1.0, 0.0, 0.1)
with col3:
    jumlah_tampil = st.slider("Jumlah Channel Ditampilkan:", min_value=3, max_value=10, value=10)

df_filtered = df[
    (df["subscriber_count"] >= min_sub) & (df["reputation_score"] >= min_rep)
].head(jumlah_tampil).reset_index(drop=True)
df_filtered.index += 1

if df_filtered.empty:
    st.warning("Tidak ada channel yang memenuhi filter di atas.")
    st.stop()

# =============================================
# GRAFIK
# =============================================
st.markdown("#### 📈 Distribusi Reputasi vs Relevansi")
fig = px.scatter(
    df_filtered, x="reputation_score", y="relevance_score", size="subscriber_count",
    color="topsis_score", hover_name="channel_name",
    color_continuous_scale=["#E85C6E", "#F2A93B", "#4CAF87"],
    labels={"reputation_score": "Skor Reputasi", "relevance_score": "Skor Relevansi",
            "topsis_score": "Skor TOPSIS", "subscriber_count": "Subscriber"},
)
fig.update_layout(height=420, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#EAF7FD")
st.plotly_chart(fig, use_container_width=True)

st.markdown("#### 📊 Skor TOPSIS per Channel")
fig2 = px.bar(
    df_filtered.sort_values("topsis_score"), x="topsis_score", y="channel_name", orientation="h",
    color="topsis_score", color_continuous_scale=["#FDEAF3", "#F45B9E", "#C23E7A"],
    labels={"topsis_score": "Skor TOPSIS", "channel_name": "Channel"},
)
fig2.update_layout(height=420, paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
st.plotly_chart(fig2, use_container_width=True)

# =============================================
# TABEL
# =============================================
st.markdown("#### 📋 Tabel Ranking Lengkap")
st.dataframe(
    df_filtered[[
        "channel_name", "subscriber_count", "reputation_score",
        "relevance_score", "engagement_rate", "frekuensi_upload",
        "rasio_penonton", "topsis_score",
    ]].rename(columns={
        "channel_name": "Channel", "subscriber_count": "Subscriber",
        "reputation_score": "Reputasi", "relevance_score": "Relevansi",
        "engagement_rate": "Engagement", "frekuensi_upload": "Frek. Upload",
        "rasio_penonton": "Rasio Penonton", "topsis_score": "TOPSIS Score",
    }).style.format({
        "Subscriber": "{:,.0f}", "Reputasi": "{:.4f}", "Relevansi": "{:.4f}",
        "Engagement": "{:.4f}", "Rasio Penonton": "{:.4f}", "TOPSIS Score": "{:.4f}",
    }).background_gradient(subset=["TOPSIS Score"], cmap="RdPu"),
    use_container_width=True, height=420,
)

csv = df_filtered.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download CSV", csv, "ranking_youtuber.csv", "text/csv")