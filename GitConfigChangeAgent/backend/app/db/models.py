from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON, Enum
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


class RunStatus(enum.Enum):
    PENDING = "PENDING"
    DISCOVERY = "DISCOVERY"
    PROPOSED = "PROPOSED"
    APPLIED = "APPLIED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CONFLICT = "CONFLICT"


class ConfigChangeRun(Base):
    __tablename__ = "config_change_runs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(128), nullable=False)
    config_type = Column(String(32), nullable=False)
    old_value = Column(Text, nullable=False)
    new_value = Column(Text, nullable=False)
    key_path = Column(String(256), nullable=True)
    scope = Column(JSON, nullable=False)
    mode = Column(String(32), nullable=False)
    branch_strategy = Column(String(64), nullable=False)
    open_merge_requests = Column(Integer, nullable=False, default=0)
    status = Column(Enum(RunStatus), nullable=False, default=RunStatus.PENDING)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    metrics = Column(JSON, nullable=True)
    evaluation = Column(JSON, nullable=True)
    audit = Column(JSON, nullable=True)


class FilePatch(Base):
    __tablename__ = "file_patches"

    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("config_change_runs.id"), nullable=False)
    project_id = Column(Integer, nullable=False)
    project_name = Column(String(256), nullable=False)
    file_path = Column(String(1024), nullable=False)
    file_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False)
    diff = Column(Text, nullable=False)
    llm_rationale = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    run = relationship("ConfigChangeRun", back_populates="patches")


ConfigChangeRun.patches = relationship("FilePatch", back_populates="run", cascade="all, delete-orphan")
