from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# These tests use `unauth_client` so auth middleware is actually exercised.

class TestLoginEndpoint:
    def test_valid_credentials_return_tokens(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post(
            "/api/v1/auth/login",
            json={"username": "underwriter1", "password": "Underwriter@123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_wrong_password_returns_401(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post(
            "/api/v1/auth/login",
            json={"username": "underwriter1", "password": "wrong"},
        )
        assert resp.status_code == 401

    def test_unknown_user_returns_401(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "Password@123"},
        )
        assert resp.status_code == 401

    def test_missing_fields_returns_422(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post("/api/v1/auth/login", json={"username": "underwriter1"})
        assert resp.status_code == 422


class TestMeEndpoint:
    def test_me_requires_auth(self, unauth_client: TestClient) -> None:
        resp = unauth_client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_returns_user_with_valid_token(self, unauth_client: TestClient) -> None:
        # First log in to get a real token
        login = unauth_client.post(
            "/api/v1/auth/login",
            json={"username": "underwriter1", "password": "Underwriter@123"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        resp = unauth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "underwriter1"
        assert "hashed_password" not in data

    def test_me_rejects_tampered_token(self, unauth_client: TestClient) -> None:
        resp = unauth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.fake.sig"},
        )
        assert resp.status_code == 401


class TestRefreshEndpoint:
    def test_refresh_returns_new_access_token(self, unauth_client: TestClient) -> None:
        login = unauth_client.post(
            "/api/v1/auth/login",
            json={"username": "underwriter1", "password": "Underwriter@123"},
        )
        refresh_token = login.json()["refresh_token"]

        resp = unauth_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()
