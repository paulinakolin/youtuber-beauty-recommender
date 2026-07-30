from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd
from utils.auth import require_login, configure_auth_from_env
from utils.styling import inject_css, page_header, rank_medal
from utils.nav import render_sidebar
from utils.database import get_criteria_matrix
from utils.sbert import hitung_relevansi
from utils.topsis import hitung_topsis, bobot_slider_ui
from utils.temp_channels import get_temp_channels, get_temp_criteria_df, compute_temp_relevance

st.set_page_config(page_title="Rekomendasi", page_icon="🔍", layout="wide")
inject_css()
configure_auth_from_env()
require_login()
render_sidebar()

page_header("🔍 Rekomendasi Youtuber", "Masukkan deskripsi produk brand Anda untuk mendapatkan rekomendasi influencer paling relevan.")

# =============================================
# ATUR BOBOT KRITERIA (AHP) — bisa diubah manual
# =============================================
with st.expander("⚙️ Atur Bobot Kepentingan Kriteria (AHP)", expanded=False):
    bobot_manual = bobot_slider_ui(st, key_prefix="rekomendasi")

st.markdown("---")

temp_channels = get_temp_channels()
if temp_channels:
    st.caption(f"🆕 {len(temp_channels)} YouTuber tambahan (sesi ini) akan ikut dihitung dalam rekomendasi.")

# =============================================
# INPUT BRAND
# =============================================
with st.form("form_rekomendasi"):
    st.markdown("#### 📝 Deskripsi Produk Brand")
    query = st.text_area(
        "Deskripsikan produk Anda:",
        placeholder="Contoh: skincare untuk kulit berminyak dan berjerawat mengandung salicylic acid dan niacinamide",
        height=120,
    )
    top_n = st.slider("Tampilkan Top-N Rekomendasi:", min_value=3, max_value=10, value=5)
    submit = st.form_submit_button("🔎 Cari Rekomendasi", use_container_width=True)

if submit and query:
    with st.spinner("Memproses: Sentence-BERT relevansi konten → gabung skor lain → TOPSIS..."):
        df_kriteria = get_criteria_matrix()
        if temp_channels:
            df_kriteria = pd.concat([df_kriteria, get_temp_criteria_df()], ignore_index=True)

        if df_kriteria.empty:
            st.warning("Belum ada data influencer di database. Jalankan scraping terlebih dahulu.")
            st.stop()

        df_rel = hitung_relevansi(query)
        if temp_channels:
            df_rel_temp = compute_temp_relevance(query)
            df_rel = pd.concat([df_rel, df_rel_temp], ignore_index=True)

        if df_rel.empty:
            st.error("❌ Belum ada data video di database. Jalankan scraping terlebih dahulu.")
            st.stop()

        df_gabung = df_kriteria.drop(columns=["relevance_score"], errors="ignore").merge(
            df_rel, on="channel_id", how="left"
        )
        df_gabung = df_gabung.fillna(0)

        df_gabung["topsis_score"] = hitung_topsis(df_gabung, bobot_manual)
        df_hasil = df_gabung.sort_values("topsis_score", ascending=False).head(top_n).reset_index(drop=True)

        st.markdown("---")
        st.markdown(f"#### 🎯 Top {top_n} Rekomendasi untuk Query:")
        st.info(f'"{query}"')

        for rank, (_, row) in enumerate(df_hasil.iterrows(), 1):
            medal = rank_medal(rank)
            rep = row.get("reputation_score", 0)
            rep_color = "#4CAF87" if rep >= 0.7 else "#F2A93B" if rep >= 0.4 else "#E85C6E"

            st.markdown(f"""
            <div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div><span style="font-size:1.5rem">{medal}</span>
                         <b style="font-size:1.1rem;margin-left:0.5rem">{row['channel_name']}</b></div>
                    <div style="text-align:right">
                        <span style="background:#EAF7FD;color:#2E9FC7;padding:4px 12px;border-radius:20px;font-weight:600;font-size:0.9rem">
                            TOPSIS: {row['topsis_score']:.4f}
                        </span>
                    </div>
                </div>
                <div style="margin-top:0.8rem;display:flex;gap:1rem;flex-wrap:wrap">
                    <span>⭐ Reputasi: <b style="color:{rep_color}">{rep:.4f}</b></span>
                    <span>🎯 Relevansi: <b>{row['relevance_score']:.4f}</b></span>
                    <span>👥 Subscriber: <b>{int(row['subscriber_count']):,}</b></span>
                    <span>📅 Upload/3bln: <b>{int(row['frekuensi_upload'])}</b></span>
                    <span>👁️ Rasio Penonton: <b>{row['rasio_penonton']:.4f}</b></span>
                    <span>🏆 Skor TOPSIS: <b style="color:#C23E7A">{row['topsis_score']:.4f}</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

elif submit and not query:
    st.warning("⚠️ Masukkan deskripsi produk terlebih dahulu")