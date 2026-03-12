"""Add subject plan storage tables.

Revision ID: 0002_subject_plan_storage
Revises: 0001_initial_schema
Create Date: 2026-03-12 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_subject_plan_storage"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    plan_lesson_kind = sa.Enum(
        "lecture",
        "seminar",
        "practical",
        name="planlessonkind",
        native_enum=False,
        length=20,
    )

    op.create_table(
        "subject_plan_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("lesson_kind", plan_lesson_kind, nullable=False),
        sa.Column("topic_number", sa.Integer(), nullable=False),
        sa.Column("session_number", sa.Integer(), nullable=False),
        sa.Column("topic_title", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_subject_plan_items_subject_id_subjects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subject_plan_items")),
        sa.UniqueConstraint(
            "subject_id",
            "lesson_kind",
            "topic_number",
            "session_number",
            name="uq_subject_plan_items_subject_lesson_identity",
        ),
    )
    op.create_index(
        "ix_subject_plan_items_subject_lookup",
        "subject_plan_items",
        ["subject_id", "lesson_kind", "topic_number", "session_number"],
        unique=False,
    )

    op.create_table(
        "plan_item_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_item_id", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_item_id"],
            ["subject_plan_items.id"],
            name=op.f("fk_plan_item_questions_plan_item_id_subject_plan_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_item_questions")),
        sa.UniqueConstraint(
            "plan_item_id",
            "order_index",
            name="uq_plan_item_questions_plan_item_order",
        ),
    )

    op.create_table(
        "plan_item_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_item_id", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("task_number", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["plan_item_id"],
            ["subject_plan_items.id"],
            name=op.f("fk_plan_item_assignments_plan_item_id_subject_plan_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_item_assignments")),
        sa.UniqueConstraint(
            "plan_item_id",
            "order_index",
            name="uq_plan_item_assignments_plan_item_order",
        ),
    )


def downgrade() -> None:
    op.drop_table("plan_item_assignments")
    op.drop_table("plan_item_questions")
    op.drop_index("ix_subject_plan_items_subject_lookup", table_name="subject_plan_items")
    op.drop_table("subject_plan_items")
