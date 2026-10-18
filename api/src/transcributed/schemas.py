from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from transcributed.enums import ProjectStatus, RunStatus, TaskStatus

Language = Literal["en", "ru", "de", "auto"]
OutputFormat = Literal["vtt", "json", "txt"]

DEFAULT_OUTPUT_FORMATS: list[OutputFormat] = ["txt"]


class ProjectDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Language = "auto"
    model: str = Field(default="small", min_length=1, max_length=50)
    output_formats: list[OutputFormat] = Field(
        default_factory=lambda: list(DEFAULT_OUTPUT_FORMATS),
        min_length=1,
    )
    max_attempts: int = Field(default=3, ge=1, le=10)

    @field_validator("output_formats")
    @classmethod
    def deduplicate_formats(cls, values: list[OutputFormat]) -> list[OutputFormat]:
        return list(dict.fromkeys(values))


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    defaults: ProjectDefaults = Field(default_factory=ProjectDefaults)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    defaults: ProjectDefaults | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    status: ProjectStatus
    defaults: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProjectItemInput(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    language: Language | None = None
    model: str | None = Field(default=None, min_length=1, max_length=50)


class ProjectItemsAddRequest(BaseModel):
    items: list[ProjectItemInput] = Field(min_length=1, max_length=500)


class ProjectItemResult(BaseModel):
    path: str
    accepted: bool
    created: bool = False
    item_id: UUID | None = None
    error: str | None = None


class ProjectItemsAddResponse(BaseModel):
    accepted: int
    rejected: int
    results: list[ProjectItemResult]


class ProjectItemRead(BaseModel):
    id: UUID
    project_id: UUID
    video_id: UUID
    path: str
    position: int
    included: bool
    spec_overrides: dict[str, Any] | None
    latest_task_status: TaskStatus | None = None
    latest_task_id: UUID | None = None


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    format: str
    filename: str
    content_type: str
    size_bytes: int | None
    created_at: datetime


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    project_item_id: UUID
    video_id: UUID
    status: TaskStatus
    spec: dict[str, Any]
    spec_hash: str
    attempts: int
    max_attempts: int
    enqueued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    artifacts: list[ArtifactRead] = Field(default_factory=list)


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    status: RunStatus
    spec: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunDetail(RunRead):
    tasks: list[TaskRead] = Field(default_factory=list)


class StartProjectResponse(BaseModel):
    run: RunRead
    task_ids: list[UUID]
    enqueued: int
    not_enqueued: int


class HealthResponse(BaseModel):
    status: str
