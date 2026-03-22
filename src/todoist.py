import logging
from dataclasses import dataclass
from datetime import date

import httpx

from src.config import TodoistFilters

logger = logging.getLogger(__name__)

TODOIST_API_BASE = "https://api.todoist.com/rest/v2"

TODOIST_COLOR_MAP: dict[str, str] = {
    "berry_red": "#b8256f",
    "red": "#db4035",
    "orange": "#ff9933",
    "yellow": "#fad000",
    "olive_green": "#afb83b",
    "lime_green": "#7ecc49",
    "green": "#299438",
    "mint_green": "#6accbc",
    "teal": "#158fad",
    "sky_blue": "#14aaf5",
    "light_blue": "#96c3eb",
    "blue": "#4073ff",
    "grape": "#884dff",
    "violet": "#af38eb",
    "lavender": "#eb96eb",
    "magenta": "#e05194",
    "salmon": "#ff8d85",
    "charcoal": "#808080",
    "grey": "#b8b8b8",
    "taupe": "#ccac93",
}


def todoist_color_to_hex(color_name: str) -> str:
    """Convert a Todoist color name to a hex color string."""
    return TODOIST_COLOR_MAP.get(color_name, "#808080")


@dataclass
class TodoistTask:
    title: str
    project_name: str
    project_color: str  # hex
    due_date: date
    is_overdue: bool


def filter_tasks(tasks: list[TodoistTask], filters: TodoistFilters) -> list[TodoistTask]:
    """Filter tasks by project name and title (exact match, case-insensitive)."""
    exclude_projects = {p.lower() for p in filters.exclude_projects}
    exclude_titles = {t.lower() for t in filters.exclude_titles}
    return [
        t
        for t in tasks
        if t.project_name.lower() not in exclude_projects and t.title.lower() not in exclude_titles
    ]


def sort_tasks(tasks: list[TodoistTask]) -> list[TodoistTask]:
    """Sort tasks: overdue first (oldest to newest), then today's tasks."""
    return sorted(tasks, key=lambda t: (not t.is_overdue, t.due_date))


def fetch_tasks(api_token: str, filters: TodoistFilters, today: date) -> list[TodoistTask]:
    """Fetch today's and overdue tasks from Todoist, filtered and sorted."""
    headers = {"Authorization": f"Bearer {api_token}"}

    with httpx.Client(base_url=TODOIST_API_BASE, headers=headers) as client:
        projects_resp = client.get("/projects")
        projects_resp.raise_for_status()
        projects_by_id: dict[str, dict] = {p["id"]: p for p in projects_resp.json()}

        tasks_resp = client.get("/tasks")
        tasks_resp.raise_for_status()

        tasks: list[TodoistTask] = []
        for raw in tasks_resp.json():
            due = raw.get("due")
            if due is None:
                continue
            due_date = date.fromisoformat(due["date"][:10])
            if due_date > today:
                continue

            project = projects_by_id.get(raw["project_id"], {})
            project_name = project.get("name", "Unknown")
            project_color = todoist_color_to_hex(project.get("color", "charcoal"))

            tasks.append(
                TodoistTask(
                    title=raw["content"],
                    project_name=project_name,
                    project_color=project_color,
                    due_date=due_date,
                    is_overdue=due_date < today,
                )
            )

        tasks = filter_tasks(tasks, filters)
        return sort_tasks(tasks)
