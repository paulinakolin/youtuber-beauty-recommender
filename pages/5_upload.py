from dotenv import load_dotenv
load_dotenv()

import io
import streamlit as st
import pandas as pd
from utils.auth import require_login, configure_auth_from_env
from utils.styling import inject_css, page_header
from utils.nav import render_sidebar
from utils.database import insert_uploaded_influencers, insert_uploaded_comments
from utils.temp_channels import render_temp_channel_widget

st.set_page_config(page_title="Upload Data", page_icon="📤", layout="wide")
inject_css()
configure_auth_from_env()
require_login()
render_sidebar()

page_header("📤 Upload Data Sendiri", "Punya data youtuber/komentar sendiri? Unggah di sini untuk dianalisis sistem ini.")

tab1, tab2, tab3 = st.tabs(["📂 Upload File", "📋 Format Template", "➕ Tambah YouTuber Lain"])

with tab2:
    st.markdown("#### Format File yang Diperlukan")
    st.markdown("Download template Excel berikut sebagai panduan:")

    template_inf = pd.DataFrame({
        "channel_id": ["UCContoh1"], "channel_name": ["ContohChannel1"],
        "subscriber_count": [100000], "total_view_count": [5000000],
        "total_video_count": [200],
    })
    template_kom = pd.DataFrame({
        "channel_id": ["UCContoh1"], "nama_akun": ["user123"],
        "text_original": ["produk ini bagus banget worth it"],
    })

    col1, col2 = st.columns(2)
    with col1:
        buf = io.BytesIO()
        template_inf.to_excel(buf, index=False)
        st.download_button("⬇️ Template Influencer", buf.getvalue(), "template_influencer.xlsx")
    with col2:
        buf2 = io.BytesIO()
        template_kom.to_excel(buf2, index=False)
        st.download_button("⬇️ Template Komentar", buf2.getvalue(), "template_komentar.xlsx")

with tab1:
    st.markdown("#### Upload File Excel")
    tipe = st.radio("Tipe data:", ["Data youtuber", "Data Komentar"], horizontal=True)
    uploaded = st.file_uploader("Pilih file Excel (.xlsx):", type=["xlsx"],
                                 help="Gunakan format sesuai template di tab 'Format Template'")

    if uploaded:
        try:
            df_upload = pd.read_excel(uploaded)
            st.success(f"✅ File berhasil dibaca: {len(df_upload)} baris")
            st.dataframe(df_upload.head(10), use_container_width=True)

            if st.button("💾 Simpan ke Database", use_container_width=True, type="primary"):
                with st.spinner("Menyimpan data..."):
                    records = df_upload.to_dict(orient="records")
                    if tipe == "Data youtuber":
                        berhasil = insert_uploaded_influencers(records)
                    else:
                        berhasil = insert_uploaded_comments(records)
                st.success(f"✅ {berhasil} data berhasil disimpan!")
                st.info("Buka menu Rekomendasi/Ranking untuk melihat hasil analisis terhadap data ini "
                        "(catatan: skor reputasi & relevansi baru terhitung setelah pipeline "
                        "IndoBERTweet/Sentence-BERT dijalankan pada data ini).")
        except Exception as e:
            st.error(f"❌ Error membaca file: {e}")

with tab3:
    st.markdown("#### Cari & Tambahkan YouTuber Lain (Sementara)")
    st.caption(
        "Ingin melihat YouTuber di luar daftar yang sudah ada? Cari di sini — datanya "
        "akan digabung sementara ke Dashboard, Rekomendasi, Ranking, dan Detail Profil, "
        "lalu otomatis hilang saat kamu keluar dari web ini."
    )
    render_temp_channel_widget()