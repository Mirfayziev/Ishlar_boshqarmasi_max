from flask import (
    Flask, render_template, redirect,
    url_for, request, session, flash, abort
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config["SECRET_KEY"] = "super-secret-key-change-this"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///imperiya.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ============================================
#  MODELLAR
# ============================================

class User(db.Model):
    """
    Foydalanuvchi:
    role: admin / manager / employee / consumer
    """
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="employee")
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Task(db.Model):
    """
    Boshqarma topshiriqlari
    """
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="yangi")  # yangi/jarayonda/bajarildi/rad_etildi
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.DateTime, nullable=True)
    is_overdue = db.Column(db.Boolean, default=False)

    assigned_to_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    assigned_to = db.relationship("User", backref="tasks")


class Vehicle(db.Model):
    """
    Boshqarma avtotransportlari
    """
    id = db.Column(db.Integer, primary_key=True)
    car_number = db.Column(db.String(50), nullable=False)  # davlat raqami
    model = db.Column(db.String(100))
    driver_name = db.Column(db.String(120))
    driver_phone = db.Column(db.String(50))

    distance_km = db.Column(db.Float, default=0)  # yurgan masofa
    fuel_limit = db.Column(db.Float, default=0)
    extra_fuel_limit = db.Column(db.Float, default=0)

    last_tech_inspection = db.Column(db.DateTime, nullable=True)
    next_tech_inspection = db.Column(db.DateTime, nullable=True)
    insurance_expiry = db.Column(db.DateTime, nullable=True)


class Contract(db.Model):
    """
    Shartnomalar: e-dokon / e-auktsion / tender / eng_yaxshi / togri
    """
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50))  # elektron_dokon, e_auktsion, tender, eng_yaxshi, togri
    total_amount = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default="jarayonda")  # jarayonda/bajarildi/bekor
    comment = db.Column(db.Text)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)


class Event(db.Model):
    """
    Tadbirlar & Mehmonlar xarajatlari
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    host_manager = db.Column(db.String(120))

    visits_count = db.Column(db.Integer, default=0)
    total_expenses = db.Column(db.Float, default=0)

    food_expenses = db.Column(db.Float, default=0)
    gifts_expenses = db.Column(db.Float, default=0)
    transport_expenses = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    gifts_given = db.Column(db.Boolean, default=False)


class Outsourcing(db.Model):
    """
    Outsourcing xizmatlari
    """
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(255), nullable=False)
    direction = db.Column(db.String(255))  # yo'nalish
    contract_amount = db.Column(db.Float, default=0)
    company_head = db.Column(db.String(255))
    employees_count = db.Column(db.Integer, default=0)
    employee_list = db.Column(db.Text)  # matn ko'rinishida ro'yxat

    access_approved = db.Column(db.Boolean, default=False)
    access_approved_at = db.Column(db.DateTime, nullable=True)


class SolarPanel(db.Model):
    """
    Quyosh panellari
    """
    id = db.Column(db.Integer, primary_key=True)
    building_address = db.Column(db.String(255), nullable=False)
    capacity_kw = db.Column(db.Float, default=0)
    installed_year = db.Column(db.Integer, nullable=True)
    efficiency_percent = db.Column(db.Float, default=0)
    total_produced_kwh = db.Column(db.Float, default=0)


class Request(db.Model):
    """
    Istemolchi (tashkilot ichki bo'limi yoki tashqaridan) талаба:
    masalan: tadbir o'tkazish, transport so'rash va h.k.
    """
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="yangi")  # yangi/qabul_qilindi/bajarildi/rad_etildi
    consumer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    consumer = db.relationship("User", backref="requests")


# ============================================
#  AUTH & ROLE DECORATOR
# ============================================

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            user = User.query.get(session["user_id"])
            if not user or user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ============================================
#  INIT ROUTE – DB CREATE, SUPER ADMIN
# ============================================

@app.route("/init-db")
def init_db():
    """
    Birinchi marta ishlatishda:
    /init-db ga kir -> DB yaratiladi, super admin ochiladi
    """
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        admin = User(
            full_name="Super Admin",
            username="admin",
            role="admin",
        )
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
    return "DB yaratildi. Super admin: login=admin, parol=admin123"


# ============================================
#  AUTH ROUTES
# ============================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username, is_active=True).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["role"] = user.role
            flash("Xush kelibsiz!", "success")
            return redirect(url_for("index"))
        flash("Login yoki parol noto'g'ri", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Tizimdan chiqdingiz", "info")
    return redirect(url_for("login"))


# ============================================
#  DASHBOARD ROUTES
# ============================================

@app.route("/")
@login_required
def index():
    role = session.get("role")
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    elif role == "manager":
        return redirect(url_for("manager_dashboard"))
    elif role == "employee":
        return redirect(url_for("employee_dashboard"))
    elif role == "consumer":
        return redirect(url_for("consumer_dashboard"))
    else:
        flash("Noma'lum rol", "danger")
        return redirect(url_for("logout"))


# ---------- ADMIN PANELI ----------

@app.route("/admin")
@login_required
@role_required("admin")
def admin_dashboard():
    return render_template(
        "admin_dashboard.html",
        user_count=User.query.count(),
        task_count=Task.query.count(),
        vehicle_count=Vehicle.query.count(),
        contract_count=Contract.query.count(),
        event_count=Event.query.count(),
        outsourcing_count=Outsourcing.query.count(),
        solar_count=SolarPanel.query.count(),
        request_count=Request.query.count(),
    )


@app.route("/admin/users")
@login_required
@role_required("admin")
def admin_users():
    users = User.query.order_by(User.id.desc()).all()
    return render_template("admin_users.html", users=users)


@app.route("/admin/users/create", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_create_user():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")

        if User.query.filter_by(username=username).first():
            flash("Bu login allaqachon mavjud", "danger")
        else:
            u = User(full_name=full_name, username=username, role=role)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            flash("Foydalanuvchi qo'shildi", "success")
            return redirect(url_for("admin_users"))

    return render_template("admin_user_form.html")


@app.route("/admin/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
@role_required("admin")
def admin_reset_password(user_id):
    u = User.query.get_or_404(user_id)
    new_password = request.form.get("new_password") or "123456"
    u.set_password(new_password)
    db.session.commit()
    flash(f"{u.full_name} uchun parol yangilandi", "success")
    return redirect(url_for("admin_users"))


# ---------- RAHBAR PANELI ----------

@app.route("/manager")
@login_required
@role_required("manager", "admin")
def manager_dashboard():
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(status="bajarildi").count()
    overdue_tasks = Task.query.filter_by(is_overdue=True).count()
    vehicles = Vehicle.query.count()
    contracts = Contract.query.count()
    events = Event.query.count()
    outsourcings = Outsourcing.query.count()
    solar_panels = SolarPanel.query.count()
    requests_count = Request.query.count()

    return render_template(
        "manager_dashboard.html",
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks,
        vehicles=vehicles,
        contracts=contracts,
        events=events,
        outsourcings=outsourcings,
        solar_panels=solar_panels,
        requests_count=requests_count,
    )


# ---------- HODIM PANELI ----------

@app.route("/employee")
@login_required
@role_required("employee", "manager", "admin")
def employee_dashboard():
    current_user = User.query.get(session["user_id"])
    total_tasks = Task.query.filter_by(assigned_to=current_user).count()
    completed_tasks = Task.query.filter_by(
        assigned_to=current_user, status="bajarildi"
    ).count()
    overdue_tasks = Task.query.filter_by(
        assigned_to=current_user, is_overdue=True
    ).count()
    return render_template(
        "employee_dashboard.html",
        user=current_user,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks,
    )


# ---------- ISTEMOLCHI PANELI ----------

@app.route("/consumer")
@login_required
@role_required("consumer")
def consumer_dashboard():
    current_user = User.query.get(session["user_id"])
    requests = Request.query.filter_by(consumer=current_user).order_by(
        Request.created_at.desc()
    )
    return render_template(
        "consumer_dashboard.html",
        user=current_user,
        requests=requests,
    )


# ============================================
#  TOPSHIRIQLAR (Tasks)
# ============================================

@app.route("/tasks")
@login_required
@role_required("manager", "admin")
def tasks_list():
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    employees = User.query.filter_by(role="employee", is_active=True).all()
    return render_template("tasks_list.html", tasks=tasks, employees=employees)


@app.route("/tasks/create", methods=["GET", "POST"])
@login_required
@role_required("manager", "admin")
def task_create():
    employees = User.query.filter_by(role="employee", is_active=True).all()
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        deadline_str = request.form.get("deadline")
        assigned_to_id = request.form.get("assigned_to_id")

        deadline = None
        if deadline_str:
            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
            except ValueError:
                deadline = None

        t = Task(
            title=title,
            description=description,
            deadline=deadline,
            assigned_to_id=assigned_to_id or None,
        )
        db.session.add(t)
        db.session.commit()
        flash("Topshiriq yaratildi", "success")
        return redirect(url_for("tasks_list"))

    return render_template("task_form.html", employees=employees)


@app.route("/tasks/<int:task_id>/status", methods=["POST"])
@login_required
@role_required("employee", "manager", "admin")
def task_update_status(task_id):
    t = Task.query.get_or_404(task_id)
    status = request.form.get("status")
    if status not in ["yangi", "jarayonda", "bajarildi", "rad_etildi"]:
        flash("Noto'g'ri holat", "danger")
    else:
        t.status = status
        if t.deadline and t.deadline < datetime.utcnow() and status != "bajarildi":
            t.is_overdue = True
        else:
            t.is_overdue = False
        db.session.commit()
        flash("Topshiriq holati yangilandi", "success")

    role = session.get("role")
    if role == "employee":
        return redirect(url_for("employee_dashboard"))
    elif role == "manager":
        return redirect(url_for("manager_dashboard"))
    elif role == "admin":
        return redirect(url_for("tasks_list"))
    return redirect(url_for("index"))


# ============================================
#  AVTOTRANSPORT
# ============================================

@app.route("/vehicles")
@login_required
@role_required("manager", "admin")
def vehicles_list():
    vehicles = Vehicle.query.order_by(Vehicle.id.desc()).all()
    return render_template("vehicles_list.html", vehicles=vehicles)


@app.route("/vehicles/create", methods=["GET", "POST"])
@login_required
@role_required("manager", "admin")
def vehicle_create():
    if request.method == "POST":
        car_number = request.form.get("car_number")
        model = request.form.get("model")
        driver_name = request.form.get("driver_name")
        driver_phone = request.form.get("driver_phone")
        distance_km = float(request.form.get("distance_km") or 0)
        fuel_limit = float(request.form.get("fuel_limit") or 0)
        extra_fuel_limit = float(request.form.get("extra_fuel_limit") or 0)

        v = Vehicle(
            car_number=car_number,
            model=model,
            driver_name=driver_name,
            driver_phone=driver_phone,
            distance_km=distance_km,
            fuel_limit=fuel_limit,
            extra_fuel_limit=extra_fuel_limit,
        )
        db.session.add(v)
        db.session.commit()
        flash("Avtotransport qo'shildi", "success")
        return redirect(url_for("vehicles_list"))

    return render_template("vehicle_form.html")


# ============================================
#  SHARTNOMALAR
# ============================================

@app.route("/contracts")
@login_required
@role_required("manager", "admin")
def contracts_list():
    contracts = Contract.query.order_by(Contract.id.desc()).all()
    return render_template("contracts_list.html", contracts=contracts)


@app.route("/contracts/create", methods=["GET", "POST"])
@login_required
@role_required("manager", "admin")
def contract_create():
    if request.method == "POST":
        title = request.form.get("title")
        type_ = request.form.get("type")
        total_amount = float(request.form.get("total_amount") or 0)
        status = request.form.get("status")
        comment = request.form.get("comment")

        c = Contract(
            title=title,
            type=type_,
            total_amount=total_amount,
            status=status,
            comment=comment,
        )
        db.session.add(c)
        db.session.commit()
        flash("Shartnoma qo'shildi", "success")
        return redirect(url_for("contracts_list"))

    return render_template("contract_form.html")


# ============================================
#  TADBIRLAR
# ============================================

@app.route("/events")
@login_required
@role_required("manager", "admin")
def events_list():
    events = Event.query.order_by(Event.date.desc()).all()
    return render_template("events_list.html", events=events)


@app.route("/events/create", methods=["GET", "POST"])
@login_required
@role_required("manager", "admin")
def event_create():
    if request.method == "POST":
        name = request.form.get("name")
        host_manager = request.form.get("host_manager")
        visits_count = int(request.form.get("visits_count") or 0)
        total_expenses = float(request.form.get("total_expenses") or 0)
        food_expenses = float(request.form.get("food_expenses") or 0)
        gifts_expenses = float(request.form.get("gifts_expenses") or 0)
        transport_expenses = float(request.form.get("transport_expenses") or 0)
        notes = request.form.get("notes")
        gifts_given = bool(request.form.get("gifts_given"))

        e = Event(
            name=name,
            host_manager=host_manager,
            visits_count=visits_count,
            total_expenses=total_expenses,
            food_expenses=food_expenses,
            gifts_expenses=gifts_expenses,
            transport_expenses=transport_expenses,
            notes=notes,
            gifts_given=gifts_given,
        )
        db.session.add(e)
        db.session.commit()
        flash("Tadbir qo'shildi", "success")
        return redirect(url_for("events_list"))

    return render_template("event_form.html")


# ============================================
#  OUTSOURCING
# ============================================

@app.route("/outsourcings")
@login_required
@role_required("manager", "admin")
def outsourcings_list():
    outs = Outsourcing.query.order_by(Outsourcing.id.desc()).all()
    return render_template("outsourcings_list.html", outsourcings=outs)


@app.route("/outsourcings/create", methods=["GET", "POST"])
@login_required
@role_required("manager", "admin")
def outsourcing_create():
    if request.method == "POST":
        company_name = request.form.get("company_name")
        direction = request.form.get("direction")
        contract_amount = float(request.form.get("contract_amount") or 0)
        company_head = request.form.get("company_head")
        employees_count = int(request.form.get("employees_count") or 0)
        employee_list = request.form.get("employee_list")

        o = Outsourcing(
            company_name=company_name,
            direction=direction,
            contract_amount=contract_amount,
            company_head=company_head,
            employees_count=employees_count,
            employee_list=employee_list,
        )
        db.session.add(o)
        db.session.commit()
        flash("Outsourcing tashkilot qo'shildi", "success")
        return redirect(url_for("outsourcings_list"))

    return render_template("outsourcing_form.html")


# ============================================
#  QUYOSH PANELLARI
# ============================================

@app.route("/solarpanels")
@login_required
@role_required("manager", "admin")
def solarpanels_list():
    panels = SolarPanel.query.order_by(SolarPanel.id.desc()).all()
    return render_template("solarpanels_list.html", panels=panels)


@app.route("/solarpanels/create", methods=["GET", "POST"])
@login_required
@role_required("manager", "admin")
def solarpanel_create():
    if request.method == "POST":
        building_address = request.form.get("building_address")
        capacity_kw = float(request.form.get("capacity_kw") or 0)
        installed_year = int(request.form.get("installed_year") or 0)
        efficiency_percent = float(request.form.get("efficiency_percent") or 0)
        total_produced_kwh = float(request.form.get("total_produced_kwh") or 0)

        s = SolarPanel(
            building_address=building_address,
            capacity_kw=capacity_kw,
            installed_year=installed_year,
            efficiency_percent=efficiency_percent,
            total_produced_kwh=total_produced_kwh,
        )
        db.session.add(s)
        db.session.commit()
        flash("Quyosh paneli qo'shildi", "success")
        return redirect(url_for("solarpanels_list"))

    return render_template("solarpanel_form.html")


# ============================================
#  ISTEMOLCHI TALABNOMALARI
# ============================================

@app.route("/requests")
@login_required
@role_required("manager", "admin")
def requests_list():
    requests_ = Request.query.order_by(Request.created_at.desc()).all()
    return render_template("requests_list.html", requests=requests_)


@app.route("/requests/create", methods=["GET", "POST"])
@login_required
@role_required("consumer")
def request_create():
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        r = Request(
            title=title,
            description=description,
            consumer_id=session["user_id"],
        )
        db.session.add(r)
        db.session.commit()
        flash("Talabnoma yuborildi", "success")
        return redirect(url_for("consumer_dashboard"))
    return render_template("request_form.html")


@app.route("/requests/<int:request_id>/status", methods=["POST"])
@login_required
@role_required("manager", "admin")
def request_update_status(request_id):
    r = Request.query.get_or_404(request_id)
    status = request.form.get("status")
    if status in ["yangi", "qabul_qilindi", "bajarildi", "rad_etildi"]:
        r.status = status
        db.session.commit()
        flash("Talabnoma holati yangilandi", "success")
    else:
        flash("Noto'g'ri holat", "danger")
    return redirect(url_for("requests_list"))


# ============================================
#  ERROR HANDLERS
# ============================================

@app.errorhandler(403)
def forbidden(e):
    return "Sizda bu sahifaga kirish huquqi yo'q", 403


@app.errorhandler(404)
def not_found(e):
    return "Sahifa topilmadi", 404


# ============================================
#  ENTRYPOINT
# ============================================

if __name__ == "__main__":
    app.run(debug=True)
