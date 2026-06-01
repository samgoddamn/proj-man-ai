"""API-DTO:er (Pydantic v2) — request- och responsmodeller för HTTP-lagret.

Skilda från agent-schemana (packages/agents/schemas.py, = LLM-output) och från
SQLAlchemy-modellerna (models.py, = persistens). Alla Out-modeller har
from_attributes=True så de kan serialiseras direkt från ORM-objekt.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import ProjectStatus, TaskStatus


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=120)
    org_name: str | None = Field(None, max_length=120)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(_Out):
    id: uuid.UUID
    email: str
    name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --------------------------------------------------------------------------- #
# Projekt
# --------------------------------------------------------------------------- #


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=10)
    target_audience: str | None = None
    business_goals: str | None = None
    budget: str | None = None
    timeframe: str | None = None


class ProjectOut(_Out):
    id: uuid.UUID
    name: str
    description: str
    target_audience: str | None
    business_goals: str | None
    budget: str | None
    timeframe: str | None
    status: ProjectStatus
    created_at: datetime


# --------------------------------------------------------------------------- #
# Generering
# --------------------------------------------------------------------------- #


class GenerateRequest(BaseModel):
    team_size: int = Field(3, ge=1, le=20)
    sprint_length_weeks: int = Field(2, ge=1, le=4)
    velocity_per_dev: int = Field(8, ge=1, le=40)


class GenerateAccepted(BaseModel):
    run_id: uuid.UUID
    status: str = "queued"


# --------------------------------------------------------------------------- #
# Full projekt-hierarki (GET /projects/{id})
# --------------------------------------------------------------------------- #


class TaskOut(_Out):
    id: uuid.UUID
    story_id: uuid.UUID
    sprint_id: uuid.UUID | None
    title: str
    description: str | None
    type: str
    status: TaskStatus
    estimate: int | None
    board_order: float


class StoryOut(_Out):
    id: uuid.UUID
    role: str
    want: str
    so_that: str
    acceptance_criteria: list
    order: int
    tasks: list[TaskOut]


class EpicOut(_Out):
    id: uuid.UUID
    roadmap_id: uuid.UUID | None
    title: str
    description: str | None
    priority: str
    business_value: str | None
    order: int
    stories: list[StoryOut]


class RoadmapOut(_Out):
    id: uuid.UUID
    phase: int
    title: str
    summary: str | None
    order: int


class SprintOut(_Out):
    id: uuid.UUID
    name: str
    goal: str | None
    capacity_points: int | None
    start_date: date | None
    end_date: date | None
    order: int


class ArchitectureOut(_Out):
    stack: list
    data_model: list
    api_design: list
    rationale: str | None


class RiskOut(_Out):
    id: uuid.UUID
    title: str
    description: str | None
    severity: str
    affected_epics: list
    recommendation: str | None


class ProjectDetail(ProjectOut):
    roadmaps: list[RoadmapOut] = []
    epics: list[EpicOut] = []
    sprints: list[SprintOut] = []
    risks: list[RiskOut] = []
    architecture: ArchitectureOut | None = None


# --------------------------------------------------------------------------- #
# Kanban
# --------------------------------------------------------------------------- #


class TaskPatch(BaseModel):
    status: TaskStatus | None = None
    board_order: float | None = None
    sprint_id: uuid.UUID | None = None


class BoardColumn(_Out):
    status: TaskStatus
    tasks: list[TaskOut]


class BoardOut(BaseModel):
    columns: list[BoardColumn]
