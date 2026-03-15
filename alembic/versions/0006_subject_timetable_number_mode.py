"""Add timetable number mode to subjects.

Revision ID: 0006_subject_timetable_number_mode
Revises: 0005_subject_plan_schedule_lesson_number
Create Date: 2026-03-13 00:00:01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006_subject_timetable_number_mode"
down_revision: str | None = "0005_subject_plan_schedule_lesson_number"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("subjects") as batch_op:
        batch_op.add_column(sa.Column("timetable_number_mode", sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("subjects") as batch_op:
        batch_op.drop_column("timetable_number_mode")
