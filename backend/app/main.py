import os
import time
import json
import hmac
import hashlib
import sqlite3
import secrets
from urllib.parse import parse_qsl
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).resolve().parent
DB = BASE / "cointy.db"

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")

SMARTLINKS = [
    "https://omg10.com/4/11950214",
    "https://omg10.com/4/11950215",
]

app = FastAPI(title="Cointy Pay API")
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <script src='//libtl.com/sdk.js' data-zone='11955158' data-sdk='show_11955158'></script>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cointy Pay</title>

        <style>
            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #f4f7fb;
                color: #222;
            }

            .container {
                max-width: 500px;
                margin: auto;
                padding: 25px 18px;
                text-align: center;
            }

            .logo {
                font-size: 42px;
                margin-top: 30px;
            }

            h1 {
                margin: 10px 0;
                color: #5b3cc4;
            }

            .card {
                background: white;
                border-radius: 18px;
                padding: 25px;
                margin-top: 25px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            }

            .balance {
                font-size: 30px;
                font-weight: bold;
                margin: 15px 0;
            }

            button {
                width: 100%;
                padding: 15px;
                margin-top: 12px;
                border: none;
                border-radius: 12px;
                font-size: 17px;
                font-weight: bold;
                color: white;
                background: #6c4bdc;
            }

            button:active {
                transform: scale(0.98);
            }

            .info {
                margin-top: 20px;
                color: #777;
                font-size: 14px;
            }
        </style>
    </head>

    <body>
        <div class="container">

            <div class="logo">🪙</div>

            <h1>Cointy Pay</h1>

            <div class="card">
                <div>Your Balance</div>

                <div class="balance">
                    0 Coins
                </div>

                <button onclick="alert('Earn feature coming soon!')">
                    🎁 Earn Coins
                </button>

                <button onclick="alert('Withdraw feature coming soon!')">
                    💰 Withdraw
                </button>
            </div>

            <div class="info">
                Complete tasks and earn coins.
            </div>

        </div>
    </body>
    </html>
    """

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN]
    if FRONTEND_ORIGIN != "*"
    else ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = conn()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        telegram_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        points INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'active',
        created_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        smartlink_index INTEGER NOT NULL,
        active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS task_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        task_id INTEGER NOT NULL,
        event TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        UNIQUE(telegram_id, task_id, event)
    );

    CREATE TABLE IF NOT EXISTS withdrawals(
        id TEXT PRIMARY KEY,
        telegram_id INTEGER NOT NULL,
        points INTEGER NOT NULL,
        amount_bdt INTEGER NOT NULL,
        method TEXT NOT NULL,
        account TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at INTEGER NOT NULL
    );
    """)

    for i in range(1, 31):
        c.execute(
            """
            INSERT OR IGNORE INTO tasks
            (id, title, smartlink_index)
            VALUES (?, ?, ?)
            """,
            (
                i,
                f"Monetag Task {i}",
                (i - 1) % 2
            )
        )

    c.commit()
    c.close()


init_db()


class InitIn(BaseModel):
    init_data: str = Field(min_length=1)


class TaskIn(InitIn):
    task_id: int = Field(ge=1, le=30)


class WithdrawIn(InitIn):
    method: str
    account: str = Field(min_length=8, max_length=20)


def validate_init_data(init_data: str):
    if not BOT_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="BOT_TOKEN is not configured"
        )

    pairs = dict(parse_qsl(
        init_data,
        keep_blank_values=True
    ))

    received = pairs.pop("hash", None)

    if not received:
        raise HTTPException(
            status_code=401,
            detail="Missing Telegram hash"
        )

    data_check = "\n".join(
        f"{k}={v}"
        for k, v in sorted(pairs.items())
    )

    secret = hmac.new(
        b"WebAppData",
        BOT_TOKEN.encode(),
        hashlib.sha256
    ).digest()

    expected = hmac.new(
        secret,
        data_check.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(
        expected,
        received
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid Telegram initData"
        )

    auth_date = int(
        pairs.get("auth_date", "0")
    )

    if abs(int(time.time()) - auth_date) > 86400:
        raise HTTPException(
            status_code=401,
            detail="Expired Telegram session"
        )

    try:
        user = json.loads(pairs["user"])
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid Telegram user data"
        )

    if not user.get("id"):
        raise HTTPException(
            status_code=401,
            detail="Missing Telegram user id"
        )

    return user


def ensure_user(user):
    c = conn()

    c.execute(
        """
        INSERT OR IGNORE INTO users
        (telegram_id, username, first_name, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            int(user["id"]),
            user.get("username"),
            user.get("first_name", ""),
            int(time.time())
        )
    )

    c.execute(
        """
        UPDATE users
        SET username=?, first_name=?
        WHERE telegram_id=?
        """,
        (
            user.get("username"),
            user.get("first_name", ""),
            int(user["id"])
        )
    )

    c.commit()
    c.close()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/me")
def me(data: InitIn):
    user = validate_init_data(data.init_data)
    ensure_user(user)

    c = conn()

    u = c.execute(
        """
        SELECT telegram_id, username, first_name,
               points, status
        FROM users
        WHERE telegram_id=?
        """,
        (user["id"],)
    ).fetchone()

    done = c.execute(
        """
        SELECT task_id
        FROM task_events
        WHERE telegram_id=?
        AND event='click'
        """,
        (user["id"],)
    ).fetchall()

    c.close()

    return {
        "user": dict(u),
        "completed": [
            r["task_id"]
            for r in done
        ]
    }


@app.get("/api/tasks")
def tasks():
    c = conn()

    rows = c.execute(
        """
        SELECT id, title, smartlink_index
        FROM tasks
        WHERE active=1
        ORDER BY id
        """
    ).fetchall()

    c.close()

    return {
        "tasks": [
            {
                "id": r["id"],
                "title": r["title"],
                "smartlink":
                    SMARTLINKS[r["smartlink_index"]]
            }
            for r in rows
        ]
    }


@app.post("/api/tasks/click")
def task_click(data: TaskIn):
    user = validate_init_data(data.init_data)
    ensure_user(user)

    c = conn()

    u = c.execute(
        """
        SELECT status
        FROM users
        WHERE telegram_id=?
        """,
        (user["id"],)
    ).fetchone()

    if not u or u["status"] != "active":
        c.close()
        raise HTTPException(
            status_code=403,
            detail="Account is not active"
        )

    t = c.execute(
        """
        SELECT id, smartlink_index
        FROM tasks
        WHERE id=?
        AND active=1
        """,
        (data.task_id,)
    ).fetchone()

    if not t:
        c.close()
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    try:
        c.execute(
            """
            INSERT INTO task_events
            (telegram_id, task_id, event, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                user["id"],
                data.task_id,
                "click",
                int(time.time())
            )
        )

        c.commit()

    except sqlite3.IntegrityError:
        pass

    c.close()

    return {
        "ok": True,
        "url": SMARTLINKS[t["smartlink_index"]],
        "rewarded": False,
        "message":
            "SmartLink click recorded. No reward was issued."
    }


@app.post("/api/withdraw")
def withdraw(data: WithdrawIn):
    user = validate_init_data(data.init_data)
    ensure_user(user)

    method = data.method.lower()
    account = data.account.strip()

    if method not in ("bkash", "nagad"):
        raise HTTPException(
            status_code=400,
            detail="Invalid payment method"
        )

    if (
        not account.isdigit()
        or len(account) != 11
        or not account.startswith("01")
    ):
        raise HTTPException(
            status_code=400,
            detail=
            "Enter a valid 11-digit Bangladesh mobile number"
        )

    c = conn()

    u = c.execute(
        """
        SELECT points, status
        FROM users
        WHERE telegram_id=?
        """,
        (user["id"],)
    ).fetchone()

    if not u or u["status"] != "active":
        c.close()
        raise HTTPException(
            status_code=403,
            detail="Account is not active"
        )

    if u["points"] < 10:
        c.close()
        raise HTTPException(
            status_code=400,
            detail="Minimum withdrawal is 10 points"
        )

    wid = secrets.token_hex(8)

    c.execute(
        """
        INSERT INTO withdrawals
        (id, telegram_id, points, amount_bdt,
         method, account, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            wid,
            user["id"],
            10,
            10,
            method,
            account,
            "pending",
            int(time.time())
        )
    )

    c.execute(
        """
        UPDATE users
        SET points=points-10
        WHERE telegram_id=?
        """,
        (user["id"],)
    )

    c.commit()
    c.close()

    return {
        "ok": True,
        "id": wid,
        "status": "pending"
    }


@app.post("/api/withdrawals")
def withdrawals(data: InitIn):
    user = validate_init_data(data.init_data)

    c = conn()

    rows = c.execute(
        """
        SELECT id, amount_bdt, method,
               status, created_at
        FROM withdrawals
        WHERE telegram_id=?
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (user["id"],)
    ).fetchall()

    c.close()

    return {
        "items": [
            dict(r)
            for r in rows
        ]
}
