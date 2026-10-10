import requests
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

def get_dashboard_stats():
    """Fetch dashboard statistics from the backend."""

    try:
        response = requests.get(f"{BASE_URL}/dashboard/stats", timeout=(5, 20))
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        return {
            "error": str(e)
        }
        
def get_all_queries():
    """Fetch all freight queries."""

    try:
        response = requests.get(f"{BASE_URL}/queries", timeout=(5, 20))
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        return {
            "error": str(e)
        }
        
        
def chat_with_ai(message: str):
    try:
        response = requests.post(
            f"{BASE_URL}/ai/chat",
            json={"message": message},
            timeout=(5, 120),
        )

        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        return {
            "error": str(e)
        }                
        
def procurement_api(method, path, payload=None):
    headers={}
    token=os.getenv("PROCUREMENT_API_TOKEN", "").strip()
    if token:
        headers["X-Procurement-Token"]=token
    try:
        response=requests.request(method, f"{BASE_URL}/procurement{path}",
            json=payload, headers=headers, timeout=(10, 600))
        if not response.ok:
            try:
                detail=response.json().get("detail", "Backend request failed.")
            except ValueError:
                detail=f"Backend returned HTTP {response.status_code}."
            return {"error": str(detail)}
        if path.endswith("/eml"):
            return {"content": response.content}
        return response.json()
    except requests.Timeout:
        return {"error": "Request timed out. Refresh saved requests before resubmitting; planning may still be running."}
    except requests.RequestException:
        return {"error": "Cannot reach backend. Check the backend terminal and API_BASE_URL."}
    except ValueError:
        return {"error": "Backend returned invalid JSON."}
