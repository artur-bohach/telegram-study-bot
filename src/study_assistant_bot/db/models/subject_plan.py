from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from study_assistant_bot.db.base import Base
from study_assistant_bot.enums import PlanLessonKind

if TYPE_CHECKING:
    from study_assistant_bot.db.models.subject import Subject


class SubjectPlanItem(Base):
    __tablename__ = "subject_plan_items"
    __table_args__ = (
        UniqueConstraint(
            "subject_id",
            "lesson_kind",
            "topic_number",
            "session_number",
            name="uq_subject_plan_items_subject_lesson_identity",
        ),
        Index(
            "ix_subject_plan_items_subject_lookup",
            "subject_id",
            "lesson_kind",
            "topic_number",
            "session_number",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    lesson_kind: Mapped[PlanLessonKind] = mapped_column(
        Enum(
            PlanLessonKind,
            values_callable=lambda enum_class: [item.value for item in enum_class],
            native_enum=False,
            length=20,
        ),
        nullable=False,
    )
    topic_number: Mapped[int] = mapped_column(Integer, nullable=False)
    session_number: Mapped[int] = mapped_column(Integer, nullable=False)
    topic_title: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    subject: Mapped["Subject"] = relationship(back_populates="plan_items")
    questions: Mapped[list["PlanItemQuestion"]] = relationship(
        back_populates="plan_item",
        cascade="all, delete-orphan",
        order_by="PlanItemQuestion.order_index",
    )
    assignments: Mapped[list["PlanItemAssignment"]] = relationship(
        back_populates="plan_item",
        cascade="all, delete-orphan",
        order_by="PlanItemAssignment.order_index",
    )


class PlanItemQuestion(Base):
    __tablename__ = "plan_item_questions"
    __table_args__ = (
        UniqueConstraint(
            "plan_item_id",
            "order_index",
            name="uq_plan_item_questions_plan_item_order",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_item_id: Mapped[int] = mapped_column(
        ForeignKey("subject_plan_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text(), nullable=False)

    plan_item: Mapped["SubjectPlanItem"] = relationship(back_populates="questions")


class PlanItemAssignment(Base):
    __tablename__ = "plan_item_assignments"
    __table_args__ = (
        UniqueConstraint(
            "plan_item_id",
            "order_index",
            name="uq_plan_item_assignments_plan_item_order",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_item_id: Mapped[int] = mapped_column(
        ForeignKey("subject_plan_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    task_number: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text(), nullable=False)
    condition: Mapped[str | None] = mapped_column(Text())
    question: Mapped[str | None] = mapped_column(Text())

    plan_item: Mapped["SubjectPlanItem"] = relationship(back_populates="assignments")
