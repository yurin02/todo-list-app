import json
import os
import uuid
from datetime import datetime
from functools import lru_cache

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SHEET_NAME = "Todos"
HEADERS = ["ID", "Title", "Content", "DueDate", "Status", "CreatedAt", "UpdatedAt", "Priority"]

STATUS_PENDING = "pending"
STATUS_DONE = "done"

DEFAULT_PRIORITY = 3
PRIORITY_MIN = 1
PRIORITY_MAX = 4


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
    return worksheet


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


def _normalize(todo: dict) -> dict:
    priority = todo.get("Priority")
    todo["Priority"] = int(priority) if priority not in (None, "") else DEFAULT_PRIORITY
    return todo


def _find_row_index(todo_id: str) -> int:
    worksheet = _get_worksheet()
    ids = worksheet.col_values(1)
    for i, value in enumerate(ids, start=1):
        if value == todo_id:
            return i
    raise ValueError(f"Todo not found: {todo_id}")


def list_todos() -> list[dict]:
    worksheet = _get_worksheet()
    records = [_normalize(r) for r in worksheet.get_all_records()]
    records.sort(key=lambda r: (r.get("DueDate") or "9999-99-99"))
    return records


def get_todo(todo_id: str) -> dict:
    worksheet = _get_worksheet()
    row_index = _find_row_index(todo_id)
    values = worksheet.row_values(row_index)
    values += [""] * (len(HEADERS) - len(values))
    return _normalize(dict(zip(HEADERS, values)))


def create_todo(title: str, content: str, due_date: str, priority: int = DEFAULT_PRIORITY) -> dict:
    worksheet = _get_worksheet()
    todo_id = str(uuid.uuid4())
    now = _now()
    row = [todo_id, title, content, due_date, STATUS_PENDING, now, now, priority]
    worksheet.append_row(row, value_input_option="USER_ENTERED")
    return _normalize(dict(zip(HEADERS, row)))


def update_todo(
    todo_id: str, title: str, content: str, due_date: str, priority: int = DEFAULT_PRIORITY
) -> None:
    worksheet = _get_worksheet()
    row_index = _find_row_index(todo_id)
    status_col = HEADERS.index("Status") + 1
    created_col = HEADERS.index("CreatedAt") + 1
    current_status = worksheet.cell(row_index, status_col).value
    created_at = worksheet.cell(row_index, created_col).value
    row = [todo_id, title, content, due_date, current_status, created_at, _now(), priority]
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
