from __future__ import annotations

from typing import Any

# ── Loan-program document requirements ───────────────────────────────────────
# Config-driven: extend this dict from a database or YAML in production.

_PROGRAM_REQUIREMENTS: dict[str, dict[str, list[str]]] = {
    "CONV_30": {
        "W2": ["W2", "PAYSTUB", "BANK_STATEMENT", "DRIVERS_LICENSE"],
        "SELF_EMPLOYED": [
            "FORM_1099",
            "SCHEDULE_C",
            "TAX_RETURN",
            "PROFIT_LOSS",
            "BANK_STATEMENT",
            "DRIVERS_LICENSE",
        ],
        "DEFAULT": ["W2", "PAYSTUB", "BANK_STATEMENT", "DRIVERS_LICENSE"],
    },
    "FHA_30": {
        "W2": [
            "W2",
            "PAYSTUB",
            "BANK_STATEMENT",
            "TAX_RETURN",
            "DRIVERS_LICENSE",
            "SOCIAL_SECURITY_CARD",
        ],
        "SELF_EMPLOYED": [
            "FORM_1099",
            "SCHEDULE_C",
            "TAX_RETURN",
            "PROFIT_LOSS",
            "BANK_STATEMENT",
            "DRIVERS_LICENSE",
            "SOCIAL_SECURITY_CARD",
        ],
        "DEFAULT": [
            "W2",
            "PAYSTUB",
            "BANK_STATEMENT",
            "TAX_RETURN",
            "DRIVERS_LICENSE",
            "SOCIAL_SECURITY_CARD",
        ],
    },
    "JUMBO_30": {
        "W2": [
            "W2",
            "PAYSTUB",
            "BANK_STATEMENT",
            "TAX_RETURN",
            "PURCHASE_CONTRACT",
            "APPRAISAL",
            "TITLE_COMMITMENT",
            "HOMEOWNERS_INSURANCE",
            "DRIVERS_LICENSE",
        ],
        "DEFAULT": [
            "W2",
            "PAYSTUB",
            "BANK_STATEMENT",
            "TAX_RETURN",
            "PURCHASE_CONTRACT",
            "APPRAISAL",
            "DRIVERS_LICENSE",
        ],
    },
}

_DEFAULT_REQUIREMENTS = ["W2", "PAYSTUB", "BANK_STATEMENT", "DRIVERS_LICENSE"]

_DOC_LABELS: dict[str, dict[str, str]] = {
    "W2": {"label": "W-2 Wage Statement", "description": "Most recent 2 years of W-2 forms"},
    "FORM_1099": {"label": "1099 Form(s)", "description": "All 1099 forms from the most recent year"},
    "PAYSTUB": {"label": "Pay Stubs", "description": "Most recent 30-day pay stubs"},
    "BANK_STATEMENT": {"label": "Bank Statements", "description": "Most recent 2-3 months of all asset accounts"},
    "TAX_RETURN": {"label": "Federal Tax Returns", "description": "Most recent 2 years of signed federal tax returns"},
    "SCHEDULE_C": {"label": "Schedule C", "description": "Most recent 2 years of Schedule C (self-employed)"},
    "PROFIT_LOSS": {"label": "Profit & Loss Statement", "description": "YTD P&L prepared by a CPA"},
    "PURCHASE_CONTRACT": {"label": "Purchase Contract", "description": "Fully executed purchase agreement"},
    "APPRAISAL": {"label": "Appraisal Report", "description": "Full URAR appraisal from a licensed appraiser"},
    "TITLE_COMMITMENT": {"label": "Title Commitment", "description": "Preliminary title insurance commitment"},
    "HOMEOWNERS_INSURANCE": {"label": "Homeowners Insurance", "description": "Declarations page from hazard insurance"},
    "DRIVERS_LICENSE": {"label": "Government-Issued ID", "description": "Valid driver's license or passport"},
    "SOCIAL_SECURITY_CARD": {"label": "Social Security Card", "description": "Original or certified copy"},
    "GIFT_LETTER": {"label": "Gift Letter", "description": "Signed gift letter if using gift funds"},
}
