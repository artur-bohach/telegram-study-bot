"""Add lesson to subject plan links.

Revision ID: 0003_lesson_plan_links
Revises: 0002_subject_plan_storage
Create Date: 2026-03-12 00:00:01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_lesson_plan_links"
down_revision: str | None = "0002_subject_plan_storage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.add_column(sa.Column("subject_plan_item_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            op.f("ix_lessons_subject_plan_item_id"),
            ["subject_plan_item_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            op.f("fk_lessons_subject_plan_item_id_subject_plan_items"),
            "subject_plan_items",
            ["subject_plan_item_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_lessons_subject_plan_item_id_subject_plan_items"),
            type_="foreignkey",
        )
        batch_op.drop_index(op.f("ix_lessons_subject_plan_item_id"))
        batch_op.drop_column("subject_plan_item_id")
