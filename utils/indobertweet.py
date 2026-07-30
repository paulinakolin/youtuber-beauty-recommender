"""
utils/indobertweet.py
Preprocessing komentar (bahasa campuran ID-EN, slang, emoji) + loader model
IndoBERTweet hasil fine-tuning dari Google Colab, untuk skor Reputasi Digital.
Model di-load dari Hugging Face Hub (repo private).

Urutan preprocessing (jangan diubah urutannya):
1. lower-case
2. URL -> "HTTPURL", mention -> "@USER"
3. emoji -> teks
4. normalisasi FRASA multi-kata dulu, baru per-kata
5. normalisasi slang ID + EN informal
6. bersihkan huruf berulang & tanda baca berlebih
"""

import os
import re
import emoji
import torch
import streamlit as st
from transformers import AutoTokenizer, AutoModelForSequenceClassification

SLANG_DICT = {
    "bgt": "banget", "gpp": "tidak apa apa", "gws": "get well soon",
    "mnrt": "menurut", "yg": "yang", "gk": "tidak", "ga": "tidak",
    "gak": "tidak", "udh": "sudah", "udah": "sudah", "jd": "jadi",
    "sm": "sama", "bs": "bisa", "tp": "tapi", "krn": "karena",
    "dr": "dari", "utk": "untuk", "dgn": "dengan", "cakep": "cantik",
    "cakeb": "cantik", "kece": "keren", "mantul": "mantap betul",
}
ENGLISH_SLANG_DICT = {
    "omg": "oh my god", "btw": "by the way", "imo": "in my opinion",
    "tbh": "to be honest", "asap": "as soon as possible",
    "so good": "sangat bagus", "on point": "sangat pas",
    "worth it": "sepadan harganya", "must have": "wajib punya",
    "glow up": "membaik penampilannya",
}
MULTIWORD_PHRASES = {k: v for k, v in {**SLANG_DICT, **ENGLISH_SLANG_DICT}.items() if " " in k}
SINGLEWORD_DICT = {k: v for k, v in {**SLANG_DICT, **ENGLISH_SLANG_DICT}.items() if " " not in k}

URL_PATTERN = re.compile(r"http\S+|www\.\S+")
MENTION_PATTERN = re.compile(r"@\w+")
REPEATED_CHAR_PATTERN = re.compile(r"(.)\1{2,}")
PUNCT_PATTERN = re.compile(r"[^\w\s]")
MULTISPACE_PATTERN = re.compile(r"\s+")


def clean_comment(raw_text: str) -> str:
    if not isinstance(raw_text, str) or not raw_text.strip():
        return ""
    text_ = raw_text.lower()
    text_ = URL_PATTERN.sub("HTTPURL", text_)
    text_ = MENTION_PATTERN.sub("@USER", text_)
    text_ = emoji.demojize(text_, delimiters=(" ", " ")).replace("_", " ")
    for phrase, rep in sorted(MULTIWORD_PHRASES.items(), key=lambda x: -len(x[0])):
        text_ = text_.replace(phrase, rep)
    text_ = " ".join(SINGLEWORD_DICT.get(tok, tok) for tok in text_.split())
    text_ = REPEATED_CHAR_PATTERN.sub(r"\1\1", text_)
    text_ = PUNCT_PATTERN.sub(" ", text_)
    return MULTISPACE_PATTERN.sub(" ", text_).strip()


@st.cache_resource(show_spinner="Memuat model IndoBERTweet...")
def load_indobertweet_model():
    """Load model & tokenizer dari Hugging Face Hub (repo private).
    Nama repo bisa dioverride lewat env var INDOBERTWEET_MODEL_PATH.
    HF_TOKEN wajib diisi (di .env lokal, atau di Secrets Streamlit Cloud saat deploy)
    karena repo model-nya private."""
    model_repo = os.getenv("INDOBERTWEET_MODEL_PATH", "kolin12/indobertweet-beauty-final")
    hf_token = os.getenv("HF_TOKEN")

    if not hf_token:
        raise RuntimeError(
            "HF_TOKEN belum diisi di .env (atau Secrets saat deploy). "
            "Token ini diperlukan karena repo model Hugging Face bersifat private."
        )

    tokenizer = AutoTokenizer.from_pretrained(model_repo, token=hf_token)
    model = AutoModelForSequenceClassification.from_pretrained(model_repo, token=hf_token)
    model.eval()
    return tokenizer, model


LABEL_MAP = {0: "positif", 1: "netral", 2: "negatif"}


def predict_sentiment(texts: list, batch_size: int = 32) -> list:
    tokenizer, model = load_indobertweet_model()
    results = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        enc = tokenizer(batch, padding=True, truncation=True, max_length=128, return_tensors="pt")
        with torch.no_grad():
            logits = model(**enc).logits
            probs = torch.softmax(logits, dim=-1)
            preds = probs.argmax(dim=-1)
        for p, prob in zip(preds.tolist(), probs.tolist()):
            results.append({"label": LABEL_MAP.get(p, "netral"), "score": max(prob)})
    return results


def hitung_reputasi_channel(labels: list) -> float:
    if not labels:
        return 0.0
    n = len(labels)
    pos = sum(1 for l in labels if l == "positif")
    neg = sum(1 for l in labels if l == "negatif")
    return (pos - neg) / n