import os
import time
import uuid
from functools import lru_cache

import gspread

from app.sheets import _get_client

SHEET_NAME = "Todos"
HEADERS = [
    "ID", "Title", "Description", "DueDate", "DueTime", "Importance",
    "Category", "Tags", "Source", "Completed", "CreatedAt", "UpdatedAt",
]

DEFAULT_IMPORTANCE = 3
DEFAULT_CATEGORY = "私用"
DEFAULT_SOURCE = "web"


def _col_letter(index0: int) -> str:
    return chr(ord("A") + index0)


LAST_COLUMN_LETTER = _col_letter(len(HEADERS) - 1)


@lru_cache(maxsize=1)
def _get_worksheet() -> gspread.Worksheet:
    client = _get_client()
    spreadsheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID_JS"])
    try:
        worksheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.sheet1
        worksheet.update_title(SHEET_NAME)
    if worksheet.row_values(1) != HEADERS:
        worksheet.update("A1", [HEADERS])
    _ensure_column_formats(worksheet)
    return worksheet


def _ensure_column_formats(worksheet: gspread.Worksheet) -> None:
    # DueTime ("09:00") gets reinterpreted as a time value and loses its
    # leading zero if Sheets auto-detects the column type under
    # USER_ENTERED, so pin every free-text column to TEXT explicitly
    # (same issue as documented in dev-knowledge for app/sheets.py).
    text_columns = ["Title", "Description", "DueDate", "DueTime", "Category", "Tags", "Source"]
    number_columns = ["Importance", "CreatedAt", "UpdatedAt"]

    def _format_request(column_name: str, number_format: dict) -> dict:
        col_index = HEADERS.index(column_name)
        return {
            "repeatCell": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": 1,
                    "startColumnIndex": col_index,
                    "endColumnIndex": col_index + 1,
                },
                "cell": {"userEnteredFormat": {"numberFormat": number_format}},
                "fields": "userEnteredFormat.numberFormat",
            }
        }

    requests = (
        [_format_request(c, {"type": "TEXT"}) for c in text_columns]
        + [_format_request(c, {"type": "NUMBER", "pattern": "0"}) for c in number_columns]
    )
    worksheet.spreadsheet.batch_update({"requests": requests})


def _now_ms() -> int:
    return int(time.time() * 1000)


def _parse_tags(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def _format_tags(tags: list[str]) -> str:
    return ",".join(t.strip() for t in tags if t.strip())


def _parse_bool(raw) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().upper() == "TRUE"


def _normalize(row: dict) -> dict:
    row["Importance"] = int(row["Importance"]) if row.get("Importance") not in (None, "") else DEFAULT_IMPORTANCE
    row["Category"] = row.get("Category") or DEFAULT_CATEGORY
    row["Tags"] = _parse_tags(row.get("Tags") or "")
    row["Source"] = row.get("Source") or DEFAULT_SOURCE
    row["Completed"] = _parse_bool(row.get("Completed"))
    row["CreatedAt"] = int(row["CreatedAt"]) if row.get("CreatedAt") not in (None, "") else _now_ms()
    row["UpdatedAt"] = int(row["UpdatedAt"]) if row.get("UpdatedAt") not in (None, "") else row["CreatedAt"]
    return row


def _find_row_index(todo_id: str) -> int:
    worksheet = _get_worksheet()
    ids = worksheet.col_values(1)
    for i, value in enumerate(ids, start=1):
        if value == todo_id:
            return i
    raise ValueError(f"Todo not found: {todo_id}")


def list_todos(completed: bool | None = None) -> list[dict]:
    worksheet = _get_worksheet()
    records = [_normalize(r) for r in worksheet.get_all_records()]
    if completed is not None:
        records = [r for r in records if r["Completed"] == completed]
    records.sort(key=lambda r: (r.get("DueDate") or "9999-99-99", r.get("DueTime") or "99:99"))
    return records


def get_todo(todo_id: str) -> dict:
    worksheet = _get_worksheet()
    row_index = _find_row_index(todo_id)
    values = worksheet.row_values(row_index)
    values += [""] * (len(HEADERS) - len(values))
    return _normalize(dict(zip(HEADERS, values)))


def create_todo(
    title: str,
    description: str = "",
    due_date: str = "",
    due_time: str = "",
    importance: int = DEFAULT_IMPORTANCE,
    category: str = DEFAULT_CATEGORY,
    tags: list[str] | None = None,
    source: str = DEFAULT_SOURCE,
) -> dict:
    worksheet = _get_worksheet()
    todo_id = str(uuid.uuid4())
    now = _now_ms()
    row = [
        todo_id, title, description, due_date, due_time, importance,
        category, _format_tags(tags or []), source, False, now, now,
    ]
    worksheet.append_row(row, value_input_option="USER_ENTERED")
    return _normalize(dict(zip(HEADERS, row)))


def update_todo(todo_id: str, **fields) -> dict:
    field_to_column = {
        "title": "Title",
        "description": "Description",
        "due_date": "DueDate",
        "due_time": "DueTime",
        "importance": "Importance",
        "category": "Category",
        "tags": "Tags",
        "source": "Source",
    }
    worksheet = _get_worksheet()
    row_index = _find_row_index(todo_id)
    current = get_todo(todo_id)
    for key, value in fields.items():
        if value is None or key not in field_to_column:
            continue
        column = field_to_column[key]
        current[column] = value
    current["UpdatedAt"] = _now_ms()
    row = [
        _format_tags(current[h]) if h == "Tags" else current[h]
        for h in HEADERS
    ]
    worksheet.update(
        f"A{row_index}:{LAST_COLUMN_LETTER}{row_index}", [row], value_input_option="USER_ENTERED"
    )
    return get_todo(todo_id)


def toggle_todo(todo_id: str) -> dict:
    worksheet = _get_worksheet()
    row_index = _find_row_index(todo_id)
    completed_col = HEADERS.index("Completed") + 1
    updated_col = HEADERS.index("UpdatedAt") + 1
    current = worksheet.cell(row_index, completed_col).value
    new_value = not _parse_bool(current)
    worksheet.update_cell(row_index, completed_col, new_value)
    worksheet.update_cell(row_index, updated_col, _now_ms())
    return get_todo(todo_id)


def delete_todo(todo_id: str) -> None:
    worksheet = _get_worksheet()
    row_index = _find_row_index(todo_id)
    worksheet.delete_rows(row_index)
