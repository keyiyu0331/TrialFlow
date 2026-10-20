"""FastAPI dependencies shared by the routers."""

from datetime import date


def get_today() -> date:
    """The date all computed values (overdue, slip, ...) are measured against.

    A dependency so tests can pin it with ``app.dependency_overrides``.
    """
    return date.today()
