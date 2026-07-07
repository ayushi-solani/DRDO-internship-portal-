"""
DRDO Internship Portal - Flask Backend
=======================================
Roles: admin | hr | candidate
Run:   python app.py
"""

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, g)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import mysql.connector
from functools import wraps
from datetime import datetime
import json
import os
import sys

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "drdo-secret-2024-change-in-prod")

# ──────────────────────────────────────────────
# RESUME ↔ JOB-ROLE MATCHER
# ──────────────────────────────────────────────
RESUME_MATCHER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resume_matcher")
sys.path.insert(0, RESUME_MATCHER_DIR)

RESUME_UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads", "resumes")
os.makedirs(RESUME_UPLOAD_FOLDER, exist_ok=True)
ALLOWED_RESUME_EXTENSIONS = {"pdf"}

_resume_model = None
_resume_model_error = None
try:
    import joblib
    from match import score_resume
    from pdf_utils import extract_text_from_pdf

    _model_path = os.path.join(RESUME_MATCHER_DIR, "model.joblib")
    _resume_model = joblib.load(_model_path)
except Exception as exc:
    _resume_model_error = str(exc)
    print(f"[warn] Resume matcher unavailable: {_resume_model_error}")


def allowed_resume_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_RESUME_EXTENSIONS


def run_resume_match(pdf_path: str):
    if _resume_model is None:
        return None, _resume_model_error or "Resume matcher model is not available."

    resume_text = extract_text_from_pdf(pdf_path)
    if len(resume_text.split()) < 5:
        return None, "Could not extract meaningful text from that PDF - is it a scanned image?"

    try:
        results = score_resume(_resume_model, resume_text)
    except Exception as exc:
        return None, f"Scoring failed: {exc}"

    results = [
        {"role": str(r["role"]), "ml_match_pct": float(r["ml_match_pct"]),
         "similarity_pct": float(r["similarity_pct"])}
        for r in results
    ]
    return results, None


# ──────────────────────────────────────────────
# DATABASE CONFIG  (edit as needed)
# ──────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "localhost"),
    "user":     os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASS", "root"),
    "database": os.environ.get("DB_NAME", "drdo_portal"),
    "autocommit": False,
}


def get_db():
    if "db" not in g:
        g.db = mysql.connector.connect(**DB_CONFIG)
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, params=(), one=False, commit=False):
    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute(sql, params)
    if commit:
        db.commit()
        return cur.lastrowid
    rows = cur.fetchall()
    return rows[0] if (one and rows) else rows


# ──────────────────────────────────────────────
# AUTH DECORATORS
# ──────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get("role") not in roles:
                flash("Access denied.", "danger")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ──────────────────────────────────────────────
# PUBLIC ROUTES
# ──────────────────────────────────────────────
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for(f"{session['role']}_dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        email    = request.form["email"].strip().lower()
        password = request.form["password"]
        # is_approved check added for 17-table schema
        user = query(
            "SELECT * FROM users WHERE email=%s AND is_active=1 AND is_approved=1",
            (email,), one=True
        )

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"]   = user["id"]
            session["user_name"] = user["full_name"]
            session["role"]      = user["role"]
            session["user_phone"] = user.get("phone", "")
            flash(f"Welcome, {user['full_name']}!", "success")
            return redirect(url_for("index"))
        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email     = request.form["email"].strip().lower()
        phone     = request.form.get("phone", "").strip()
        password  = request.form["password"]
        confirm   = request.form["confirm_password"]

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        existing = query("SELECT id FROM users WHERE email=%s", (email,), one=True)
        if existing:
            flash("Email already registered.", "danger")
            return render_template("register.html")

        hashed = generate_password_hash(password)
        # is_approved=1 for candidates (self-registration)
        uid = query(
            "INSERT INTO users (full_name, email, password_hash, role, phone, is_approved) VALUES (%s,%s,%s,'candidate',%s,1)",
            (full_name, email, hashed, phone), commit=True
        )
        query("INSERT INTO candidate_profiles (user_id) VALUES (%s)", (uid,), commit=True)
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ──────────────────────────────────────────────
# CANDIDATE ROUTES
# ──────────────────────────────────────────────
@app.route("/candidate/dashboard")
@login_required
@role_required("candidate")
def candidate_dashboard():
    apps = query("""
        SELECT a.*, ip.title, ip.location, ip.stipend, d.name AS department
        FROM applications a
        JOIN internship_positions ip ON ip.id = a.position_id
        LEFT JOIN departments d ON d.id = ip.department_id
        WHERE a.candidate_id = %s
        ORDER BY a.applied_at DESC
    """, (session["user_id"],))

    profile = query("SELECT * FROM candidate_profiles WHERE user_id=%s",
                    (session["user_id"],), one=True)
    resume_match = None
    if profile and profile.get("resume_match_json"):
        resume_match = {
            "best_role": profile["resume_best_role"],
            "best_pct":  profile["resume_best_pct"],
            "breakdown": json.loads(profile["resume_match_json"]),
        }

    return render_template("candidate_dashboard.html",
                           applications=apps, resume_match=resume_match)


@app.route("/candidate/apply", methods=["GET", "POST"])
@login_required
@role_required("candidate")
def candidate_apply():
    positions = query("""
        SELECT ip.*, u.full_name AS hr_name, d.name AS department
        FROM internship_positions ip
        JOIN users u ON u.id = ip.created_by
        LEFT JOIN departments d ON d.id = ip.department_id
        WHERE ip.is_active=1 AND (ip.deadline IS NULL OR ip.deadline >= CURDATE())
        ORDER BY ip.created_at DESC
    """)

    if request.method == "POST":
        pos_id       = request.form["position_id"]
        cover_letter = request.form.get("cover_letter", "").strip()

        dup = query("SELECT id FROM applications WHERE candidate_id=%s AND position_id=%s",
                    (session["user_id"], pos_id), one=True)
        if dup:
            flash("You have already applied for this position.", "warning")
            return redirect(url_for("candidate_dashboard"))

        app_id = query(
            "INSERT INTO applications (candidate_id, position_id, cover_letter) VALUES (%s,%s,%s)",
            (session["user_id"], pos_id, cover_letter), commit=True
        )
        query(
            "INSERT INTO application_history (application_id, old_status, new_status, remarks, changed_by) VALUES (%s,%s,%s,%s,%s)",
            (app_id, None, "Submitted", "Application submitted by candidate.", session["user_id"]),
            commit=True
        )
        flash("Application submitted successfully!", "success")
        return redirect(url_for("candidate_dashboard"))

    return render_template("candidate_apply.html", positions=positions)


@app.route("/candidate/application/<int:app_id>")
@login_required
@role_required("candidate")
def candidate_application_detail(app_id):
    application = query("""
        SELECT a.*, ip.title, ip.location, ip.description,
               ip.stipend, ip.duration, d.name AS department
        FROM applications a
        JOIN internship_positions ip ON ip.id = a.position_id
        LEFT JOIN departments d ON d.id = ip.department_id
        WHERE a.id=%s AND a.candidate_id=%s
    """, (app_id, session["user_id"]), one=True)

    if not application:
        flash("Application not found.", "danger")
        return redirect(url_for("candidate_dashboard"))

    history = query("""
        SELECT ah.*, u.full_name AS changed_by_name
        FROM application_history ah
        JOIN users u ON u.id = ah.changed_by
        WHERE ah.application_id=%s
        ORDER BY ah.changed_at ASC
    """, (app_id,))

    return render_template("candidate_application_detail.html",
                           application=application, history=history)


# ──────────────────────────────────────────────
# CANDIDATE PROFILE
# ──────────────────────────────────────────────
@app.route("/candidate/profile", methods=["GET", "POST"])
@login_required
@role_required("candidate")
def candidate_profile():
    profile = query("SELECT * FROM candidate_profiles WHERE user_id=%s",
                    (session["user_id"],), one=True)

    if request.method == "POST":
        query("""
            UPDATE candidate_profiles SET
              dob=%s, gender=%s, address=%s, college=%s, degree=%s,
              branch=%s, graduation_year=%s, cgpa=%s, skills=%s,
              linkedin_url=%s, github_url=%s
            WHERE user_id=%s
        """, (
            request.form.get("dob") or None,
            request.form.get("gender") or None,
            request.form.get("address", ""),
            request.form.get("college", ""),
            request.form.get("degree", ""),
            request.form.get("branch", ""),
            request.form.get("graduation_year") or None,
            request.form.get("cgpa") or None,
            request.form.get("skills", ""),
            request.form.get("linkedin_url", ""),
            request.form.get("github_url", ""),
            session["user_id"]
        ), commit=True)

        # Resume upload
        resume_file = request.files.get("resume")
        if resume_file and resume_file.filename:
            if not allowed_resume_file(resume_file.filename):
                flash("Resume must be a PDF file.", "danger")
                return redirect(url_for("candidate_profile"))

            filename  = secure_filename(f"user{session['user_id']}_{resume_file.filename}")
            save_path = os.path.join(RESUME_UPLOAD_FOLDER, filename)
            resume_file.save(save_path)
            resume_url = f"uploads/resumes/{filename}"

            results, error = run_resume_match(save_path)
            if error:
                query("UPDATE candidate_profiles SET resume_url=%s WHERE user_id=%s",
                      (resume_url, session["user_id"]), commit=True)
                flash(f"Resume uploaded, but could not be auto-scored: {error}", "warning")
            else:
                best = results[0]
                query("""
                    UPDATE candidate_profiles SET
                      resume_url=%s, resume_best_role=%s, resume_best_pct=%s,
                      resume_match_json=%s, resume_matched_at=%s
                    WHERE user_id=%s
                """, (
                    resume_url, best["role"], best["ml_match_pct"],
                    json.dumps(results), datetime.now(), session["user_id"]
                ), commit=True)
                flash(f"Resume uploaded! Best-fit role: {best['role']} "
                      f"({best['ml_match_pct']:.1f}% match).", "success")
        else:
            flash("Profile updated!", "success")

        return redirect(url_for("candidate_profile"))

    resume_match = None
    if profile and profile.get("resume_match_json"):
        resume_match = {
            "best_role": profile["resume_best_role"],
            "best_pct":  profile["resume_best_pct"],
            "breakdown": json.loads(profile["resume_match_json"]),
        }

    return render_template("candidate_profile.html",
                           profile=profile, resume_match=resume_match)


# ──────────────────────────────────────────────
# HR ROUTES
# ──────────────────────────────────────────────
@app.route("/hr/dashboard")
@login_required
@role_required("hr")
def hr_dashboard():
    stats = {
        "total":       query("SELECT COUNT(*) AS c FROM applications", one=True)["c"],
        "submitted":   query("SELECT COUNT(*) AS c FROM applications WHERE status='Submitted'", one=True)["c"],
        "shortlisted": query("SELECT COUNT(*) AS c FROM applications WHERE status='Shortlisted'", one=True)["c"],
        "selected":    query("SELECT COUNT(*) AS c FROM applications WHERE status='Selected'", one=True)["c"],
    }
    applications = query("""
        SELECT a.*, u.full_name AS candidate_name, u.email AS candidate_email,
               ip.title AS position_title, d.name AS department
        FROM applications a
        JOIN users u ON u.id = a.candidate_id
        JOIN internship_positions ip ON ip.id = a.position_id
        LEFT JOIN departments d ON d.id = ip.department_id
        ORDER BY a.applied_at DESC
    """)
    return render_template("hr_dashboard.html", stats=stats, applications=applications)


@app.route("/hr/application/<int:app_id>", methods=["GET", "POST"])
@login_required
@role_required("hr")
def hr_application_detail(app_id):
    application = query("""
        SELECT a.*, u.full_name AS candidate_name, u.email AS candidate_email,
               u.phone AS candidate_phone,
               ip.title, ip.location, ip.description,
               ip.stipend, ip.duration, d.name AS department,
               cp.college, cp.degree, cp.branch, cp.graduation_year,
               cp.cgpa, cp.skills, cp.resume_url,
               cp.resume_best_role, cp.resume_best_pct,
               cp.linkedin_url, cp.github_url
        FROM applications a
        JOIN users u ON u.id = a.candidate_id
        LEFT JOIN candidate_profiles cp ON cp.user_id = u.id
        JOIN internship_positions ip ON ip.id = a.position_id
        LEFT JOIN departments d ON d.id = ip.department_id
        WHERE a.id=%s
    """, (app_id,), one=True)

    if not application:
        flash("Application not found.", "danger")
        return redirect(url_for("hr_dashboard"))

    if request.method == "POST":
        new_status = request.form["status"]
        remarks    = request.form.get("remarks", "").strip()
        old_status = application["status"]

        query("UPDATE applications SET status=%s, hr_remarks=%s, reviewed_by=%s, reviewed_at=%s WHERE id=%s",
              (new_status, remarks, session["user_id"], datetime.now(), app_id), commit=True)
        query("""
            INSERT INTO application_history
            (application_id, old_status, new_status, remarks, changed_by)
            VALUES (%s,%s,%s,%s,%s)
        """, (app_id, old_status, new_status, remarks, session["user_id"]), commit=True)

        flash(f"Status updated to '{new_status}'.", "success")
        return redirect(url_for("hr_application_detail", app_id=app_id))

    history = query("""
        SELECT ah.*, u.full_name AS changed_by_name
        FROM application_history ah
        JOIN users u ON u.id = ah.changed_by
        WHERE ah.application_id=%s
        ORDER BY ah.changed_at ASC
    """, (app_id,))

    statuses = ["Submitted", "Under Review", "Shortlisted",
                "Interview Scheduled", "Selected", "Rejected"]
    return render_template("hr_application_detail.html",
                           application=application, history=history,
                           statuses=statuses)


@app.route("/hr/positions", methods=["GET", "POST"])
@login_required
@role_required("hr")
def hr_positions():
    if request.method == "POST":
        query("""
            INSERT INTO internship_positions
            (title, department_id, location, description, requirements,
             duration, stipend, total_seats, deadline, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form["title"],
            request.form.get("department_id") or None,
            request.form.get("location", "DRDO HQ, New Delhi"),
            request.form.get("description", ""),
            request.form.get("requirements", ""),
            request.form.get("duration", ""),
            request.form.get("stipend") or None,
            int(request.form.get("total_seats", 1)),
            request.form.get("deadline") or None,
            session["user_id"]
        ), commit=True)
        flash("Internship position created!", "success")
        return redirect(url_for("hr_positions"))

    positions = query("""
        SELECT ip.*, d.name AS department,
               (SELECT COUNT(*) FROM applications a WHERE a.position_id=ip.id) AS applicant_count
        FROM internship_positions ip
        LEFT JOIN departments d ON d.id = ip.department_id
        WHERE ip.created_by=%s
        ORDER BY ip.created_at DESC
    """, (session["user_id"],))

    departments = query("SELECT id, name FROM departments WHERE is_active=1")
    return render_template("hr_positions.html", positions=positions, departments=departments)


@app.route("/hr/positions/<int:pos_id>/toggle")
@login_required
@role_required("hr")
def hr_toggle_position(pos_id):
    pos = query("SELECT is_active FROM internship_positions WHERE id=%s AND created_by=%s",
                (pos_id, session["user_id"]), one=True)
    if pos:
        new_val = 0 if pos["is_active"] else 1
        query("UPDATE internship_positions SET is_active=%s WHERE id=%s",
              (new_val, pos_id), commit=True)
        flash("Position updated.", "success")
    return redirect(url_for("hr_positions"))


# ──────────────────────────────────────────────
# ADMIN ROUTES
# ──────────────────────────────────────────────
@app.route("/admin/dashboard")
@login_required
@role_required("admin")
def admin_dashboard():
    stats = {
        "users":        query("SELECT COUNT(*) AS c FROM users", one=True)["c"],
        "hrs":          query("SELECT COUNT(*) AS c FROM users WHERE role='hr'", one=True)["c"],
        "candidates":   query("SELECT COUNT(*) AS c FROM users WHERE role='candidate'", one=True)["c"],
        "positions":    query("SELECT COUNT(*) AS c FROM internship_positions", one=True)["c"],
        "applications": query("SELECT COUNT(*) AS c FROM applications", one=True)["c"],
        "pending_hr":   query("SELECT COUNT(*) AS c FROM users WHERE role='hr' AND is_approved=0", one=True)["c"],
    }
    users = query("""
        SELECT id, full_name, email, role, phone, is_active, is_approved, created_at
        FROM users ORDER BY created_at DESC
    """)
    departments = query("SELECT id, name FROM departments WHERE is_active=1")
    return render_template("admin_dashboard.html", stats=stats, users=users, departments=departments)


@app.route("/admin/users/<int:uid>/toggle")
@login_required
@role_required("admin")
def admin_toggle_user(uid):
    user = query("SELECT is_active FROM users WHERE id=%s", (uid,), one=True)
    if user:
        query("UPDATE users SET is_active=%s WHERE id=%s",
              (0 if user["is_active"] else 1, uid), commit=True)
        flash("User status updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/users/<int:uid>/approve")
@login_required
@role_required("admin")
def admin_approve_user(uid):
    query("UPDATE users SET is_approved=1 WHERE id=%s", (uid,), commit=True)
    flash("HR account approved.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/add_hr", methods=["POST"])
@login_required
@role_required("admin")
def admin_add_hr():
    full_name = request.form["full_name"].strip()
    email     = request.form["email"].strip().lower()
    password  = request.form["password"]
    phone     = request.form.get("phone", "").strip()

    existing = query("SELECT id FROM users WHERE email=%s", (email,), one=True)
    if existing:
        flash("Email already registered.", "danger")
        return redirect(url_for("admin_dashboard"))

    hashed = generate_password_hash(password)
    # is_approved=0 for HR — admin must approve before first login
    query("INSERT INTO users (full_name, email, password_hash, role, phone, is_approved) VALUES (%s,%s,%s,'hr',%s,0)",
          (full_name, email, hashed, phone), commit=True)
    flash(f"HR account created for {full_name}. Approve it to activate.", "success")
    return redirect(url_for("admin_dashboard"))


# ──────────────────────────────────────────────
# JINJA HELPERS
# ──────────────────────────────────────────────
@app.template_filter("status_color")
def status_color(status):
    colors = {
        "Submitted":           "secondary",
        "Under Review":        "info",
        "Shortlisted":         "primary",
        "Interview Scheduled": "warning",
        "Selected":            "success",
        "Rejected":            "danger",
    }
    return colors.get(status, "secondary")


@app.template_filter("datefmt")
def datefmt(value, fmt="%d %b %Y"):
    if value is None:
        return "—"
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return value
    return value.strftime(fmt)


if __name__ == "__main__":
    app.run(debug=True, port=5000)