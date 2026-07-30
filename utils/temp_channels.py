"""
utils/temp_channels.py
Fitur "Tambah YouTuber Lain (Sementara)" — pengguna bisa mencari & menambahkan
channel YouTube di luar daftar yang sudah ada di database, untuk dilihat
gabungannya SELAMA SESI ITU SAJA. Data disimpan di st.session_state (bukan ke
Postgres), jadi otomatis hilang begitu pengguna keluar/tutup web.
"""

import numpy as np
import pandas as pd
import streamlit as st
from sentence_transformers import util

from utils.scraping import get_youtube_client, scrape_channel_videos, scrape_video_comments
from utils.indobertweet import predict_sentiment, hitung_reputasi_channel
from utils.sbert import load_sbert_model, clean_metadata_text

SESSION_KEY = "temp_channels"


def _ensure_state():
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = {}


def _best_thumbnail(thumbnails: dict) -> str:
    for size in ("high", "medium", "default"):
        if size in thumbnails:
            return thumbnails[size].get("url")
    return None


def search_channel_candidates(query: str, max_results: int = 5) -> list:
    """Cari channel YouTube berdasarkan nama/keyword."""
    yt = get_youtube_client()
    resp = yt.search().list(
        part="snippet", q=query, type="channel", maxResults=max_results
    ).execute()
    candidates = []
    for item in resp.get("items", []):
        snippet = item["snippet"]
        candidates.append({
            "channel_id": item["id"]["channelId"],
            "channel_name": snippet.get("title"),
            "thumbnail": _best_thumbnail(snippet.get("thumbnails", {})),
        })
    return candidates


def add_temp_channel(channel_id: str, n_videos: int = 25, n_comments: int = 50) -> dict:
    """Scrape channel + hitung skor secara LIVE, simpan ke session_state."""
    _ensure_state()
    if channel_id in st.session_state[SESSION_KEY]:
        return st.session_state[SESSION_KEY][channel_id]

    yt = get_youtube_client()
    resp = yt.channels().list(part="snippet,statistics", id=channel_id).execute()
    if not resp.get("items"):
        raise RuntimeError("Channel tidak ditemukan di YouTube.")
    item = resp["items"][0]
    stats, snippet = item["statistics"], item["snippet"]
    info = {
        "channel_id": channel_id,
        "channel_name": snippet.get("title"),
        "profile_picture_url": _best_thumbnail(snippet.get("thumbnails", {})),
        "subscriber_count": int(stats.get("subscriberCount", 0)),
        "total_view_count": int(stats.get("viewCount", 0)),
        "total_video_count": int(stats.get("videoCount", 0)),
    }

    videos = scrape_channel_videos(channel_id, max_results=n_videos)
    all_comments = []
    for v in videos:
        all_comments.extend(scrape_video_comments(v["video_id"], channel_id, n_comments))

    df_videos = pd.DataFrame(videos) if videos else pd.DataFrame(columns=[
        "video_id", "channel_id", "title", "description", "tags",
        "published_at", "view_count", "like_count", "comment_count",
    ])
    df_comments = pd.DataFrame(all_comments) if all_comments else pd.DataFrame(columns=[
        "comment_id", "video_id", "channel_id", "nama_akun",
        "text_original", "text_clean", "like_count", "published_at",
    ])

    # --- Sentimen & reputasi (IndoBERTweet, dihitung langsung) ---
    model_warning = None
    if not df_comments.empty:
        try:
            preds = predict_sentiment(df_comments["text_clean"].fillna("").tolist())
            df_comments["sentiment_label"] = [p["label"] for p in preds]
            df_comments["sentiment_score"] = [p["score"] for p in preds]
            reputation_score = hitung_reputasi_channel(df_comments["sentiment_label"].tolist())
        except Exception as e:
            model_warning = str(e)
            df_comments["sentiment_label"] = "netral"
            df_comments["sentiment_score"] = 0.0
            reputation_score = 0.0
    else:
        reputation_score = 0.0

    # --- Engagement, frekuensi upload (3 bulan), rasio penonton ---
    if not df_videos.empty:
        df_videos["published_at_dt"] = pd.to_datetime(df_videos["published_at"], utc=True, errors="coerce")
        total_views = df_videos["view_count"].fillna(0).sum()
        total_likes = df_videos["like_count"].fillna(0).sum()
        total_comment_count = df_videos["comment_count"].fillna(0).sum()
        engagement_rate = ((total_likes + total_comment_count) / total_views) if total_views > 0 else 0.0

        cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=90)
        frekuensi_upload = int(df_videos[df_videos["published_at_dt"] >= cutoff].shape[0])

        rasio_penonton = (
            df_videos["view_count"].fillna(0).mean() / info["subscriber_count"]
        ) if info["subscriber_count"] > 0 else 0.0
    else:
        engagement_rate, frekuensi_upload, rasio_penonton = 0.0, 0, 0.0

    data = {
        "info": info,
        "videos": df_videos,
        "comments": df_comments,
        "reputation_score": float(reputation_score),
        "engagement_rate": float(engagement_rate),
        "frekuensi_upload": frekuensi_upload,
        "rasio_penonton": float(rasio_penonton),
        "model_warning": model_warning,
    }
    st.session_state[SESSION_KEY][channel_id] = data
    return data


def remove_temp_channel(channel_id: str):
    _ensure_state()
    st.session_state[SESSION_KEY].pop(channel_id, None)


def get_temp_channels() -> dict:
    _ensure_state()
    return st.session_state[SESSION_KEY]


def has_temp_channels() -> bool:
    _ensure_state()
    return len(st.session_state[SESSION_KEY]) > 0


def get_temp_criteria_df() -> pd.DataFrame:
    """Format sama seperti get_criteria_matrix() di database.py, supaya bisa
    langsung digabung (pd.concat) dengan data YouTuber dari database."""
    temp = get_temp_channels()
    rows = []
    for cid, data in temp.items():
        info = data["info"]
        rows.append({
            "channel_id": cid,
            "channel_name": f"🆕 {info['channel_name']}",
            "subscriber_count": info["subscriber_count"],
            "total_video_count": info["total_video_count"],
            "total_view_count": info["total_view_count"],
            "profile_picture_url": info["profile_picture_url"],
            "reputation_score": data["reputation_score"],
            "relevance_score": 0.0,
            "engagement_rate": data["engagement_rate"],
            "frekuensi_upload": data["frekuensi_upload"],
            "rasio_penonton": data["rasio_penonton"],
        })
    return pd.DataFrame(rows)


def compute_temp_relevance(query: str) -> pd.DataFrame:
    """Hitung relevansi (SBERT) channel tambahan terhadap query brand,
    dengan cara yang sama seperti hitung_relevansi() di sbert.py."""
    temp = get_temp_channels()
    if not temp:
        return pd.DataFrame(columns=["channel_id", "relevance_score"])

    model = load_sbert_model()
    query_emb = model.encode(query, convert_to_numpy=True)

    rows = []
    for cid, data in temp.items():
        df_v = data["videos"]
        if df_v.empty:
            rows.append({"channel_id": cid, "relevance_score": 0.0})
            continue
        texts = [
            clean_metadata_text(r.get("title"), r.get("description"), r.get("tags"))
            for _, r in df_v.iterrows()
        ]
        embs = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        scores = np.clip(util.cos_sim(query_emb, embs).numpy()[0], 0, 1)
        rows.append({"channel_id": cid, "relevance_score": float(scores.mean())})
    return pd.DataFrame(rows)


def render_temp_channel_widget():
    """Widget UI untuk cari & kelola channel tambahan. Bisa dipanggil dari
    halaman mana saja (sekarang dipakai di tab 'Tambah YouTuber Lain' pada
    halaman Upload Data)."""
    query_input = st.text_input(
        "Cari nama channel:", key="temp_search_input",
        placeholder="Contoh: Tasya Farasya",
    )
    if st.button("🔍 Cari", key="temp_search_btn"):
        if query_input.strip():
            with st.spinner("Mencari channel..."):
                try:
                    st.session_state["temp_search_results"] = search_channel_candidates(query_input.strip())
                    st.session_state["temp_error"] = None
                except Exception as e:
                    st.session_state["temp_error"] = f"Gagal mencari: {e}"
                    st.session_state["temp_search_results"] = []
        else:
            st.session_state["temp_error"] = "Masukkan nama channel dulu."

    # --- Tampilkan hasil pencarian, TIDAK di dalam kolom sempit ---
    results = st.session_state.get("temp_search_results", [])
    pending_add = None
    if results:
        st.markdown("**Hasil pencarian:**")
        for c in results:
            col_a, col_b = st.columns([6, 1])
            with col_a:
                st.write(c["channel_name"])
            with col_b:
                if st.button("➕ Tambah", key=f"add_{c['channel_id']}"):
                    pending_add = c

    # --- Proses tambah channel DI LUAR kolom, supaya spinner & pesan
    #     error/sukses tampil penuh lebar halaman (tidak wrap huruf per baris) ---
    if pending_add:
        with st.spinner(f"Mengambil data {pending_add['channel_name']}... (25 video, 50 komentar/video)"):
            try:
                data = add_temp_channel(pending_add["channel_id"], n_videos=25, n_comments=50)
                st.session_state["temp_search_results"] = []
                if data.get("model_warning"):
                    st.session_state["temp_error"] = (
                        f"⚠️ {pending_add['channel_name']} ditambahkan, tapi skor reputasi "
                        f"sementara 0 karena model sentimen gagal dimuat: {data['model_warning']}"
                    )
                else:
                    st.session_state["temp_error"] = None
                    st.session_state["temp_success"] = f"✅ {pending_add['channel_name']} ditambahkan!"
            except Exception as e:
                st.session_state["temp_error"] = f"Gagal mengambil data: {e}"
        st.rerun()

    if st.session_state.get("temp_error"):
        st.warning(st.session_state["temp_error"])
    if st.session_state.get("temp_success"):
        st.success(st.session_state.pop("temp_success"))

    temp = get_temp_channels()
    if temp:
        st.markdown("---")
        st.markdown("**Aktif di sesi ini:**")
        for cid, data in list(temp.items()):
            col_a, col_b = st.columns([6, 1])
            with col_a:
                st.write(f"🆕 {data['info']['channel_name']}")
            with col_b:
                if st.button("🗑️ Hapus", key=f"remove_{cid}"):
                    remove_temp_channel(cid)
                    st.rerun()