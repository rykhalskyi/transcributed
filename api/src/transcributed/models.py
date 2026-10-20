from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from transcributed.enums import ProjectStatus, RunStatus, TaskStatus


def enum_type(enum_cls: type[Enum]) -> SAEnum:
    return SAEnum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [member.value for member in members],
        length=32,
    )


project_status_type = enum_type(ProjectStatus)
run_status_type = enum_type(RunStatus)
task_status_type = enum_type(TaskStatus)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Video(Base, TimestampMixin):
    __tablename__ = "videos"
    __table_args__ = (
        UniqueConstraint(
            "path",
            "size_bytes",
            "mtime",
            name="uq_videos_path_size_mtime",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mtime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        project_status_type,
        nullable=False,
        default=ProjectStatus.DRAFT,
        server_default=text("'draft'"),
    )
    defaults: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    items: Mapped[list[ProjectItem]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    runs: Mapped[list[Run]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ProjectItem(Base, TimestampMixin):
    __tablename__ = "project_items"
    __table_args__ = (
        UniqueConstraint("project_id", "video_id", name="uq_project_items_project_video"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("videos.id"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    spec_overrides: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    included: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    project: Mapped[Project] = relationship(back_populates="items")
    video: Mapped[Video] = relationship(lazy="joined")


class Run(Base, TimestampMixin):
    __tablename__ = "runs"
    __table_args__ = (
        Index(
            "uq_runs_active_project",
            "project_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[RunStatus] = mapped_column(
        run_status_type,
        nullable=False,
        default=RunStatus.QUEUED,
        server_default=text("'queued'"),
    )
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="runs")
    tasks: Mapped[list[Task]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("run_id", "project_item_id", name="uq_tasks_run_item"),
        Index("ix_tasks_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("project_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("videos.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[TaskStatus] = mapped_column(
        task_status_type,
        nullable=False,
        default=TaskStatus.QUEUED,
        server_default=text("'queued'"),
    )
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default=text("3"),
    )
    enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_pod: Mapped[str | None] = mapped_column(String(253), nullable=True)
    worker_node: Mapped[str | None] = mapped_column(String(253), nullable=True)
    progress: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[Run] = relationship(back_populates="tasks")
    project_item: Mapped[ProjectItem] = relationship()
    video: Mapped[Video] = relationship()
    artifacts: Mapped[list[Artifact]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class Artifact(Base, TimestampMixin):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("task_id", "format", name="uq_artifacts_task_format"),)

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    task: Mapped[Task] = relationship(back_populates="artifacts")
