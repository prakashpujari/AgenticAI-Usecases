from __future__ import annotations

from sqlalchemy import Column, Date, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.infrastructure.database.engine import Base


class BorrowerORM(Base):
    __tablename__ = "borrowers"

    id = Column(String, primary_key=True)
    loan_number = Column(String, unique=True, nullable=False, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False, index=True)
    ssn_last4 = Column(String(4), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    loan_amount = Column(Float, nullable=False)
    property_value = Column(Float, nullable=False)
    loan_purpose = Column(String, nullable=False)
    property_type = Column(String, nullable=False)

    annual_income = Column(Float, nullable=False)
    income_type = Column(String, nullable=False)
    monthly_debts = Column(Float, nullable=False)
    credit_score = Column(Integer, nullable=False)

    dti_ratio = Column(Float, nullable=True)
    ltv_ratio = Column(Float, nullable=True)

    loan_program = Column(String, nullable=True)
    loan_officer = Column(String, nullable=True)

    # Store risk_flags and extra as JSONB; fall back to Text for non-Postgres
    risk_flags = Column(JSONB, nullable=False, server_default="[]")
    extra = Column(JSONB, nullable=False, server_default="{}")
