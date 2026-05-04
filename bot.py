pip install flask requests
from flask import Flask, request
import requests
import sqlite3

TOKEN = "2120856079:JXJgdRHgQQjgIvS-8QTjzQEQmFm-rlwQ-Ig"
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"

app = Flask(__name__)

# ---------------- DB ----------------
def db():
    conn = sqlite3.connect("db.db")
    return conn

def init():
    conn = db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users(
        chat_id TEXT PRIMARY KEY,
        step TEXT,
        temp TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS reservations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT,
        date TEXT,
        time TEXT
    )""")

    conn.commit()
    conn.close()

init()

# ---------------- SEND ----------------
def send(chat_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if keyboard:
        payload["reply_markup"] = keyboard

    requests.post(f"{BASE_URL}/sendMessage", json=payload)

# ---------------- KEYBOARD ----------------
def menu():
    return {
        "inline_keyboard": [
            [{"text": "📅 رزرو نوبت", "callback_data": "reserve"}],
            [{"text": "📋 رزروهای من", "callback_data": "list"}],
            [{"text": "❌ لغو رزرو", "callback_data": "cancel"}]
        ]
    }

# ---------------- USER ----------------
def set_step(chat_id, step):
    conn = db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users(chat_id, step, temp) VALUES(?,?,COALESCE((SELECT temp FROM users WHERE chat_id=?),''))",
              (chat_id, step, chat_id))
    conn.commit()
    conn.close()

def get_user(chat_id):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT step, temp FROM users WHERE chat_id=?", (chat_id,))
    r = c.fetchone()
    conn.close()
    return r

def set_temp(chat_id, value):
    conn = db()
    c = conn.cursor()
    c.execute("UPDATE users SET temp=? WHERE chat_id=?", (value, chat_id))
    conn.commit()
    conn.close()

# ---------------- CHECK SLOT ----------------
def taken(date, time):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM reservations WHERE date=? AND time=?", (date, time))
    r = c.fetchone()
    conn.close()
    return r

# ---------------- MAIN ----------------
@app.route("/", methods=["POST"])
def bot():
    data = request.json

    # CALLBACK
    if "callback_query" in data:
        cb = data["callback_query"]
        chat_id = str(cb["message"]["chat"]["id"])
        data_cb = cb["data"]

        if data_cb == "reserve":
            send(chat_id, "📅 تاریخ را وارد کن:\nمثال: 1405/02/01")
            set_step(chat_id, "date")

        elif data_cb == "list":
            conn = db()
            c = conn.cursor()
            c.execute("SELECT * FROM reservations WHERE chat_id=?", (chat_id,))
            rows = c.fetchall()

            if not rows:
                send(chat_id, "هیچ رزروی نداری ❌")
            else:
                msg = "📋 رزروهای شما:\n"
                for r in rows:
                    msg += f"{r[0]} | {r[2]} | {r[3]}\n"
                send(chat_id, msg)

        elif data_cb == "cancel":
            send(chat_id, "ID رزرو را بفرست:")
            set_step(chat_id, "cancel")

        return "ok"

    # MESSAGE
    msg = data.get("message", {})
    if not msg:
        return "ok"

    chat_id = str(msg["chat"]["id"])
    text = msg.get("text", "")

    user = get_user(chat_id)
    step = user[0] if user else None

    # START
    if text == "/start":
        send(chat_id, "سلام 👋\nبه سیستم رزرو خوش آمدی", menu())
        return "ok"

    # DATE STEP
    if step == "date":
        set_temp(chat_id, text)
        send(chat_id, "⏰ ساعت را وارد کن:\nمثال: 1-2")
        set_step(chat_id, "time")
        return "ok"

    # TIME STEP
    if step == "time":
        date = user[1]
        time = text

        if taken(date, time):
            send(chat_id, "❌ این تایم قبلاً رزرو شده")
        else:
            conn = db()
            c = conn.cursor()
            c.execute("INSERT INTO reservations(chat_id, date, time) VALUES(?,?,?)",
                      (chat_id, date, time))
            conn.commit()
            conn.close()

            send(chat_id, "✅ رزرو شما ثبت شد")

        set_step(chat_id, None)
        send(chat_id, "منو:", menu())
        return "ok"

    # CANCEL STEP
    if step == "cancel":
        conn = db()
        c = conn.cursor()
        c.execute("DELETE FROM reservations WHERE id=? AND chat_id=?", (text, chat_id))
        conn.commit()
        conn.close()

        send(chat_id, "❌ رزرو حذف شد")
        set_step(chat_id, None)
        send(chat_id, "منو:", menu())
        return "ok"

    send(chat_id, "منو:", menu())
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)