"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-01

Speglar apps/api/app/models.py. Skapandeordningen respekterar FK-beroenden:
sprints före tasks (tasks.sprint_id), epics före user_stories, user_stories före tasks.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)

project_status = sa.Enum(
    "draft", "generating", "ready", "failed", name="projectstatus"
)
task_status = sa.Enum(
    "backlog", "todo", "in_progress", "review", "done", name="taskstatus"
)
run_status = sa.Enum(
    "queued", "running", "succeeded", "failed", name="runstatus"
)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("org_id", UUID, nullable=True, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("business_goals", sa.Text(), nullable=True),
        sa.Column("budget", sa.String(120), nullable=True),
        sa.Column("timeframe", sa.String(120), nullable=True),
        sa.Column("status", project_status, nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "roadmaps",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("phase", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "epics",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("roadmap_id", UUID, sa.ForeignKey("roadmaps.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("business_value", sa.Text(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "sprints",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("capacity_points", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "user_stories",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("epic_id", UUID, sa.ForeignKey("epics.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(120), nullable=False),
        sa.Column("want", sa.Text(), nullable=False),
        sa.Column("so_that", sa.Text(), nullable=False),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "tasks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("story_id", UUID, sa.ForeignKey("user_stories.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sprint_id", UUID, sa.ForeignKey("sprints.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("status", task_status, nullable=False, server_default="backlog"),
        sa.Column("estimate", sa.Integer(), nullable=True),
        sa.Column("board_order", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "architecture",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("stack", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("data_model", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("api_design", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("rationale", sa.Text(), nullable=True),
    )

    op.create_table(
        "risks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("affected_epics", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("recommendation", sa.Text(), nullable=True),
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", run_status, nullable=False, server_default="queued"),
        sa.Column("current_agent", sa.String(40), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    for table in (
        "agent_runs", "risks", "architecture", "tasks", "user_stories",
        "sprints", "epics", "roadmaps", "projects",
    ):
        op.drop_table(table)
    for enum in (run_status, task_status, project_status):
        enum.drop(op.get_bind(), checkfirst=True)
