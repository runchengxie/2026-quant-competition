"""Fixed daily-study decision calendars, without account state."""

from datetime import date


def weekly_flags(decision_dates):
    return [
        i == 0 or date.fromisoformat(day).weekday() == 0
        for i, day in enumerate(decision_dates)
    ]
