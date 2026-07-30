# Beauty Influencer Recommender — v2 (Pink + Biru Muda)

## Yang baru di versi ini
- Alur sesuai flowchart: Login (Google) → Dashboard Utama (app.py) → pilih menu:
  Rekomendasi, Ranking, Detail Profil, **Upload Data** (baru).
- Tema warna **pink + biru muda** konsisten di semua halaman (`utils/styling.py`).
- Bobot kriteria AHP (C1–C5) bisa **diatur manual lewat slider** di halaman
  Rekomendasi & Ranking (default tetap dari perhitungan AHP).
- Ranking & Rekomendasi bisa pilih **jumlah channel ditampilkan (3–10)**.
- Skema database mengikuti tabel yang SUDAH kamu buat sendiri:
  `influencers`, `videos`, `comments`, `influencer_scores`.
- Sidebar navigasi dipusatkan di `utils/nav.py` (dipanggil semua halaman),
  jadi tidak ada kode yang diulang-ulang.
- Menu navigasi otomatis Streamlit dimatikan lewat `.streamlit/config.toml`
  (`showSidebarNavigation = false`) — yang tampil cuma menu custom kita.

## SQL tambahan yang perlu dijalankan (Supabase SQL Editor)
```sql
ALTER TABLE influencer_scores ADD COLUMN IF NOT EXISTS topsis_score FLOAT;

CREATE TABLE IF NOT EXISTS users_log (
    email text PRIMARY KEY,
    nama text,
    last_login timestamp
);

CREATE TABLE IF NOT EXISTS scraping_log (
    id serial PRIMARY KEY,
    executed_at timestamp DEFAULT NOW()
);
```

## Cara jalan (ringkas — sama seperti sebelumnya)
1. Ekstrak zip, buka di VSCode
2. `python -m venv venv` → aktifkan
3. `python -m pip install -r requirements.txt`
4. Copy `.env.example` → `.env`, isi kredensial (Google OAuth, `DATABASE_URL` dari Supabase, `YOUTUBE_API_KEY`)
5. `python -m streamlit run app.py`

## Struktur folder
```
streamlit_app/
├── app.py                    # login + Dashboard Utama
├── .streamlit/config.toml    # matikan nav otomatis + tema warna dasar
├── utils/
│   ├── styling.py             # tema pink + biru muda
│   ├── nav.py                 # sidebar navigasi terpusat
│   ├── auth.py                 # login Google
│   ├── database.py             # semua query (sesuai skema tabelmu)
│   ├── topsis.py                # AHP + TOPSIS (bobot manual)
│   ├── sbert.py                  # relevansi konten
│   ├── indobertweet.py            # preprocessing + reputasi digital
│   └── scraping.py                 # scraping YouTube API
├── pages/
│   ├── 2_rekomendasi.py   # query + bobot AHP + top-N
│   ├── 3_ranking.py       # bobot AHP + jumlah channel + tabel/grafik
│   ├── 4_profil.py        # detail profil (versi diperbaiki)
│   └── 5_upload.py        # upload data sendiri (BARU)
└── scheduler/auto_scrape.py
```

**Catatan**: `pages/1_dashboard.py` sengaja dihapus — perannya sekarang
diambil alih `app.py` langsung (sesuai flowchart: setelah login, yang muncul
duluan adalah Dashboard Utama).
