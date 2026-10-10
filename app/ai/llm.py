import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

api_key = os.getenv("GROQ_API_KEY", "").strip()

if not api_key:
    raise RuntimeError("GROQ_API_KEY is missing.")

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    groq_api_key=api_key,
    timeout=60,
    max_retries=1,
)