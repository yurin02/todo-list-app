import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from linebot.v3.messaging import (
    ApiClient,
    BroadcastRequest,
    Configuration,
    MessagingApi,
    TextMessage,
)

from app import sheets

JST = ZoneInfo("Asia/Tokyo")
_WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


def today_jst() -> date:
    return datetime.now(JST).date()


def split_due_and_overdue(todos: list[dict], today: date) -> tuple[list[dict], list[dict]]:
    due_today = []
    overdue = []
    for todo in todos:
        due_raw = todo.get("DueDate") or ""
        if not due_raw:
            continue
        try:
            due_date = date.fromisoformat(due_raw)
        except ValueError:
            continue
        if due_date == today:
            due_today.append(todo)
        elif due_date < today:
            overdue.append(todo)
    due_today.sort(key=lambda t: t.get("DueTime") or "99:99")
    overdue.sort(key=lambda t: t.get("DueDate") or "")
    return due_today, overdue


def _format_today_header(today: date) -> str:
    weekday = _WEEKDAY_JP[today.weekday()]
    return f"{today.year}年{today.month}月{today.day}日 ({weekday})"


def _category_label(todo: dict) -> str:
    return sheets.CATEGORIES.get(todo.get("Category"), todo.get("Category") or "")


def build_message(due_today: list[dict], overdue: list[dict], today: date) -> str:
    lines = ["おはようございます!", f"📅 今日 ({_format_today_header(today)})", ""]

    if not due_today and not overdue:
        lines.append("今日の予定はありません☕")
        lines.append("ゆっくりした1日をお過ごしください")
        return "\n".join(lines)

    if overdue:
        lines.append(f"🔴 期限切れ ({len(overdue)}件)")
        for todo in overdue:
            due_date = date.fromisoformat(todo["DueDate"])
            days_over = (today - due_date).days
            lines.append(f"・{todo.get('Title', '')} ({days_over}日超過) [{_category_label(todo)}]")
        lines.append("")

    if due_today:
        lines.append(f"📌 今日の予定 ({len(due_today)}件)")
        for todo in due_today:
            time_label = todo.get("DueTime") or "時間未定"
            lines.append(f"・{time_label} {todo.get('Title', '')} [{_category_label(todo)}]")
        lines.append("")

    lines.append("今日も1日頑張りましょう💪")
    return "\n".join(lines)


def send_broadcast(message: str) -> None:
    configuration = Configuration(access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).broadcast(BroadcastRequest(messages=[TextMessage(text=message)]))
