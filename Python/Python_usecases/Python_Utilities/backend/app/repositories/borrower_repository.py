from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.engine import get_session_factory
from app.infrastructure.database.models import BorrowerORM
from app.models.domain.borrower import (
    BorrowerProfile,
    IncomeType,
    LoanPurpose,
    PropertyType,
    RiskFlag,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _orm_to_domain(row: BorrowerORM) -> BorrowerProfile:
    risk_flags = [RiskFlag(**f) for f in (row.risk_flags or [])]
    return BorrowerProfile(
        id=row.id,
        loan_number=row.loan_number,
        first_name=row.first_name,
        last_name=row.last_name,
        ssn_last4=row.ssn_last4,
        date_of_birth=row.date_of_birth,
        email=row.email,
        phone=row.phone,
        loan_amount=row.loan_amount,
        property_value=row.property_value,
        loan_purpose=LoanPurpose(row.loan_purpose),
        property_type=PropertyType(row.property_type),
        annual_income=row.annual_income,
        income_type=IncomeType(row.income_type),
        monthly_debts=row.monthly_debts,
        credit_score=row.credit_score,
        dti_ratio=row.dti_ratio,
        ltv_ratio=row.ltv_ratio,
        risk_flags=risk_flags,
        loan_program=row.loan_program,
        loan_officer=row.loan_officer,
        extra=row.extra or {},
    )


def _domain_to_orm(profile: BorrowerProfile) -> BorrowerORM:
    return BorrowerORM(
        id=profile.id,
        loan_number=profile.loan_number,
        first_name=profile.first_name,
        last_name=profile.last_name,
        ssn_last4=profile.ssn_last4,
        date_of_birth=profile.date_of_birth,
        email=profile.email,
        phone=profile.phone,
        loan_amount=profile.loan_amount,
        property_value=profile.property_value,
        loan_purpose=profile.loan_purpose.value,
        property_type=profile.property_type.value,
        annual_income=profile.annual_income,
        income_type=profile.income_type.value,
        monthly_debts=profile.monthly_debts,
        credit_score=profile.credit_score,
        dti_ratio=profile.dti_ratio,
        ltv_ratio=profile.ltv_ratio,
        risk_flags=[f.model_dump() for f in profile.risk_flags],
        loan_program=profile.loan_program,
        loan_officer=profile.loan_officer,
        extra=profile.extra,
    )


# ── Repository ────────────────────────────────────────────────────────────────

class BorrowerRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def get_by_id(self, entity_id: str) -> BorrowerProfile | None:
        async with self._sf() as session:
            row = await session.get(BorrowerORM, entity_id)
            return _orm_to_domain(row) if row else None

    async def get_by_loan_number(self, loan_number: str) -> BorrowerProfile | None:
        async with self._sf() as session:
            result = await session.execute(
                select(BorrowerORM).where(BorrowerORM.loan_number == loan_number)
            )
            row = result.scalar_one_or_none()
            return _orm_to_domain(row) if row else None

    async def search(
        self,
        *,
        loan_number: str | None = None,
        last_name: str | None = None,
        ssn_last4: str | None = None,
        first_name: str | None = None,
    ) -> list[BorrowerProfile]:
        async with self._sf() as session:
            stmt = select(BorrowerORM)
            conditions = []
            if loan_number:
                conditions.append(BorrowerORM.loan_number.ilike(f"%{loan_number}%"))
            if last_name:
                conditions.append(BorrowerORM.last_name.ilike(f"%{last_name}%"))
            if ssn_last4:
                conditions.append(BorrowerORM.ssn_last4 == ssn_last4)
            if first_name:
                conditions.append(BorrowerORM.first_name.ilike(f"%{first_name}%"))
            if not conditions:
                return []
            stmt = stmt.where(or_(*conditions))
            result = await session.execute(stmt)
            return [_orm_to_domain(row) for row in result.scalars().all()]

    async def save(self, profile: BorrowerProfile) -> BorrowerProfile:
        async with self._sf() as session:
            existing = await session.get(BorrowerORM, profile.id)
            if existing:
                orm_obj = _domain_to_orm(profile)
                for col in BorrowerORM.__table__.columns.keys():
                    setattr(existing, col, getattr(orm_obj, col))
                orm_obj = existing
            else:
                orm_obj = _domain_to_orm(profile)
                session.add(orm_obj)
            await session.commit()
            await session.refresh(orm_obj)
            return _orm_to_domain(orm_obj)

    async def delete(self, entity_id: str) -> bool:
        async with self._sf() as session:
            row = await session.get(BorrowerORM, entity_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def count(self) -> int:
        async with self._sf() as session:
            result = await session.execute(select(func.count()).select_from(BorrowerORM))
            return result.scalar_one()


# ── Dependency ────────────────────────────────────────────────────────────────

_borrower_repo: BorrowerRepository | None = None


def get_borrower_repository() -> BorrowerRepository:
    global _borrower_repo
    if _borrower_repo is None:
        _borrower_repo = BorrowerRepository(get_session_factory())
    return _borrower_repo
