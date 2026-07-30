"""
scheduler/auto_scrape.py
Scraping otomatis SEKALI SEMINGGU. Bisa dipakai:
1. Terintegrasi dengan app Streamlit (BackgroundScheduler jalan selama proses hidup)
2. Dijalankan terpisah: python scheduler/auto_scrape.py (cocok buat cron/Task Scheduler)
"""

import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

import streamlit as st
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from utils.scraping import scrape_all_channels

# GANTI dengan channel_id asli kamu, atau load dinamis dari database:
#   from utils.database import get_all_influencers
#   CHANNEL_IDS = get_all_influencers()["channel_id"].tolist()
CHANNEL_IDS = [
    # "UCxxxxxxxxxxxxxxxxxxxxxx",
]


def job_scrape_mingguan():
    if CHANNEL_IDS:
        print(f"[auto_scrape] Mulai scraping {len(CHANNEL_IDS)} channel...")
        hasil = scrape_all_channels(CHANNEL_IDS)
        print(f"[auto_scrape] Selesai. {hasil}")
    else:
        print("[auto_scrape] CHANNEL_IDS kosong, tidak ada yang di-scrape.")


@st.cache_resource(show_spinner=False)
def start_scheduler():
    scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
    scheduler.add_job(
        job_scrape_mingguan, trigger=IntervalTrigger(weeks=1),
        id="weekly_scrape_job", replace_existing=True,
    )
    scheduler.start()
    return scheduler


def trigger_manual_scrape(channel_ids=None, progress_callback=None):
    ids = channel_ids or CHANNEL_IDS
    if not ids:
        return {"error": "CHANNEL_IDS kosong. Isi dulu di scheduler/auto_scrape.py"}
    return scrape_all_channels(ids, progress_callback=progress_callback)


if __name__ == "__main__":
    job_scrape_mingguan()
