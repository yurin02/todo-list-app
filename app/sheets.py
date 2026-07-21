import json
import os
import uuid
from datetime import datetime
from functools import lru_cache

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SHEET_NAME = "Todos"
HEADERS = [
    "ID", "Title", "Content", "DueDate", "Status", "CreatedAt", "UpdatedAt",
    "Priority", "Category", "Tags", "Source", "DueTime",
]

STATUS_PENDING = "pending"
STATUS_DONE = "done"

DEFAULT_PRIORITY = 3
PRIORITY_MIN = 1
PRIORITY_MAX = 4

CATEGORIES = {
    "work": "本業",
    "secondhand": "物販",
    "chatbot": "案件",
    "personal": "私用",
    "engineer": "エンジニア",
}
DEFAULT_CATEGORY = "personal"

SOURCE_WEB = "web"
SOURCE_LINE = "line"
DEFAULT_SOURCE = SOURCE_WEB


def _col_letter(index0: int) -> str:
    return chr(ord("A") + index0)


STATUS_COLUMN_LETTER = _col_letter(HEADERS.index("Status"))
LAST_COLUMN_LETTER = _col_letter(len(HEADERS) - 1)
DONE_HIGHLIGHT_FORMULA = f'=${STATUS_COLUMN_LETTER}2="{STATUS_DONE}"'
DONE_HIGHLIGHT_COLOR = {"red": 0.85, "green": 0.97, "blue": 0.88}


@lru_cache(maxsize=1)
def _get_client() -> gspread.Client:
    info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(credentials)


@lru_cache(maxsize=1)
def _get_worksheet() -> gspread.Worksheet:
    client = _get_client()
    spreadsheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"])
    try:
        worksheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(HEADERS))
    if worksheet.row_values(1) != HEADERS:
        worksheet.update("A1", [HEADERS])
    _ensure_done_highlight_rule(worksheet)
    _ensure_column_formats(worksheet)
    return worksheet


def _ensure_column_formats(worksheet: gspread.Worksheet) -> None:
    # New columns added after the sheet already existed can inherit the
    # DATE_TIME format of the last pre-existing column (UpdatedAt) when the
    # grid auto-expands. A plain number written under USER_ENTERED into a
    # cell that already has a DATE_TIME format gets reinterpreted as a date
    # serial instead of staying a plain number, so pin the correct format
    # explicitly for every non-date column.
    text_columns = ["Category", "Tags", "Source"]
    number_columns = ["Priority"]
    time_columns = ["DueTime"]

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
        + [_format_request(c, {"type": "TIME", "pattern": "h:mm"}) for c in time_columns]
    )
    worksheet.spreadsheet.batch_update({"requests": requests})


def _ensure_done_highlight_rule(worksheet: gspread.Worksheet) -> None:
    spreadsheet = worksheet.spreadsheet
    metadata = spreadsheet.fetch_sheet_metadata()
    sheet_meta = next(
        (s for s in metadata["sheets"] if s["properties"]["sheetId"] == worksheet.id),
        None,
    )
    existing_rules = (sheet_meta or {}).get("conditionalFormats", [])
    for rule in existing_rules:
        values = rule.get("booleanRule", {}).get("condition", {}).get("values", [])
        if values and values[0].get("userEnteredValue") == DONE_HIGHLIGHT_FORMULA:
            return

    spreadsheet.batch_update(
        {
            "requests": [
                {
                    "addConditionalFormatRule": {
                        "rule": {
                            "ranges": [
                                {
                                    "sheetId": worksheet.id,
                                    "startRowIndex": 1,
                                    "startColumnIndex": 0,
                                    "endColumnIndex": len(HEADERS),
                                }
                            ],
                            "booleanRule": {
                                "condition": {
                                    "type": "CUSTOM_FORMULA",
                                    "values": [{"userEnteredValue": DONE_HIGHLIGHT_FORMULA}],
                                },
                                "format": {"backgroundColor": DONE_HIGHLIGHT_COLOR},
                            },
                        },
                        "index": 0,
                    }
                }
            ]
        }
    )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_tags(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def _format_tags(raw: str) -> str:
    return ",".join(_parse_tags(raw))


def _normalize(todo: dict) -> dict:
    priority = todo.get("Priority")
    todo["Priority"] = int(priority) if priority not in (None, "") else DEFAULT_PRIORITY
    if todo.get("Category") not in CATEGORIES:
        todo["Category"] = DEFAULT_CATEGORY
    todo["TagList"] = _parse_tags(todo.get("Tags") or "")
    if not todo.get("Source"):
        todo["Source"] = DEFAULT_SOURCE
    return todo


def _find_row_index(todo_id: str) -> int:
    worksheet = _get_worksheet()
    ids = worksheet.col_values(1)
    for i, value in enumerate(ids, start=1):
        if value == todo_id:
            return i
    raise ValueError(f"Todo not found: {todo_id}")


def _due_time_key(todo: dict) -> str:
    return todo.get("DueTime") or "99:99"


SORT_KEYS = {
    "due": lambda r: (r.get("DueDate") or "9999-99-99", _due_time_key(r)),
    "priority": lambda r: (
        -int(r.get("Priority") or DEFAULT_PRIORITY),
        r.get("DueDate") or "9999-99-99",
        _due_time_key(r),
    ),
    "created": lambda r: r.get("CreatedAt") or "",
}
DEFAULT_SORT = "due"


def list_todos(sort: str = DEFAULT_SORT) -> list[dict]:
    worksheet = _get_worksheet()
    records = [_normalize(r) for r in worksheet.get_all_records()]
    key_func = SORT_KEYS.get(sort, SORT_KEYS[DEFAULT_SORT])
    records.sort(key=key_func)
    return records


def get_todo(todo_id: str) -> dict:
    worksheet = _get_worksheet()
    row_index = _find_row_index(todo_id)
    values = worksheet.row_values(row_index)
    values += [""] * (len(HEADERS) - len(values))
    return _normalize(dict(zip(HEADERS, values)))


def create_todo(
    title: str,
    content: str,
    due_date: str,
    priority: int = DEFAULT_PRIORITY,
    category: str = DEFAULT_CATEGORY,
    tags: str = "",
    due_time: str = "",
) -> dict:
    worksheet = _get_worksheet()
    todo_id = str(uuid.uuid4())
    now = _now()
    row = [
        todo_id, title, content, due_date, STATUS_PENDING, now, now,
        priority, category, _format_tags(tags), SOURCE_WEB, due_time,
    ]
    worksheet.append_row(row, value_input_option="USER_ENTERED")
    return _normalize(dict(zip(HEADERS, row)))


def update_todo(
    todo_id: str,
    title: str,
    content: str,
    due_date: str,
    priority: int = DEFAULT_PRIORITY,
    category: str = DEFAULT_CATEGORY,
    tags: str = "",
    due_time: str = "",
) -> None:
    worksheet = _get_worksheet()
    row_index = _find_row_index(todo_id)
    status_col = HEADERS.index("Status") + 1
    created_col = HEADERS.index("CreatedAt") + 1
    source_col = HEADERS.index("Source") + 1
    current_status = worksheet.cell(row_index, status_col).value
    created_at = worksheet.cell(row_index, created_col).value
    current_source = worksheet.cell(row_index, source_col).value or DEFAULT_SOURCE
    row = [
        todo_id, title, content, due_date, current_status, created_at, _now(),
        priority, category, _format_tags(tags), current_source, due_time,
    ]
    worksheet.update(
        f"A{row_index}:{LAST_COLUMN_LETTER}{row_index}", [row], value_input_option="USER_ENTERED"
    )


def delete_todo(todo_id: str) -> None:
    worksheet = _get_worksheet()
    row_index = _find_row_index(todo_id)
    worksheet.delete_rows(row_index)


def toggle_status(todo_id: str) -> None:
    worksheet = _get_worksheet()
    row_index = _find_row_index(todo_id)
    status_col = HEADERS.index("Status") + 1
    updated_col = HEADERS.index("UpdatedAt") + 1
    current = worksheet.cell(row_index, status_col).value
    new_status = STATUS_PENDING if current == STATUS_DONE else STATUS_DONE
    worksheet.update_cell(row_index, status_col, new_status)
    worksheet.update_cell(row_index, updated_col, _now())
