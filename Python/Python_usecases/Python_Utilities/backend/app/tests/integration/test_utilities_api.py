from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ── /api/v1/utilities/dti ─────────────────────────────────────────────────────

class TestDTIEndpoint:
    def test_valid_request_returns_200(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/utilities/dti",
            params={"loan_program": "CONV_30"},
            json={
                "gross_monthly_income": 10000,
                "monthly_debt_payments": 500,
                "proposed_monthly_payment": 2000,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "back_end_ratio" in data
        assert "passes_threshold" in data

    def test_back_end_calculation(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/utilities/dti",
            params={"loan_program": "CONV_30"},
            json={
                "gross_monthly_income": 10000,
                "monthly_debt_payments": 500,
                "proposed_monthly_payment": 2000,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert abs(data["back_end_ratio"] - 25.0) < 0.1

    def test_missing_income_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/utilities/dti",
            json={"monthly_debt_payments": 500, "proposed_monthly_payment": 2000},
        )
        assert resp.status_code == 422

    def test_unauthenticated_returns_401(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post(
            "/api/v1/utilities/dti",
            json={"gross_monthly_income": 10000, "monthly_debt_payments": 500, "proposed_monthly_payment": 2000},
        )
        assert resp.status_code == 401


# ── /api/v1/utilities/ltv ─────────────────────────────────────────────────────

class TestLTVEndpoint:
    def test_valid_request_returns_200(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/utilities/ltv",
            json={"loan_amount": 160000, "appraised_value": 200000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "ltv_ratio" in data
        assert abs(data["ltv_ratio"] - 80.0) < 0.1

    def test_pmi_required_flag(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/utilities/ltv",
            json={"loan_amount": 170000, "appraised_value": 200000},
        )
        assert resp.status_code == 200
        assert resp.json()["pmi_required"] is True

    def test_zero_appraised_value_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/utilities/ltv",
            json={"loan_amount": 160000, "appraised_value": 0},
        )
        assert resp.status_code in (400, 422)


# ── /api/v1/utilities/eligibility ─────────────────────────────────────────────

class TestEligibilityEndpoint:
    def test_eligible_borrower(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/utilities/eligibility",
            json={
                "loan_program": "CONV_30",
                "fico_score": 750,
                "dti": 35,
                "ltv": 80,
                "loan_amount": 300000,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["eligible"] is True
        assert data["failures"] == []

    def test_ineligible_fico(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/utilities/eligibility",
            json={
                "loan_program": "CONV_30",
                "fico_score": 580,
                "dti": 35,
                "ltv": 80,
                "loan_amount": 300000,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["eligible"] is False
        assert len(data["failures"]) > 0
