"""
FastAPI learning API.

Run locally:
    uvicorn main:app --reload

Then open:
    http://127.0.0.1:8000/docs    <- interactive Swagger UI (try every endpoint here)
    http://127.0.0.1:8000/redoc   <- alternative read-only docs

Each section below introduces one FastAPI concept. Read top to bottom.
"""

import os
from datetime import datetime, timezone
from enum import Enum

from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

# Which environment we are running in (dev / uat / prod). The deployment
# pipeline sets this; locally it defaults to "local".
APP_ENV = os.getenv("APP_ENV", "local")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")

# The `app` object is the whole API. `uvicorn main:app` means
# "in file main.py, serve the object named app".
app = FastAPI(
    title="FastAPI Learning API",
    description="A small API to learn path/query params, request bodies and responses.",
    version=APP_VERSION,
)


# ---------------------------------------------------------------------------
# 1. The simplest endpoint: no input, returns JSON.
#    A Python dict is converted to JSON automatically.
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Hello from FastAPI!", "docs": "/docs"}


# ---------------------------------------------------------------------------
# 2. Health check. CI/CD and monitoring call this after a deployment to
#    confirm the app is alive and running the expected version.
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "environment": APP_ENV,
        "version": APP_VERSION,
        "time": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# 3. Path parameters: part of the URL itself.  GET /hello/Elie
#    The type hint `name: str` tells FastAPI what to expect.
# ---------------------------------------------------------------------------
@app.get("/hello/{name}")
def say_hello(name: str):
    return {"message": f"Hello, {name}!"}


# ---------------------------------------------------------------------------
# 4. Query parameters: after the `?` in the URL.
#    GET /add?a=3&b=4
#    Type hints (`float`) make FastAPI validate and convert the values.
#    Try /add?a=abc&b=1 -> you get a 422 error explaining what's wrong.
# ---------------------------------------------------------------------------
@app.get("/add")
def add(a: float, b: float):
    return {"a": a, "b": b, "result": a + b}


# ---------------------------------------------------------------------------
# 5. Optional query parameters, defaults, validation and Enums.
#    GET /calculate?a=10&b=2&operation=divide
#    `operation` is limited to the Enum values (the docs show a dropdown).
#    `precision` is optional, defaults to 2, must be between 0 and 10.
# ---------------------------------------------------------------------------
class Operation(str, Enum):
    add = "add"
    subtract = "subtract"
    multiply = "multiply"
    divide = "divide"


@app.get("/calculate")
def calculate(
    a: float,
    b: float,
    operation: Operation = Operation.add,
    precision: int = Query(default=2, ge=0, le=10, description="Decimal places"),
):
    if operation == Operation.add:
        result = a + b
    elif operation == Operation.subtract:
        result = a - b
    elif operation == Operation.multiply:
        result = a * b
    else:
        if b == 0:
            # Raising HTTPException returns a proper error status to the caller.
            raise HTTPException(status_code=400, detail="Cannot divide by zero")
        result = a / b
    return {"operation": operation, "result": round(result, precision)}


# ---------------------------------------------------------------------------
# 6. Request body (POST) with Pydantic models.
#    A Pydantic model describes the JSON shape. FastAPI validates incoming
#    JSON against it and documents it in /docs automatically.
#    `response_model` controls (and documents) what is sent back.
# ---------------------------------------------------------------------------
class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Laptop"])
    price: float = Field(gt=0, examples=[999.99])
    quantity: int = Field(default=1, ge=1, examples=[2])
    description: str | None = Field(default=None, examples=["14 inch, 16GB RAM"])


class ItemOut(ItemIn):
    id: int
    total: float


# In-memory "database" - resets on every restart. Later this becomes PostgreSQL.
items_db: dict[int, ItemOut] = {}
next_id = 1


@app.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(item: ItemIn):
    global next_id
    new_item = ItemOut(id=next_id, total=round(item.price * item.quantity, 2), **item.model_dump())
    items_db[next_id] = new_item
    next_id += 1
    return new_item


@app.get("/items", response_model=list[ItemOut])
def list_items(limit: int = Query(default=10, ge=1, le=100)):
    return list(items_db.values())[:limit]


@app.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    return items_db[item_id]


@app.put("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: int, item: ItemIn):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    updated = ItemOut(id=item_id, total=round(item.price * item.quantity, 2), **item.model_dump())
    items_db[item_id] = updated
    return updated


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int):
    if items_db.pop(item_id, None) is None:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
