"""
utils/scraping.py
Scraping channel/video/komentar via YouTube Data API v3, simpan ke database
sesuai skema tabel yang sudah dibuat user (influencers, videos, comments).
"""

import os
import datetime
from googleapiclient.discovery import build
from sqlalchemy import text
from utils.database import get_engine
from utils.indobertweet import clean_comment


def get_youtube_client():
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY belum diisi di .env")
    return build("youtube", "v3", developerKey=api_key)


def _best_thumbnail_url(thumbnails: dict) -> str:
    """Ambil URL thumbnail resolusi tertinggi yang tersedia (high > medium > default),
    supaya foto profil tidak blur saat ditampilkan besar di halaman Detail Profil."""
    for size in ("high", "medium", "default"):
        if size in thumbnails:
            return thumbnails[size].get("url")
    return None


def scrape_channel_info(channel_id: str) -> dict:
    yt = get_youtube_client()
    resp = yt.channels().list(part="snippet,statistics", id=channel_id).execute()
    if not resp.get("items"):
        return {}
    item = resp["items"][0]
    stats, snippet = item["statistics"], item["snippet"]
    return {
        "channel_id": channel_id,
        "channel_name": snippet.get("title"),
        "profile_picture_url": _best_thumbnail_url(snippet.get("thumbnails", {})),
        "subscriber_count": int(stats.get("subscriberCount", 0)),
        "total_view_count": int(stats.get("viewCount", 0)),
        "total_video_count": int(stats.get("videoCount", 0)),
    }


def scrape_channel_videos(channel_id: str, max_results: int = 25) -> list:
    yt = get_youtube_client()
    search_resp = yt.search().list(
        part="id", channelId=channel_id, order="date", maxResults=max_results, type="video",
    ).execute()
    video_ids = [it["id"]["videoId"] for it in search_resp.get("items", [])]
    if not video_ids:
        return []

    videos_resp = yt.videos().list(part="snippet,statistics", id=",".join(video_ids)).execute()
    videos = []
    for it in videos_resp.get("items", []):
        snippet, stats = it["snippet"], it["statistics"]
        videos.append({
            "video_id": it["id"], "channel_id": channel_id,
            "title": snippet.get("title"), "description": snippet.get("description"),
            "tags": ",".join(snippet.get("tags", [])),
            "published_at": snippet.get("publishedAt"),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
        })
    return videos


def scrape_video_comments(video_id: str, channel_id: str, max_results: int = 50) -> list:
    yt = get_youtube_client()
    comments = []
    try:
        resp = yt.commentThreads().list(
            part="snippet", videoId=video_id, maxResults=max_results, textFormat="plainText",
        ).execute()
    except Exception:
        return comments
    for item in resp.get("items", []):
        top = item["snippet"]["topLevelComment"]["snippet"]
        raw_text = top.get("textOriginal", "")
        comments.append({
            "comment_id": item["id"], "video_id": video_id, "channel_id": channel_id,
            "nama_akun": top.get("authorDisplayName", ""),
            "text_original": raw_text, "text_clean": clean_comment(raw_text),
            "like_count": int(top.get("likeCount", 0)),
            "published_at": top.get("publishedAt"),
        })
    return comments


def _upsert(conn, table, rows, pk_col, columns):
    for row in rows:
        set_clause = ", ".join(f"{c} = :{c}" for c in columns if c != pk_col)
        col_names = ", ".join(columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        conn.execute(text(f"""
            INSERT INTO {table} ({col_names}) VALUES ({placeholders})
            ON CONFLICT ({pk_col}) DO UPDATE SET {set_clause}
        """), {c: row.get(c) for c in columns})


def scrape_channel(channel_id: str, n_videos: int = 25, n_comments_per_video: int = 50) -> dict:
    """Fungsi utama dipanggil scheduler mingguan & tombol manual di Dashboard."""
    engine = get_engine()

    info = scrape_channel_info(channel_id)
    videos = scrape_channel_videos(channel_id, max_results=n_videos)
    all_comments = []
    for v in videos:
        all_comments.extend(scrape_video_comments(v["video_id"], channel_id, n_comments_per_video))

    with engine.connect() as conn:
        if info:
            conn.execute(text("""
                INSERT INTO influencers
                    (channel_id, channel_name, profile_picture_url,
                     subscriber_count, total_view_count, total_video_count, tanggal_dibuat)
                VALUES (:channel_id, :channel_name, :profile_picture_url,
                        :subscriber_count, :total_view_count, :total_video_count, NOW())
                ON CONFLICT (channel_id) DO UPDATE SET
                    channel_name = :channel_name, profile_picture_url = :profile_picture_url,
                    subscriber_count = :subscriber_count, total_view_count = :total_view_count,
                    total_video_count = :total_video_count, last_updated = NOW()
            """), info)

        if videos:
            _upsert(conn, "videos", videos, "video_id",
                    ["video_id", "channel_id", "title", "description", "tags",
                     "published_at", "view_count", "like_count", "comment_count"])

        if all_comments:
            _upsert(conn, "comments", all_comments, "comment_id",
                    ["comment_id", "video_id", "channel_id", "nama_akun",
                     "text_original", "text_clean", "like_count", "published_at"])

        conn.execute(text("INSERT INTO scraping_log (executed_at) VALUES (NOW())"))
        conn.commit()

    return {
        "channel_id": channel_id, "n_videos": len(videos), "n_comments": len(all_comments),
        "scraped_at": datetime.datetime.utcnow().isoformat(),
    }


def scrape_all_channels(channel_id_list: list, progress_callback=None) -> list:
    results = []
    total = len(channel_id_list)
    for i, cid in enumerate(channel_id_list, start=1):
        try:
            results.append(scrape_channel(cid))
        except Exception as e:
            results.append({"channel_id": cid, "error": str(e)})
        if progress_callback:
            progress_callback(i, total, cid)
    return results