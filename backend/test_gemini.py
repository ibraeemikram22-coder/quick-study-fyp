"""Manual Gemini API test — uses GEMINI_API_KEY from backend/.env only."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
if not api_key:
    raise SystemExit("Set GEMINI_API_KEY in backend/.env")

from google import genai

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Reply with one word: OK",
)

print(response.text)
