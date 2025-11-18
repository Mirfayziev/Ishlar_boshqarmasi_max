import os
from flask import Flask, render_template, redirect, request, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests

# ------------------------
# Flask Config
# ------------------------
app = Flask(__name__)
app.secret_key = "super_secret_aziz"

# DATABASE CONFIG — AUTOMATIC SQLITE
db_url = os.getenv("DATABASE_URL")

# Postgres bo'lsa — formatni to'g'rilab qo'yamiz
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Agar DATABASE_URL BO‘LMASA — SQLite ishlaydi
if not db_url:
    db_url = "sqlite:///database.db"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ------------------------
# Telegram Push
# ------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        requests.post(API_URL, data={"chat_id": chat_id, "text": text})
    except:
        pass

# ------------------------
# MODELS
# ------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(120))
    role = db.Column(db.String(20))
    telegram_id = db.Column(db.String(50), nullable=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default="Yangi")
    deadline = db.Column(db.DateTime, nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

# ------------------------
# INIT DATABASE
# ------------------------
@app.route("/init-db")
def init_db():
    db.drop_all()
    db.create_all()

    admin = User(username="admin", password="admin123", role="admin")
    db.session.add(admin)
    db.session.commit()
    return "DB yaratildi! Login: admin / admin123"

# ------------------------
# AUTH
# ------------------------
@app.route("/")
def home():
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        user = User.query.filter_by(username=u, password=p).first()
        if user:
            session["user_id"] = user.id
            session["role"] = user.role
            return redirect("/admin" if user.role == "admin" else "/tasks")

        return render_template("login.html", error="Login yoki parol noto‘g‘ri")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ------------------------
# ADMIN PANEL
# ------------------------
@app.route("/admin")
def admin_panel():
    if session.get("role") != "admin":
        return redirect("/login")
    tasks = Task.query.all()
    users = User.query.filter_by(role="user").all()
    return render_template("admin_panel.html", tasks=tasks, users=users)

@app.route("/admin/add_task", methods=["POST"])
def admin_add_task():
    if session.get("role") != "admin":
        return redirect("/login")

    t = Task(
        title=request.form["title"],
        description=request.form["description"],
        deadline=datetime.strptime(request.form["deadline"], "%Y-%m-%d"),
        assigned_to=request.form["assigned_to"],
        status="Yangi",
    )
    db.session.add(t)
    db.session.commit()

    user = User.query.get(request.form["assigned_to"])
    if user.telegram_id:
        send_telegram(user.telegram_id, f"📩 Yangi topshiriq:\n📝 {t.title}\n⏳ {t.deadline}")

    return redirect("/admin")

# ------------------------
# USER TASK PANEL
# ------------------------
@app.route("/tasks")
def user_tasks():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    tasks = Task.query.filter_by(assigned_to=user_id).all()
    return render_template("user_tasks.html", tasks=tasks)

@app.route("/tasks/update/<int:task_id>/<string:action>")
def update_task(task_id, action):
    user_id = session.get("user_id")
    task = Task.query.get(task_id)

    if not task or task.assigned_to != user_id:
        return redirect("/tasks")

    if action == "start":
        task.status = "Jarayonda"
    elif action == "done":
        task.status = "Bajarildi"

        admin = User.query.filter_by(role="admin").first()
        if admin and admin.telegram_id:
            send_telegram(admin.telegram_id, f"✅ Hodim topshiriqni tugatdi:\n{task.title}")

    task.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect("/tasks")

# ------------------------
# ADMIN VERIFY
# ------------------------
@app.route("/admin/verify/<int:task_id>/<string:action>")
def verify_task(task_id, action):
    if session.get("role") != "admin":
        return redirect("/login")

    task = Task.query.get(task_id)
    user = User.query.get(task.assigned_to)

    if action == "accept":
        task.status = "Tasdiqlandi"
        if user.telegram_id:
            send_telegram(user.telegram_id, f"🎉 Tasdiqlandi:\n{task.title}")

    elif action == "reject":
        task.status = "Rad etildi"
        if user.telegram_id:
            send_telegram(user.telegram_id, f"❌ Rad etildi:\n{task.title}")

    task.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect("/admin")

# ------------------------
# RUN
# ------------------------
if __name__ == "__main__":
    app.run(debug=True)

