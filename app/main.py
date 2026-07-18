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


def _with_overdue_flag(todos: list[dict]) -> list[dict]:
    today = date.today().isoformat()
    for todo in todos:
        due = todo.get("DueDate") or ""
        todo["is_overdue"] = bool(due) and due < today and todo.get("Status") != sheets.STATUS_DONE
    return todos


@app.get("/")
def index(request: Request):
    todos = _with_overdue_flag(sheets.list_todos())
    return templates.TemplateResponse(
        "index.html", {"request": request, "todos": todos}
    )


@app.get("/todos/new")
def new_todo_form(request: Request):
    return templates.TemplateResponse(
        "form.html",
        {"request": request, "mode": "new", "todo": {}},
    )


@app.post("/todos")
def create_todo(
    title: str = Form(...),
    content: str = Form(""),
    due_date: str = Form(""),
):
    sheets.create_todo(title=title, content=content, due_date=due_date)
    return RedirectResponse(url="/", status_code=303)


@app.get("/todos/{todo_id}/edit")
def edit_todo_form(request: Request, todo_id: str):
    todo = sheets.get_todo(todo_id)
    return templates.TemplateResponse(
        "form.html",
        {"request": request, "mode": "edit", "todo": todo},
    )


@app.post("/todos/{todo_id}")
def update_todo(
    todo_id: str,
    title: str = Form(...),
    content: str = Form(""),
    due_date: str = Form(""),
):
    sheets.update_todo(todo_id, title=title, content=content, due_date=due_date)
    return RedirectResponse(url="/", status_code=303)


@app.post("/todos/{todo_id}/delete")
def delete_todo(todo_id: str):
    sheets.delete_todo(todo_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/todos/{todo_id}/toggle")
def toggle_todo(todo_id: str):
    sheets.toggle_status(todo_id)
    return RedirectResponse(url="/", status_code=303)
