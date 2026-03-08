from enum import StrEnum


class UserRole(StrEnum):
    STUDENT = "student"
    ADMIN = "admin"


class MainMenuSection(StrEnum):
    SCHEDULE = "Schedule"
    SUBJECTS = "Subjects"
    TASKS = "Tasks"
    FILES = "Files"
    AI = "AI"
