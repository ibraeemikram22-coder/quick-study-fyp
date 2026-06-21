"""Manual Gemini API test — same REST path as live modules."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from modules.gemini_config import gemini_api_keys, gemini_model_chain, gemini_post, gemini_url

keys = gemini_api_keys()
if not keys:
    sys.exit("Set GEMINI_API_KEY in backend/.env")

model = gemini_model_chain()[0]
res = gemini_post(
    gemini_url(model),
    keys[0],
    {"contents": [{"parts": [{"text": "Reply with one word: OK"}]}]},
    timeout=30,
)

print("HTTP status:", res.status_code)
if not res.ok:
    print(res.text[:400])
    sys.exit("Gemini test FAILED — check API key in .env or create a new key in AI Studio")

data = res.json()
parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts") or []
text = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in parts).strip()
print("Reply:", text or "(empty)")
print("Gemini test OK")
