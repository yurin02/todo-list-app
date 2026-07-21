import html
import re
from datetime import date

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import sheets

app = FastAPI(title="Todo List App")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

_URL_PATTERN = re.compile(r"https?://[^\s<]+")


def _linkify(text: str) -> str:
    escaped = html.escape(text)
    return _URL_PATTERN.sub(
        lambda m: f'<a href="{m.group(0)}" target="_blank" rel="noopener noreferrer">{m.group(0)}</a>',
        escaped,
    )


templates.env.filters["linkify"] = _linkify


def _with_overdue_flag(todos: list[dict]) -> list[dict]:
    today = date.today().isoformat()
    for todo in todos:
        due = todo.get("DueDate") or ""
        todo["is_overdue"] = bool(due) and due < today and todo.get("Status") != sheets.STATUS_DONE
    return todos


@app.get("/")
def index(request: Request, sort: str = sheets.DEFAULT_SORT):
    if sort not in sheets.SORT_KEYS:
        sort = sheets.DEFAULT_SORT
    todos = _with_overdue_flag(sheets.list_todos(sort=sort))
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "todos": todos,
            "current_sort": sort,
            "category_labels": sheets.CATEGORIES,
        },
    )


@app.get("/todos/new")
def new_todo_form(request: Request):
    return templates.TemplateResponse(
        "form.html",
        {"request": request, "mode": "new", "todo": {}, "categories": sheets.CATEGORIES},
    )


def _clamp_priority(priority: int) -> int:
    return max(sheets.PRIORITY_MIN, min(sheets.PRIORITY_MAX, priority))


def _clean_category(category: str) -> str:
    return category if category in sheets.CATEGORIES else sheets.DEFAULT_CATEGORY


@app.post("/todos")
def create_todo(
    title: str = Form(...),
    content: str = Form(""),
    due_date: str = Form(""),
    priority: int = Form(sheets.DEFAULT_PRIORITY),
    category: str = Form(sheets.DEFAULT_CATEGORY),
    tags: str = Form(""),
    due_time: str = Form(""),
):
    sheets.create_todo(
        title=title,
        content=content,
        due_date=due_date,
        priority=_clamp_priority(priority),
        category=_clean_category(category),
        tags=tags,
        due_time=due_time,
    )
    return RedirectResponse(url="/", status_code=303)


@app.get("/todos/{todo_id}/edit")
def edit_todo_form(request: Request, todo_id: str):
    todo = sheets.get_todo(todo_id)
    return templates.TemplateResponse(
        "form.html",
        {"request": request, "mode": "edit", "todo": todo, "categories": sheets.CATEGORIES},
    )


@app.post("/todos/{todo_id}")
def update_todo(
    todo_id: str,
    title: str = Form(...),
    content: str = Form(""),
    due_date: str = Form(""),
    priority: int = Form(sheets.DEFAULT_PRIORITY),
    category: str = Form(sheets.DEFAULT_CATEGORY),
    tags: str = Form(""),
    due_time: str = Form(""),
):
    sheets.update_todo(
        todo_id,
        title=title,
        content=content,
        due_date=due_date,
        priority=_clamp_priority(priority),
        category=_clean_category(category),
        tags=tags,
        due_time=due_time,
    )
    return RedirectResponse(url="/", status_code=303)


@app.post("/todos/{todo_id}/delete")
def delete_todo(todo_id: str):
    sheets.delete_todo(todo_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/todos/{todo_id}/toggle")
def toggle_todo(todo_id: str):
    sheets.toggle_status(todo_id)
    return RedirectResponse(url="/", status_code=303)
