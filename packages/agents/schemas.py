"""Pydantic v2-scheman för agent-pipelinen.

Varje agents output-schema är BÅDE databaskontraktet OCH den structured-output-spec
som skickas till LLM:en. Därför är Field(description=...) inte kommentarer — de matas
in i modellen som JSON-schema och ska skrivas som instruktioner.

Konventioner:
  * Enums/Literal för alla kategorifält → normaliserad output utan efterbearbetning.
  * min/max_length på listor → hindrar tomma svar och översvämmande output.
  * Echo-fält (epic_title, story_role) → binder fan-out/cross-agent-output till rätt rad.
  * Deterministiska värden (kapacitet) beräknas i kod, inte av modellen.
  * "Draft"-scheman är agent-output, INTE DB-rader. Noden mappar Draft → SQLAlchemy
    och sätter id, project_id, order, board_order på servern. Modellen genererar
    aldrig primärnycklar eller ordningsfält.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# --------------------------------------------------------------------------- #
# 0. Delade typer & enums
# --------------------------------------------------------------------------- #


class Priority(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class TaskType(str, Enum):
    backend = "backend"
    frontend = "frontend"
    test = "test"
    infra = "infra"


class Severity(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


# Fibonacci story points — tvinga modellen till giltiga estimat
StoryPoints = Literal[1, 2, 3, 5, 8, 13]


# --------------------------------------------------------------------------- #
# 1. Input — ProjectBrief (pipelinens enda externa input, cache-kandidat)
# --------------------------------------------------------------------------- #


class ProjectBrief(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(
        ..., min_length=10, description="Fri beskrivning av produktidén."
    )
    target_audience: str | None = Field(
        None, description="Målgrupp, t.ex. 'privatpersoner och hantverkare'."
    )
    business_goals: str | None = Field(
        None, description="Affärsmål, t.ex. 'ta 5% av lokalmarknaden inom 12 mån'."
    )
    budget: str | None = None
    timeframe: str | None = Field(None, description="T.ex. 'MVP inom 3 månader'.")


# --------------------------------------------------------------------------- #
# 2. Discovery Agent → DiscoveryOutput
# --------------------------------------------------------------------------- #


class CoreFeature(BaseModel):
    name: str = Field(..., description="Kort namn, t.ex. 'Bokning'.")
    rationale: str = Field(..., description="Varför funktionen behövs för målgruppen.")


class DiscoveryOutput(BaseModel):
    overview: str = Field(..., description="1–2 meningars sammanfattning av produkten.")
    domain: str = Field(
        ..., description="Domän/bransch, t.ex. 'marknadsplats för tjänstebokning'."
    )
    target_audience: str
    core_features: list[CoreFeature] = Field(..., min_length=3, max_length=10)
    functional_requirements: list[str] = Field(..., min_length=3)
    out_of_scope: list[str] = Field(
        default_factory=list,
        description="Vad som uttryckligen INTE ingår i MVP — viktigt för scope-kontroll.",
    )
    key_risks: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# 3. Product Manager Agent → ProductPlan (roadmap + epics i ett anrop)
# --------------------------------------------------------------------------- #


class RoadmapPhase(BaseModel):
    phase: int = Field(..., ge=1, description="1=MVP, 2=Marknadsplats, 3=Tillväxt ...")
    title: str
    summary: str
    feature_names: list[str] = Field(
        ..., description="Funktioner som hör till fasen (refererar core_features-namn)."
    )


class EpicDraft(BaseModel):
    title: str
    description: str
    priority: Priority
    business_value: str = Field(..., description="Varför detta epic skapar värde.")
    phase: int = Field(..., ge=1, description="Vilken roadmap-fas epicet hör till.")


class ProductPlan(BaseModel):
    roadmap: list[RoadmapPhase] = Field(..., min_length=1, max_length=5)
    epics: list[EpicDraft] = Field(..., min_length=3, max_length=15)

    @field_validator("epics")
    @classmethod
    def epics_reference_existing_phase(cls, epics, info):
        roadmap = info.data.get("roadmap")
        if roadmap:
            phases = {p.phase for p in roadmap}
            for e in epics:
                if e.phase not in phases:
                    raise ValueError(
                        f"Epic '{e.title}' refererar fas {e.phase} som saknas i roadmap."
                    )
        return epics


# --------------------------------------------------------------------------- #
# 4. Solution Architect Agent → ArchitectureDraft
# --------------------------------------------------------------------------- #


class StackChoice(BaseModel):
    layer: str = Field(..., description="T.ex. 'frontend', 'backend', 'database'.")
    technology: str
    rationale: str


class DataEntity(BaseModel):
    name: str
    fields: list[str] = Field(
        ..., description="Fältnamn med typ, t.ex. 'id: UUID'."
    )
    relations: list[str] = Field(
        default_factory=list,
        description="T.ex. 'belongs_to User', 'has_many Booking'.",
    )


class ApiEndpoint(BaseModel):
    method: Literal["GET", "POST", "PATCH", "PUT", "DELETE"]
    path: str
    purpose: str


class ArchitectureDraft(BaseModel):
    stack: list[StackChoice] = Field(..., min_length=3)
    data_model: list[DataEntity] = Field(..., min_length=2)
    api_design: list[ApiEndpoint] = Field(..., min_length=3)
    rationale: str = Field(..., description="Övergripande motivering av arkitekturen.")


# --------------------------------------------------------------------------- #
# 5. Engineering Agent → EpicBreakdown (körs per epic, parallell fan-out)
# --------------------------------------------------------------------------- #


class TaskDraft(BaseModel):
    title: str = Field(
        ..., description="Konkret utvecklingsuppgift, t.ex. 'Skapa Booking API endpoint'."
    )
    description: str | None = None
    type: TaskType
    estimate: StoryPoints = Field(..., description="Story points (Fibonacci).")


class StoryDraft(BaseModel):
    role: str = Field(..., description="'Som <roll>', t.ex. 'kund'.")
    want: str = Field(..., description="'vill jag kunna ...'.")
    so_that: str = Field(..., description="'så att ...'.")
    acceptance_criteria: list[str] = Field(
        ..., min_length=1, description="Testbara villkor i Given/When/Then-stil."
    )
    tasks: list[TaskDraft] = Field(..., min_length=1, max_length=12)


class EpicBreakdown(BaseModel):
    epic_title: str = Field(
        ..., description="Echo av epicet — binder outputen till rätt epic."
    )
    stories: list[StoryDraft] = Field(..., min_length=1, max_length=8)


# --------------------------------------------------------------------------- #
# 6. Scrum Master Agent → SprintPlan (efter Engineering; kräver estimat)
# --------------------------------------------------------------------------- #


class SprintInput(BaseModel):
    team_size: int = Field(..., ge=1, le=20)
    sprint_length_weeks: int = Field(2, ge=1, le=4)
    velocity_per_dev: int = Field(
        8, description="Antagna story points per utvecklare per sprint."
    )

    @property
    def capacity_points(self) -> int:
        """Deterministisk kapacitet — beräknas i kod, matas in i prompten."""
        return self.team_size * self.velocity_per_dev


class SprintDraft(BaseModel):
    name: str = Field(..., description="T.ex. 'Sprint 1'.")
    goal: str
    capacity_points: int = Field(..., ge=1)
    task_titles: list[str] = Field(
        ...,
        description="Tasks (per titel) som planeras in — summan ≤ capacity_points.",
    )


class SprintPlan(BaseModel):
    sprints: list[SprintDraft] = Field(..., min_length=1)

    @field_validator("sprints")
    @classmethod
    def sequentially_named(cls, sprints):
        for i, s in enumerate(sprints, start=1):
            if str(i) not in s.name:
                raise ValueError(
                    f"Sprint {i} ska refereras i namnet, fick '{s.name}'"
                )
        return sprints


# --------------------------------------------------------------------------- #
# 7. QA Agent → TestPlan
# --------------------------------------------------------------------------- #


class TestCase(BaseModel):
    story_role: str = Field(..., description="Bind till story via dess roll/titel.")
    title: str
    type: Literal["unit", "integration", "e2e"]
    steps: list[str]
    expected: str


class TestPlan(BaseModel):
    strategy: str = Field(..., description="Övergripande teststrategi för projektet.")
    test_cases: list[TestCase] = Field(..., min_length=1)


# --------------------------------------------------------------------------- #
# 8. Health Agent → HealthReport (körs sist, ser hela bilden)
# --------------------------------------------------------------------------- #


class RiskDraft(BaseModel):
    title: str
    description: str
    severity: Severity
    affected_epics: list[str] = Field(
        default_factory=list, description="Epic-titlar som risken påverkar."
    )
    recommendation: str = Field(
        ..., description="Konkret åtgärd, t.ex. 'Flytta till Sprint 4'."
    )


class HealthReport(BaseModel):
    summary: str
    risks: list[RiskDraft] = Field(default_factory=list)
    overloaded_sprints: list[str] = Field(
        default_factory=list,
        description="Sprintnamn där inplanerade points överstiger kapacitet.",
    )


# --------------------------------------------------------------------------- #
# 9. Delad pipeline-state
# --------------------------------------------------------------------------- #


class AgentState(BaseModel):
    project_id: UUID
    run_id: UUID
    brief: ProjectBrief
    sprint_input: SprintInput

    discovery: DiscoveryOutput | None = None
    plan: ProductPlan | None = None
    architecture: ArchitectureDraft | None = None
    breakdowns: list[EpicBreakdown] = Field(default_factory=list)
    sprint_plan: SprintPlan | None = None
    test_plan: TestPlan | None = None
    health: HealthReport | None = None

    errors: list[str] = Field(default_factory=list)
