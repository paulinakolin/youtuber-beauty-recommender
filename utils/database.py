"""
utils/database.py
Koneksi ke Postgres (Supabase) via SQLAlchemy. Skema tabel mengikuti yang
SUDAH kamu buat sendiri:
  influencers(channel_id, channel_name, subscriber_count, total_video_count,
              total_view_count, tanggal_dibuat, profile_picture_url, last_updated)
  videos(video_id, channel_id, title, description, tags, published_at,
         view_count, like_count, comment_count)
  comments(comment_id, video_id, channel_id, nama_akun, text_original,
           like_count, published_at, text_clean, sentiment_label, sentiment_score)
  influencer_scores(channel_id, reputation_score, relevance_score, saw_score,
                     topsis_score, calculated_at)
  users_log(email, nama, last_login)
  scraping_log(id, executed_at)
"""

import os
import re
from collections import Counter

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# Stopword umum ID/EN dipakai bareng untuk kategori konten & kata negatif —
# supaya deteksinya generik, tidak spesifik ke satu niche (mis. beauty).
STOPWORDS_ID = {
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "untuk", "dengan", "saya",
    "kamu", "aku", "gue", "gua", "kita", "kami", "dia", "nya", "ga", "gak",
    "tidak", "aja", "juga", "banget", "sih", "deh", "kok", "kak", "min", "ya",
    "lah", "pada", "atau", "ada", "jadi", "kalau", "kalo", "udah", "udh",
    "gitu", "gini", "apa", "kenapa", "gmn", "gimana", "dong", "nih", "tuh",
    "kan", "biar", "buat", "pas", "kayak", "kaya", "sama", "sudah", "belum",
    "masih", "lagi", "bisa", "tp", "trs", "terus", "yg",
    "the", "and", "for", "to", "of", "in", "on", "is", "a", "an",
}


@st.cache_resource(show_spinner=False)
def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL belum diisi di .env")
    return create_engine(db_url, pool_pre_ping=True)


def get_all_influencers() -> pd.DataFrame:
    """Data channel + skor (reputasi, relevansi, topsis, saw). Dipakai di
    Ranking dan Detail Profil."""
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text("""
            SELECT i.*,
                   s.reputation_score, s.relevance_score,
                   s.topsis_score, s.saw_score
            FROM influencers i
            LEFT JOIN influencer_scores s ON s.channel_id = i.channel_id
            ORDER BY s.topsis_score DESC NULLS LAST
        """), conn)
    return df


def get_criteria_matrix() -> pd.DataFrame:
    """Gabungan skor + kriteria mentah (engagement, frekuensi upload, rasio
    penonton) yang dihitung LIVE dari tabel videos. Dipakai untuk TOPSIS
    di halaman Rekomendasi & Ranking."""
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text("""
            SELECT
                i.channel_id, i.channel_name, i.subscriber_count,
                i.total_video_count, i.total_view_count, i.profile_picture_url,
                s.reputation_score, s.relevance_score,
                COALESCE(
                    (SUM(v.like_count) + SUM(v.comment_count))::float
                    / NULLIF(SUM(v.view_count), 0), 0
                ) AS engagement_rate,
                COUNT(DISTINCT CASE
                    WHEN v.published_at >= NOW() - INTERVAL '3 months'
                    THEN v.video_id END
                ) AS frekuensi_upload,
                COALESCE(
                    AVG(v.view_count)::float / NULLIF(i.subscriber_count, 0), 0
                ) AS rasio_penonton
            FROM influencers i
            LEFT JOIN influencer_scores s ON s.channel_id = i.channel_id
            LEFT JOIN videos v ON v.channel_id = i.channel_id
            GROUP BY i.channel_id, i.channel_name, i.subscriber_count,
                     i.total_video_count, i.total_view_count, i.profile_picture_url,
                     s.reputation_score, s.relevance_score
        """), conn)
    return df.fillna(0)


def get_sentiment_stats() -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text("""
            SELECT i.channel_id, i.channel_name, s.reputation_score,
                   COUNT(*) FILTER (WHERE c.sentiment_label='positif') AS positif,
                   COUNT(*) FILTER (WHERE c.sentiment_label='netral')  AS netral,
                   COUNT(*) FILTER (WHERE c.sentiment_label='negatif') AS negatif
            FROM influencers i
            LEFT JOIN influencer_scores s ON s.channel_id = i.channel_id
            LEFT JOIN comments c ON c.channel_id = i.channel_id
            GROUP BY i.channel_id, i.channel_name, s.reputation_score
        """), conn)
    return df


def get_alert_influencers(threshold: float = 0.4) -> pd.DataFrame:
    """Alert versi sederhana berbasis ambang skor reputasi. Masih dipertahankan
    untuk kompatibilitas; dashboard utama sekarang pakai get_smart_alerts()."""
    df = get_all_influencers()
    if "reputation_score" not in df.columns or df.empty:
        return df.iloc[0:0]
    return df[df["reputation_score"].fillna(0) < threshold]


def get_dashboard_summary() -> dict:
    """Ringkasan angka untuk kartu statistik di Dashboard Utama. Generik —
    diambil langsung dari tabel influencers/videos/comments/influencer_scores,
    tidak spesifik ke niche apa pun."""
    engine = get_engine()
    with engine.connect() as conn:
        total_influencer = conn.execute(text("SELECT COUNT(*) FROM influencers")).scalar() or 0
        total_video = conn.execute(text("SELECT COUNT(*) FROM videos")).scalar() or 0
        total_comment = conn.execute(text("SELECT COUNT(*) FROM comments")).scalar() or 0

        avg_reputation = conn.execute(text(
            "SELECT AVG(reputation_score) FROM influencer_scores"
        )).scalar() or 0

        avg_subscriber = conn.execute(text(
            "SELECT AVG(subscriber_count) FROM influencers"
        )).scalar() or 0

        avg_engagement = conn.execute(text("""
            SELECT AVG(engagement_rate) FROM (
                SELECT channel_id,
                       COALESCE((SUM(like_count) + SUM(comment_count))::float
                                 / NULLIF(SUM(view_count), 0), 0) AS engagement_rate
                FROM videos GROUP BY channel_id
            ) t
        """)).scalar() or 0

        sent_row = conn.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE sentiment_label = 'positif') AS positif,
                COUNT(*) FILTER (WHERE sentiment_label = 'netral')  AS netral,
                COUNT(*) FILTER (WHERE sentiment_label = 'negatif') AS negatif
            FROM comments
        """)).fetchone()

        last_update = conn.execute(text("SELECT MAX(executed_at) FROM scraping_log")).scalar()

    positif, netral, negatif = (sent_row if sent_row else (0, 0, 0))
    positif, netral, negatif = positif or 0, netral or 0, negatif or 0
    total_sentimen = positif + netral + negatif
    avg_positive_sentiment = (positif / total_sentimen * 100) if total_sentimen else 0

    return {
         "total_influencer": total_influencer,
        "total_video": total_video,
        "total_comment": total_comment,
        "avg_reputation": float(avg_reputation),
        "avg_engagement": float(avg_engagement) * 100,
        "avg_subscriber": float(avg_subscriber),
        "avg_positive_sentiment": avg_positive_sentiment,
        "positif": positif,
        "netral": netral,
        "negatif": negatif,
        "last_update": last_update,
    }


def get_top_content_categories(top_n: int = 4) -> pd.DataFrame:
    """Kategori konten paling sering muncul, dihitung OTOMATIS dari tags video
    (fallback ke judul kalau tags kosong). Sengaja tidak hardcode ke kategori
    beauty tertentu, supaya tetap relevan apa pun niche Youtuber yang di-scrape
    nantinya."""
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text("SELECT tags, title FROM videos"), conn)

    if df.empty:
        return pd.DataFrame(columns=["kategori", "persentase"])

    counter = Counter()
    for _, row in df.iterrows():
        tags_raw = str(row.get("tags") or "").strip()
        if tags_raw:
            toks = {t.strip().lower() for t in tags_raw.split(",") if t.strip()}
        else:
            title = str(row.get("title") or "").lower()
            title = re.sub(r"[^\w\s]", " ", title)
            toks = {w for w in title.split() if len(w) > 3 and w not in STOPWORDS_ID}
        counter.update(toks)

    if not counter:
        return pd.DataFrame(columns=["kategori", "persentase"])

    total_video = len(df)
    top = counter.most_common(top_n)
    data = [{"kategori": k, "persentase": round(v / total_video * 100)} for k, v in top]
    return pd.DataFrame(data)


def get_negative_keywords(top_n: int = 3) -> list:
    """Kata yang paling sering muncul di komentar bersentimen negatif,
    dihitung otomatis dari text_clean — generik untuk niche apa pun."""
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(
            "SELECT text_clean FROM comments WHERE sentiment_label = 'negatif'"
        ), conn)

    if df.empty:
        return []

    counter = Counter()
    for txt in df["text_clean"].dropna():
        for w in str(txt).split():
            if len(w) > 2 and w not in STOPWORDS_ID:
                counter[w] += 1

    return [w for w, _ in counter.most_common(top_n)]


def get_smart_alerts(min_days_no_upload: int = 30,
                      sentiment_increase_threshold: float = 10,
                      low_engagement_ratio: float = 0.05) -> list:
    """Deteksi otomatis Youtuber yang perlu perhatian:
    1. Tidak upload video dalam waktu lama
    2. Sentimen negatif naik signifikan (30 hari terakhir vs 30 hari sebelumnya)
    3. Engagement turun tajam (view rata-rata jauh di bawah subscriber count)

    Ambang batas bisa disesuaikan lewat parameter — tidak hardcode ke niche
    tertentu, jadi tetap jalan walau daftar Youtuber yang di-scrape bertambah
    atau berubah niche."""
    engine = get_engine()
    alerts = []
    now = pd.Timestamp.utcnow()

    with engine.connect() as conn:
        df_upload = pd.read_sql(text("""
            SELECT i.channel_id, i.channel_name, MAX(v.published_at) AS last_upload
            FROM influencers i
            LEFT JOIN videos v ON v.channel_id = i.channel_id
            GROUP BY i.channel_id, i.channel_name
        """), conn)

        df_sent = pd.read_sql(text("""
            SELECT c.channel_id, i.channel_name, c.sentiment_label, c.published_at
            FROM comments c
            JOIN influencers i ON i.channel_id = c.channel_id
            WHERE c.published_at IS NOT NULL
        """), conn)

        df_eng = pd.read_sql(text("""
            SELECT i.channel_id, i.channel_name, i.subscriber_count, AVG(v.view_count) AS avg_view
            FROM influencers i
            JOIN videos v ON v.channel_id = i.channel_id
            GROUP BY i.channel_id, i.channel_name, i.subscriber_count
        """), conn)

    # 1. Tidak upload lama
    for _, r in df_upload.iterrows():
        if pd.isna(r["last_upload"]):
            continue
        last_upload = pd.to_datetime(r["last_upload"], utc=True)
        days = (now - last_upload).days
        if days >= min_days_no_upload:
            alerts.append({
                "channel_name": r["channel_name"],
                "message": f"tidak upload video sejak {days} hari lalu",
                "level": "warning",
            })

    # 2. Sentimen negatif naik
    if not df_sent.empty:
        df_sent["published_at"] = pd.to_datetime(df_sent["published_at"], utc=True, errors="coerce")
        recent_cut = now - pd.Timedelta(days=30)
        prev_cut = now - pd.Timedelta(days=60)
        for cid, g in df_sent.groupby("channel_id"):
            recent = g[g["published_at"] >= recent_cut]
            previous = g[(g["published_at"] < recent_cut) & (g["published_at"] >= prev_cut)]
            if len(recent) < 5 or len(previous) < 5:
                continue
            pct_recent = (recent["sentiment_label"] == "negatif").mean() * 100
            pct_prev = (previous["sentiment_label"] == "negatif").mean() * 100
            delta = pct_recent - pct_prev
            if delta >= sentiment_increase_threshold:
                alerts.append({
                    "channel_name": g["channel_name"].iloc[0],
                    "message": f"sentimen negatif naik {delta:.0f}% dalam 30 hari terakhir",
                    "level": "warning",
                })

    # 3. Engagement turun tajam
    for _, r in df_eng.iterrows():
        sub = r["subscriber_count"] or 0
        if sub > 0:
            ratio = (r["avg_view"] or 0) / sub
            if ratio < low_engagement_ratio:
                alerts.append({
                    "channel_name": r["channel_name"],
                    "message": "engagement rate turun tajam, view tidak sebanding subscriber",
                    "level": "danger",
                })

    return alerts


def get_influencer_detail(channel_id: str):
    engine = get_engine()
    with engine.connect() as conn:
        channel = pd.read_sql(text("""
            SELECT i.*, s.reputation_score, s.relevance_score,
                   s.topsis_score, s.saw_score
            FROM influencers i
            LEFT JOIN influencer_scores s ON s.channel_id = i.channel_id
            WHERE i.channel_id = :cid
        """), conn, params={"cid": channel_id})

        sentimen = pd.read_sql(text("""
            SELECT sentiment_label, COUNT(*) AS jumlah
            FROM comments WHERE channel_id = :cid
            GROUP BY sentiment_label
        """), conn, params={"cid": channel_id})

        videos = pd.read_sql(text("""
            SELECT title, view_count, like_count, comment_count, published_at
            FROM videos WHERE channel_id = :cid
            ORDER BY published_at DESC
        """), conn, params={"cid": channel_id})
    return channel, sentimen, videos


def get_last_scrape_time():
    engine = get_engine()
    try:
        with engine.connect() as conn:
            r = conn.execute(text("SELECT MAX(executed_at) FROM scraping_log"))
            return r.fetchone()[0]
    except Exception:
        return None


def log_google_login(email: str, nama: str):
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO users_log (email, nama, last_login)
            VALUES (:email, :nama, NOW())
            ON CONFLICT (email) DO UPDATE SET nama = :nama, last_login = NOW()
        """), {"email": email, "nama": nama})
        conn.commit()


def insert_uploaded_influencers(records: list):
    """Dipakai halaman Upload Data (tipe: Data Influencer)."""
    engine = get_engine()
    berhasil = 0
    with engine.connect() as conn:
        for row in records:
            try:
                conn.execute(text("""
                    INSERT INTO influencers
                        (channel_id, channel_name, subscriber_count,
                         total_video_count, total_view_count, tanggal_dibuat)
                    VALUES (:cid, :name, :sub, :vid, :view, NOW())
                    ON CONFLICT (channel_id) DO UPDATE SET
                        channel_name = :name, subscriber_count = :sub,
                        total_video_count = :vid, total_view_count = :view,
                        last_updated = NOW()
                """), {
                    "cid": row.get("channel_id"), "name": row.get("channel_name", ""),
                    "sub": row.get("subscriber_count", 0), "vid": row.get("total_video_count", 0),
                    "view": row.get("total_view_count", 0),
                })
                berhasil += 1
            except Exception:
                continue
        conn.commit()
    return berhasil


def insert_uploaded_comments(records: list):
    """Dipakai halaman Upload Data (tipe: Data Komentar). comment_id
    di-generate otomatis kalau tidak disediakan di file upload."""
    import uuid
    engine = get_engine()
    berhasil = 0
    with engine.connect() as conn:
        for row in records:
            try:
                cid = row.get("comment_id") or str(uuid.uuid4())
                conn.execute(text("""
                    INSERT INTO comments
                        (comment_id, channel_id, nama_akun, text_original, published_at)
                    VALUES (:comment_id, :channel_id, :nama_akun, :text_original, NOW())
                    ON CONFLICT (comment_id) DO NOTHING
                """), {
                    "comment_id": cid, "channel_id": row.get("channel_id"),
                    "nama_akun": row.get("nama_akun", ""),
                    "text_original": row.get("text_original", ""),
                })
                berhasil += 1
            except Exception:
                continue
        conn.commit()
    return berhasil