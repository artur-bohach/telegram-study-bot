"""Add schedule lesson number to subject plan items.

Revision ID: 0005_subject_plan_schedule_lesson_number
Revises: 0004_subject_short_name_normalization
Create Date: 2026-03-13 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005_subject_plan_schedule_lesson_number"
down_revision: str | None = "0004_subject_short_name_normalization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("subject_plan_items") as batch_op:
        batch_op.add_column(sa.Column("schedule_lesson_number", sa.Integer(), nullable=True))
        batch_op.create_index(
            "ix_subject_plan_items_schedule_lookup",
            ["subject_id", "lesson_kind", "topic_number", "schedule_lesson_number"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("subject_plan_items") as batch_op:
        batch_op.drop_index("ix_subject_plan_items_schedule_lookup")
        batch_op.drop_column("schedule_lesson_number")
