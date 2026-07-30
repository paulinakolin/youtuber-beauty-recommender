"""
utils/sbert.py
Skor Relevansi Konten memakai Sentence-BERT
(sentence-transformers/paraphrase-multilingual-mpnet-base-v2).

Skema preprocessing teks video HARUS identik dengan preprocessing_final() di
notebook Colab SBERT: judul dibobotkan 3x + deskripsi, TAGS SENGAJA TIDAK
DIPAKAI (hasil eksperimen menunjukkan pengaruhnya minim dan berisiko menambah
noise generik seperti #skincare, #beauty, dll), tidak di-lowercase, dan video
dengan teks_konten < 5 kata dibuang.

Skor relevansi per channel = RATA-RATA cosine similarity antara query dengan
SETIAP video milik channel tsb. Metadata (judul + deskripsi + tags) diambil
LANGSUNG dari tabel videos setiap kali dibutuhkan (bukan dari file .pkl
offline), supaya selalu up-to-date.
"""

import os
import re
import numpy as np
import pandas as pd
import streamlit as st
from sentence_transformers import SentenceTransformer, util
from sqlalchemy import text
from utils.database import get_engine

URL_PATTERN = re.compile(r"http\S+|www\S+")
NON_LATIN_PATTERN = re.compile(r"[^\x00-\x7F\u00C0-\u024F\u1E00-\u1EFF]")
HASHTAG_PATTERN = re.compile(r"#(\w+)")
NON_WORD_PATTERN = re.compile(r"[^\w\s.,!?]")
MULTISPACE_PATTERN = re.compile(r"\s+")
MAX_WORDS = 500
MIN_WORDS = 5


def clean_metadata_text(title, description, tags=None) -> str:
    """Skema preprocessing FINAL — identik dengan preprocessing_final() di
    notebook Colab SBERT. Parameter `tags` sengaja diterima tapi TIDAK
    dipakai, supaya signature fungsi tetap kompatibel dengan pemanggil lama."""
    judul = title if isinstance(title, str) else ""
    deskripsi = description if isinstance(description, str) else ""

    # judul diberi bobot 3x karena paling representatif (sama seperti Colab)
    teks = f"{judul} {judul} {judul} {deskripsi}"

    teks = URL_PATTERN.sub("", teks)
    teks = NON_LATIN_PATTERN.sub(" ", teks)
    teks = HASHTAG_PATTERN.sub(r"\1", teks)
    teks = NON_WORD_PATTERN.sub(" ", teks)
    teks = MULTISPACE_PATTERN.sub(" ", teks).strip()

    kata = teks.split()
    if len(kata) > MAX_WORDS:
        teks = " ".join(kata[:MAX_WORDS])
    return teks


@st.cache_resource(show_spinner="Memuat model Sentence-BERT...")
def load_sbert_model():
    model_name = os.getenv("SBERT_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
    return SentenceTransformer(model_name)


@st.cache_data(show_spinner="Mengambil metadata video per channel...", ttl=600)
def get_video_metadata() -> pd.DataFrame:
    """Satu baris per video (bukan digabung per channel), supaya tiap video
    di-encode dan dibandingkan ke query secara terpisah. Video dengan
    teks_konten < 5 kata dibuang, sama seperti Cell 3 notebook Colab SBERT."""
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text("SELECT channel_id, title, description, tags FROM videos"), conn)

    if df.empty:
        return pd.DataFrame(columns=["channel_id", "metadata_text"])

    df["metadata_text"] = df.apply(
        lambda r: clean_metadata_text(r["title"], r["description"], r["tags"]), axis=1
    )
    df = df[df["metadata_text"].apply(lambda x: len(x.split()) >= MIN_WORDS)].reset_index(drop=True)
    return df[["channel_id", "metadata_text"]]


@st.cache_data(show_spinner=False)
def _encode_texts(texts: tuple) -> np.ndarray:
    model = load_sbert_model()
    return model.encode(list(texts), show_progress_bar=False, convert_to_numpy=True)


def hitung_relevansi(query: str) -> pd.DataFrame:
    """Return DataFrame [channel_id, relevance_score]. Skor per channel adalah
    RATA-RATA skor kemiripan (cosine similarity) query terhadap SELURUH video
    milik channel tsb — jadi mencerminkan relevansi konten channel secara
    keseluruhan, bukan hanya video yang paling mirip."""
    df_video = get_video_metadata()
    if df_video.empty:
        return pd.DataFrame(columns=["channel_id", "relevance_score"])

    model = load_sbert_model()
    query_emb = model.encode(query, convert_to_numpy=True)
    video_embs = _encode_texts(tuple(df_video["metadata_text"].tolist()))

    video_scores = util.cos_sim(query_emb, video_embs).numpy()[0]

    df_video = df_video.copy()
    df_video["video_score"] = np.clip(video_scores, 0, 1)

    df_channel = df_video.groupby("channel_id")["video_score"].mean().reset_index()
    df_channel.columns = ["channel_id", "relevance_score"]
    return df_channel