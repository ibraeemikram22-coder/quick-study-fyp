"""Shared Gemini model IDs."""
import os

DEFAULT_GEMINI_MODELS = (
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
)

RETRYABLE_STATUSES = {429, 500, 503, 504}
SKIP_MODEL_STATUSES = {404}


def gemini_model_chain(env_key="GEMINI_MODEL"):
    override = (os.getenv(env_key) or "").strip()
    if override:
        rest = [m for m in DEFAULT_GEMINI_MODELS if m != override]
        return (override,) + tuple(rest)
    return DEFAULT_GEMINI_MODELS


def gemini_url(model):
    return (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
