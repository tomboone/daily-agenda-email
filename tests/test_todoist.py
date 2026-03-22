from datetime import date
from unittest.mock import MagicMock, patch

from src.config import TodoistFilters
from src.todoist import (
    TodoistTask,
    fetch_tasks,
    filter_tasks,
    todoist_color_to_hex,
)


class TestTodoistColorMap:
    def test_known_color(self) -> None:
        assert todoist_color_to_hex("berry_red") == "#b8256f"

    def test_unknown_color_returns_default(self) -> None:
        assert todoist_color_to_hex("nonexistent") == "#808080"


class TestFilterTasks:
    def test_excludes_by_project_name(self) -> None:
        tasks = [
            TodoistTask(
                title="Walk the dog",
                project_name="Dog",
                project_color="#b8256f",
                due_date=date(2026, 3, 22),
                is_overdue=False,
            ),
            TodoistTask(
                title="Buy groceries",
                project_name="Shopping",
                project_color="#4073ff",
                due_date=date(2026, 3, 22),
                is_overdue=False,
            ),
        ]
        filters = TodoistFilters(exclude_projects=["Dog"], exclude_titles=[])
        result = filter_tasks(tasks, filters)
        assert len(result) == 1
        assert result[0].title == "Buy groceries"

    def test_excludes_by_title_exact_match(self) -> None:
        tasks = [
            TodoistTask(
                title="Outside",
                project_name="Dog",
                project_color="#b8256f",
                due_date=date(2026, 3, 22),
                is_overdue=False,
            ),
            TodoistTask(
                title="Outside play time",
                project_name="Dog",
                project_color="#b8256f",
                due_date=date(2026, 3, 22),
                is_overdue=False,
            ),
        ]
        filters = TodoistFilters(exclude_projects=[], exclude_titles=["Outside"])
        result = filter_tasks(tasks, filters)
        assert len(result) == 1
        assert result[0].title == "Outside play time"

    def test_case_insensitive(self) -> None:
        tasks = [
            TodoistTask(
                title="outside",
                project_name="Dog",
                project_color="#b8256f",
                due_date=date(2026, 3, 22),
                is_overdue=False,
            ),
        ]
        filters = TodoistFilters(exclude_projects=[], exclude_titles=["Outside"])
        result = filter_tasks(tasks, filters)
        assert len(result) == 0


class TestSortTasks:
    def test_overdue_sorted_before_today(self) -> None:
        tasks = [
            TodoistTask(
                title="Today task",
                project_name="Work",
                project_color="#4073ff",
                due_date=date(2026, 3, 22),
                is_overdue=False,
            ),
            TodoistTask(
                title="Old task",
                project_name="Work",
                project_color="#4073ff",
                due_date=date(2026, 3, 20),
                is_overdue=True,
            ),
        ]
        sorted_tasks = sorted(tasks, key=lambda t: (not t.is_overdue, t.due_date))
        assert sorted_tasks[0].title == "Old task"
        assert sorted_tasks[1].title == "Today task"


class TestFetchTasks:
    @patch("src.todoist.httpx.Client")
    def test_fetches_and_parses_tasks(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        projects_response = MagicMock()
        projects_response.json.return_value = [
            {"id": "1001", "name": "Shopping", "color": "blue"},
            {"id": "1002", "name": "Dog", "color": "berry_red"},
        ]
        projects_response.raise_for_status = MagicMock()

        tasks_response = MagicMock()
        tasks_response.json.return_value = [
            {
                "id": "2001",
                "content": "Buy groceries",
                "project_id": "1001",
                "due": {"date": "2026-03-22"},
            },
            {
                "id": "2002",
                "content": "Walk the dog",
                "project_id": "1002",
                "due": {"date": "2026-03-22"},
            },
            {
                "id": "2003",
                "content": "No due date task",
                "project_id": "1001",
                "due": None,
            },
        ]
        tasks_response.raise_for_status = MagicMock()

        mock_client.get.side_effect = [projects_response, tasks_response]

        filters = TodoistFilters(exclude_projects=["Dog"], exclude_titles=[])
        today = date(2026, 3, 22)

        result = fetch_tasks("fake-api-token", filters, today)

        assert len(result) == 1
        assert result[0].title == "Buy groceries"
        assert result[0].project_color == "#4073ff"  # blue
