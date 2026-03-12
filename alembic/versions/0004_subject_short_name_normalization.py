"""Normalize subject naming with short_name.

Revision ID: 0004_subject_short_name_normalization
Revises: 0003_lesson_plan_links
Create Date: 2026-03-12 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_subject_short_name_normalization"
down_revision: str | None = "0003_lesson_plan_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("subjects") as batch_op:
        batch_op.add_column(sa.Column("short_name", sa.String(length=255), nullable=True))

    op.execute("UPDATE subjects SET short_name = name WHERE short_name IS NULL")

    with op.batch_alter_table("subjects") as batch_op:
        batch_op.create_unique_constraint(
            op.f("uq_subjects_short_name"),
            ["short_name"],
        )


def downgrade() -> None:
    with op.batch_alter_table("subjects") as batch_op:
        batch_op.drop_constraint(op.f("uq_subjects_short_name"), type_="unique")
        batch_op.drop_column("short_name")
