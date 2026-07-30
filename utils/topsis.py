"""
utils/topsis.py
AHP (Saaty, 1980) untuk bobot default + TOPSIS (Hwang & Yoon, 1981) untuk
perangkingan. Bobot AHP bisa DIGANTI MANUAL oleh pengguna lewat slider di
halaman Rekomendasi/Ranking (lihat normalisasi_bobot_manual).

Implementasi hitung_topsis() HARUS identik dengan notebook Colab AHP-TOPSIS:
hanya normalisasi vektor (TANPA min-max scaling tambahan), dengan transformasi
log1p pada rasio_penonton untuk meredam outlier ekstrem (Cell 6 Colab).
"""

import numpy as np

CRITERIA_NAMES = [
    "Reputasi Digital", "Relevansi Konten", "Engagement Rate",
    "Frekuensi Upload", "Rasio Penonton",
]
KOLOM_KRITERIA = [
    "reputation_score", "relevance_score", "engagement_rate",
    "frekuensi_upload", "rasio_penonton",
]
RI_TABLE = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.9, 5: 1.12}


def default_pairwise_matrix():
    # Matriks perbandingan berpasangan AHP hasil kuesioner ke pembimbing/pakar
    return np.array([
        [1,     2,     3,     5,    3],
        [1/2,   1,     3,     5,    3],
        [1/3,   1/3,   1,     3,    1],
        [1/5,   1/5,   1/3,   1,    1/3],
        [1/3,   1/3,   1,     3,    1],
    ], dtype=float)


def hitung_bobot_ahp(pairwise_matrix=None):
    if pairwise_matrix is None:
        pairwise_matrix = default_pairwise_matrix()
    n = pairwise_matrix.shape[0]
    normalized = pairwise_matrix / pairwise_matrix.sum(axis=0)
    bobot = normalized.mean(axis=1)
    lambda_max = (pairwise_matrix @ bobot / bobot).mean()
    ci = (lambda_max - n) / (n - 1)
    cr = ci / RI_TABLE.get(n, 1.12)
    return bobot, cr


def normalisasi_bobot_manual(nilai: list) -> np.ndarray:
    arr = np.array(nilai, dtype=float)
    total = arr.sum()
    if total == 0:
        return np.array([1 / len(arr)] * len(arr))
    return arr / total


def hitung_topsis(df, bobot, kolom=None):
    if kolom is None:
        kolom = KOLOM_KRITERIA
    X = df[kolom].fillna(0).to_numpy(dtype=float)

    # Transformasi log1p pada rasio_penonton (Viewer Ratio), sesuai notebook
    # Colab AHP-TOPSIS Cell 6 — kriteria ini sangat skewed dengan outlier
    # ekstrem; log1p meredam pengaruhnya tanpa mengubah urutan ranking relatif.
    if "rasio_penonton" in kolom:
        idx_vr = kolom.index("rasio_penonton")
        X[:, idx_vr] = np.log1p(X[:, idx_vr])

    denom = np.sqrt((X ** 2).sum(axis=0))
    denom[denom == 0] = 1e-9
    R = X / denom
    V = R * bobot

    A_plus, A_minus = V.max(axis=0), V.min(axis=0)
    D_plus = np.sqrt(((V - A_plus) ** 2).sum(axis=1))
    D_minus = np.sqrt(((V - A_minus) ** 2).sum(axis=1))

    denom2 = D_plus + D_minus
    denom2[denom2 == 0] = 1e-9
    return D_minus / denom2


def bobot_slider_ui(st, key_prefix: str = ""):
    """Widget slider AHP dipakai bareng di halaman Rekomendasi & Ranking,
    supaya konsisten. Return array bobot (sudah dinormalisasi)."""
    bobot_default, cr_default = hitung_bobot_ahp()
    st.caption(
        f"Default di bawah hasil perhitungan AHP (Consistency Ratio: {cr_default:.3f}). "
        f"Geser slider untuk mengubah bobot — otomatis dinormalisasi jadi total 100%."
    )
    nilai = []
    for i, nama in enumerate(CRITERIA_NAMES):
        v = st.slider(f"C{i+1} — {nama}", 0.0, 1.0, float(bobot_default[i]), 0.01,
                       key=f"{key_prefix}_bobot_{i}")
        nilai.append(v)

    bobot_manual = normalisasi_bobot_manual(nilai)

    cols = st.columns(5)
    for col, nama, b in zip(cols, CRITERIA_NAMES, bobot_manual):
        col.metric(nama.split()[0], f"{b:.1%}")

    return bobot_manual