"""
utils/nav.py
Sidebar navigasi terpusat (info user, menu, tombol scraping manual, logout)
supaya tampilannya identik & konsisten di app.py maupun semua halaman pages/.
"""

import streamlit as st
from utils.auth import logout
from utils.database import get_last_scrape_time


def render_sidebar():
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:1rem 0;border-bottom:1px solid rgba(255,255,255,0.3)">
            <div style="font-size:3rem">👤</div>
            <div style="font-weight:600;font-size:1.1rem">{st.user.name}</div>
            <div style="font-size:0.8rem;opacity:0.85">{st.user.email}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 📌 Menu Navigasi")
        st.page_link("app.py",                 label="Dashboard Utama",    icon="🏠")
        st.page_link("pages/2_rekomendasi.py", label="Rekomendasi",        icon="🔍")
        st.page_link("pages/3_ranking.py",     label="Ranking youtuber", icon="🏆")
        st.page_link("pages/4_profil.py",      label="Detail Profil",      icon="👤")
        st.page_link("pages/5_upload.py",      label="Upload Data",        icon="📤")

        st.markdown("---")
        st.markdown("### 🔄 Update Data")
        if st.button("🚀 Scraping Manual", use_container_width=True, key="nav_scrape_btn"):
            with st.spinner("Scraping data terbaru..."):
                from utils.database import get_all_influencers
                from utils.scraping import scrape_channel
                df_inf = get_all_influencers()
                for _, row in df_inf.iterrows():
                    scrape_channel(row["channel_id"])
            st.success("✅ Data berhasil diperbarui!")

        last = get_last_scrape_time()
        if last:
            st.info(f"🕐 Update terakhir:\n{last.strftime('%d %b %Y %H:%M')}")
        else:
            st.info("🕐 Jadwal: Setiap Senin 02.00 WIB")

        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True, key="nav_logout_btn"):
            logout()