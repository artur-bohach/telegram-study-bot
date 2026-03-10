from __future__ import annotations

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from study_assistant_bot.bot.keyboards import build_main_menu, build_schedule_menu
from study_assistant_bot.enums import MainMenuSection, ScheduleMenuAction
from study_assistant_bot.services import ScheduleService
from study_assistant_bot.texts import (
    SCHEDULE_BACK_TEXT,
    SCHEDULE_MENU_TEXT,
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
    schedule_service = ScheduleService(session)
    lessons = await schedule_service.get_lessons_for_day(schedule_date)

    await message.answer(
        build_today_schedule_text(schedule_date=schedule_date, lessons=lessons),
        reply_markup=build_schedule_menu(),
    )


@router.message(F.text == ScheduleMenuAction.TOMORROW.value)
async def show_tomorrow_schedule(
    message: Message,
    session: AsyncSession,
) -> None:
    schedule_date = date.today() + timedelta(days=1)
    schedule_service = ScheduleService(session)
    lessons = await schedule_service.get_lessons_for_day(schedule_date)

    await message.answer(
        build_tomorrow_schedule_text(schedule_date=schedule_date, lessons=lessons),
        reply_markup=build_schedule_menu(),
    )


@router.message(F.text == ScheduleMenuAction.WEEK.value)
async def show_week_schedule(
    message: Message,
    session: AsyncSession,
) -> None:
    today = date.today()
    schedule_service = ScheduleService(session)
    week_start, week_end = schedule_service.get_week_bounds(today)
    lessons = await schedule_service.get_lessons_for_week(reference_date=today)

    await message.answer(
        build_week_schedule_text(
            week_start=week_start,
            week_end=week_end,
            lessons=lessons,
        ),
        reply_markup=build_schedule_menu(),
    )


@router.message(F.text == ScheduleMenuAction.BACK.value)
async def return_to_main_menu(message: Message) -> None:
    await message.answer(
        SCHEDULE_BACK_TEXT,
        reply_markup=build_main_menu(),
    )
