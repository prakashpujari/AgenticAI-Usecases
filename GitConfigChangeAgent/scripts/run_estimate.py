import requests
import json

BASE = "http://127.0.0.1:8000"

def main():
    try:
        t_resp = requests.post(f"{BASE}/dev/auth/token", timeout=10)
        t_resp.raise_for_status()
        token = t_resp.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "query": "database.host",
            "scope": {"group_ids": [], "project_ids": [1]}
        }
        r = requests.post(f"{BASE}/api/v1/estimate", json=payload, headers=headers, timeout=30)
        print(r.status_code)
        try:
            print(json.dumps(r.json(), indent=2))
        except Exception:
            print(r.text)
    except Exception as e:
        print('ERROR', type(e).__name__, e)

if __name__ == '__main__':
    main()
