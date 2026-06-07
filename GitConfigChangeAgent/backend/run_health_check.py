from fastapi.testclient import TestClient

from app.main import app


def main():
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    print("Health check passed")


if __name__ == "__main__":
    main()
