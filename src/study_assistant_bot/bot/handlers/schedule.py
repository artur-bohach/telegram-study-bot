from __future__ import annotations

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from study_assistant_bot.bot.keyboards import (
    LessonActionCallback,
    LessonDetailsCallback,
    WeekDayCallback,
    build_day_schedule_keyboard,
    build_lesson_details_keyboard,
    build_main_menu,
    build_schedule_menu,
    build_week_picker_keyboard,
)
from study_assistant_bot.enums import MainMenuSection, ScheduleMenuAction
from study_assistant_bot.services import ScheduleService
from study_assistant_bot.texts import (
    LESSON_NOT_FOUND_TEXT,
    SCHEDULE_BACK_TEXT,
    SCHEDULE_MENU_TEXT,
    build_lesson_action_placeholder_text,
    build_lesson_details_text,
    build_selected_day_schedule_text,
    build_today_schedule_text,
    build_tomorrow_schedule_text,
    build_week_schedule_text,
)

router = Router(name="schedule")


@router.message(F.text == MainMenuSection.SCHEDULE.value)
async def open_schedule_menu(message: Message) -> None:
    await message.answer(
        SCHEDULE_MENU_TEXT,
        reply_markup=build_schedule_menu(),
    )


@router.message(F.text == ScheduleMenuAction.TODAY.value)
async def show_today_schedule(
    message: Message,
    session: AsyncSession,
) -> None:
    schedule_date = date.today()
    await _send_day_schedule_message(
        message=message,
        session=session,
        context="today",
        schedule_date=schedule_date,
    )


@router.message(F.text == ScheduleMenuAction.TOMORROW.value)
async def show_tomorrow_schedule(
    message: Message,
    session: AsyncSession,
) -> None:
    schedule_date = date.today() + timedelta(days=1)
    await _send_day_schedule_message(
        message=message,
        session=session,
        context="tomorrow",
        schedule_date=schedule_date,
    )


@router.message(F.text == ScheduleMenuAction.WEEK.value)
async def show_week_schedule(
    message: Message,
    session: AsyncSession,
) -> None:
    today = date.today()
    text, keyboard = await _build_schedule_context_payload(
        session=session,
        context="week",
        context_date=today,
    )
    await message.answer(text, reply_markup=keyboard)


@router.message(F.text == ScheduleMenuAction.BACK.value)
async def return_to_main_menu(message: Message) -> None:
    await message.answer(
        SCHEDULE_BACK_TEXT,
        reply_markup=build_main_menu(),
    )


@router.callback_query(LessonDetailsCallback.filter())
async def open_lesson_details(
    callback: CallbackQuery,
    callback_data: LessonDetailsCallback,
    session: AsyncSession,
) -> None:
    if callback.message is None:
        await callback.answer(LESSON_NOT_FOUND_TEXT, show_alert=True)
        return

    schedule_service = ScheduleService(session)
    lesson = await schedule_service.get_lesson_by_id(callback_data.lesson_id)
    if lesson is None:
        await callback.answer(LESSON_NOT_FOUND_TEXT, show_alert=True)
        return

    context_date = date.fromisoformat(callback_data.context_date)
    await callback.message.edit_text(
        build_lesson_details_text(lesson),
        reply_markup=build_lesson_details_keyboard(
            lesson_id=lesson.id,
            context=callback_data.context,
            context_date=context_date,
        ),
    )
    await callback.answer()


@router.callback_query(WeekDayCallback.filter())
async def show_week_day_schedule(
    callback: CallbackQuery,
    callback_data: WeekDayCallback,
    session: AsyncSession,
) -> None:
    if callback.message is None:
        await callback.answer(SCHEDULE_MENU_TEXT, show_alert=True)
        return

    selected_date = date.fromisoformat(callback_data.context_date)
    text, keyboard = await _build_schedule_context_payload(
        session=session,
        context="week_day",
        context_date=selected_date,
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(LessonActionCallback.filter(F.action == "back"))
async def return_to_schedule_context(
    callback: CallbackQuery,
    callback_data: LessonActionCallback,
    session: AsyncSession,
) -> None:
    if callback.message is None:
        await callback.answer(SCHEDULE_MENU_TEXT, show_alert=True)
        return

    context_date = date.fromisoformat(callback_data.context_date)
    text, keyboard = await _build_schedule_context_payload(
        session=session,
        context=callback_data.context,
        context_date=context_date,
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(LessonActionCallback.filter())
async def handle_lesson_action_placeholder(
    callback: CallbackQuery,
    callback_data: LessonActionCallback,
) -> None:
    await callback.answer(
        build_lesson_action_placeholder_text(callback_data.action),
        show_alert=False,
    )


async def _send_day_schedule_message(
    message: Message,
    session: AsyncSession,
    context: str,
    schedule_date: date,
) -> None:
    text, keyboard = await _build_schedule_context_payload(
        session=session,
        context=context,
        context_date=schedule_date,
    )
    await message.answer(text, reply_markup=keyboard)


async def _build_schedule_context_payload(
    session: AsyncSession,
    context: str,
    context_date: date,
) -> tuple[str, object | None]:
    schedule_service = ScheduleService(session)

    if context == "today":
        lessons = await schedule_service.get_lessons_for_day(context_date)
        text = build_today_schedule_text(schedule_date=context_date, lessons=lessons)
        keyboard = build_day_schedule_keyboard(
            lessons=lessons,
            context=context,
            context_date=context_date,
        )
    elif context == "tomorrow":
        lessons = await schedule_service.get_lessons_for_day(context_date)
        text = build_tomorrow_schedule_text(schedule_date=context_date, lessons=lessons)
        keyboard = build_day_schedule_keyboard(
            lessons=lessons,
            context=context,
            context_date=context_date,
        )
    elif context == "week_day":
        lessons = await schedule_service.get_lessons_for_day(context_date)
        week_dates = schedule_service.get_work_week_dates(context_date)
        text = build_selected_day_schedule_text(schedule_date=context_date, lessons=lessons)
        keyboard = build_day_schedule_keyboard(
            lessons=lessons,
            context=context,
            context_date=context_date,
            week_dates=week_dates,
            selected_date=context_date,
        )
    else:
        week_dates = schedule_service.get_work_week_dates(context_date)
        text = build_week_schedule_text(week_dates=week_dates)
        keyboard = build_week_picker_keyboard(week_dates=week_dates)

    return text, keyboard
