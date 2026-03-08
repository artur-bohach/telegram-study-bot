from __future__ import annotations

from study_assistant_bot.enums import MainMenuSection

ACCESS_DENIED_TEXT = (
    "Access denied. This bot is configured for a small fixed list of trusted Telegram users."
)

START_TEXT = (
    "Welcome to the study assistant.\n\n"
    "This is the initial project foundation for a shared university workflow. "
    "Choose a section from the menu below."
)

UNKNOWN_MESSAGE_TEXT = (
    "Use the menu below to open one of the available sections. "
    "More workflows will be added in future phases."
)

SECTION_PLACEHOLDER_TEXTS = {
    MainMenuSection.SCHEDULE: (
        "Schedule is not implemented yet.\n\n"
        "This section will later show the shared lesson calendar and upcoming study events."
    ),
    MainMenuSection.SUBJECTS: (
        "Subjects is not implemented yet.\n\n"
        "This section will later contain the shared list of university subjects and materials."
    ),
    MainMenuSection.TASKS: (
        "Tasks is not implemented yet.\n\n"
        "This section will later track deadlines, homework, and helper-admin coordination."
    ),
    MainMenuSection.FILES: (
        "Files is not implemented yet.\n\n"
        "This section will later hold uploaded seminar files, notes, and study attachments."
    ),
    MainMenuSection.AI: (
        "AI is not implemented yet.\n\n"
        "This section is reserved for future AI-assisted study workflows."
    ),
}
