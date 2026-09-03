import requests

BASE_URL = "http://127.0.0.1:8000"

def get_dashboard_stats():
    """Fetch dashboard statistics from the backend."""

    try:
        response = requests.get(f"{BASE_URL}/dashboard/stats")
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        return {
            "error": str(e)
        }
        
def get_all_queries():
    """Fetch all freight queries."""

    try:
        response = requests.get(f"{BASE_URL}/queries")
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
        )

        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        return {
            "error": str(e)
        }                