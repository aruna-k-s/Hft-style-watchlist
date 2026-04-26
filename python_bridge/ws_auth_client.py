import requests

def get_authorized_url(access_token: str) -> str:
    url = "https://api.upstox.com/v3/feed/market-data-feed/authorize"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    response = requests.get(url, headers=headers, timeout=5)

    if response.status_code != 200:
        raise Exception(f"WS auth failed: {response.text}")

    data = response.json()

    if data.get("status") != "success":
        raise Exception(f"Invalid response: {data}")

    wss_url = data["data"].get("authorized_redirect_uri")

    if not wss_url:
        raise Exception("Missing authorized_redirect_uri")

    return wss_url