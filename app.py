import os
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from passlib.hash import pbkdf2_sha256


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///mentorship.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False)  # mentor or mentee
    bio = db.Column(db.Text, default="")
    skills = db.Column(db.Text, default="")
    availability = db.Column(db.String(120), default="")
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    mentorships_as_mentor = db.relationship(
        "MentorshipRequest", backref="mentor", foreign_keys="MentorshipRequest.mentor_id", lazy="dynamic"
    )
    mentorships_as_mentee = db.relationship(
        "MentorshipRequest", backref="mentee", foreign_keys="MentorshipRequest.mentee_id", lazy="dynamic"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = pbkdf2_sha256.hash(password)

    def check_password(self, password: str) -> bool:
        return pbkdf2_sha256.verify(password, self.password_hash)


class MentorshipRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    mentee_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    goal = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending, accepted, declined, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    messages = db.relationship("Message", backref="mentorship", lazy="dynamic", cascade="all, delete-orphan")


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mentorship_id = db.Column(db.Integer, db.ForeignKey("mentorship_request.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship("User")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role")
        password = request.form.get("password", "")

        if not all([name, email, role, password]):
            flash("Please fill out all required fields.", "error")
            return render_template("register.html")

        if role not in {"mentor", "mentee"}:
            flash("Please choose a valid role.", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return render_template("register.html")

        user = User(name=name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome to the mentorship community!", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Successfully signed in.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Signed out successfully.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    mentors = User.query.filter_by(role="mentor").all()
    mentees = User.query.filter_by(role="mentee").all()
    my_requests = MentorshipRequest.query.filter(
        (MentorshipRequest.mentor_id == current_user.id) | (MentorshipRequest.mentee_id == current_user.id)
    ).order_by(MentorshipRequest.created_at.desc())

    stats = {
        "total_users": User.query.count(),
        "mentor_count": len(mentors),
        "mentee_count": len(mentees),
        "active_mentorships": MentorshipRequest.query.filter_by(status="accepted").count(),
    }

    return render_template(
        "dashboard.html",
        mentors=mentors,
        mentees=mentees,
        my_requests=my_requests,
        stats=stats,
    )


@app.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.name = request.form.get("name", current_user.name)
        current_user.bio = request.form.get("bio", current_user.bio)
        current_user.skills = request.form.get("skills", current_user.skills)
        current_user.availability = request.form.get("availability", current_user.availability)
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("dashboard"))

    return render_template("edit_profile.html")


@app.route("/mentorships", methods=["GET", "POST"])
@login_required
def mentorships():
    if request.method == "POST":
        mentor_id = request.form.get("mentor_id")
        goal = request.form.get("goal", "").strip()

        if not mentor_id or not goal:
            flash("Please select a mentor and describe your goal.", "error")
        elif current_user.role != "mentee":
            flash("Only mentees can request mentorships.", "error")
        else:
            mentor = User.query.get(int(mentor_id))
            if mentor and mentor.role == "mentor":
                mentorship = MentorshipRequest(mentor_id=mentor.id, mentee_id=current_user.id, goal=goal)
                db.session.add(mentorship)
                db.session.commit()
                flash("Mentorship request created.", "success")
                return redirect(url_for("mentorships"))
            else:
                flash("Selected mentor is not available.", "error")

    available_mentors = User.query.filter_by(role="mentor").all()
    requests = MentorshipRequest.query.filter(
        (MentorshipRequest.mentor_id == current_user.id) | (MentorshipRequest.mentee_id == current_user.id)
    ).order_by(MentorshipRequest.created_at.desc())
    return render_template("mentorships.html", mentors=available_mentors, requests=requests)


@app.route("/mentorships/<int:request_id>/accept", methods=["POST"])
@login_required
def accept_request(request_id):
    mentorship = MentorshipRequest.query.get_or_404(request_id)
    if mentorship.mentor_id != current_user.id:
        flash("Only the assigned mentor can accept this request.", "error")
        return redirect(url_for("mentorships"))

    mentorship.status = "accepted"
    db.session.commit()
    flash("Mentorship accepted. Start collaborating!", "success")
    return redirect(url_for("mentorships"))


@app.route("/mentorships/<int:request_id>/decline", methods=["POST"])
@login_required
def decline_request(request_id):
    mentorship = MentorshipRequest.query.get_or_404(request_id)
    if mentorship.mentor_id != current_user.id:
        flash("Only the assigned mentor can decline this request.", "error")
        return redirect(url_for("mentorships"))

    mentorship.status = "declined"
    db.session.commit()
    flash("Request declined.", "info")
    return redirect(url_for("mentorships"))


@app.route("/mentorships/<int:request_id>/complete", methods=["POST"])
@login_required
def complete_request(request_id):
    mentorship = MentorshipRequest.query.get_or_404(request_id)
    if current_user.id not in {mentorship.mentor_id, mentorship.mentee_id}:
        flash("You cannot complete an unrelated request.", "error")
        return redirect(url_for("mentorships"))

    mentorship.status = "completed"
    db.session.commit()
    flash("Mentorship marked as completed.", "success")
    return redirect(url_for("mentorships"))


@app.route("/mentorships/<int:request_id>/messages", methods=["GET", "POST"])
@login_required
def mentorship_messages(request_id):
    mentorship = MentorshipRequest.query.get_or_404(request_id)
    if current_user.id not in {mentorship.mentor_id, mentorship.mentee_id}:
        flash("You are not part of this mentorship.", "error")
        return redirect(url_for("mentorships"))

    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if body:
            message = Message(mentorship_id=mentorship.id, sender_id=current_user.id, body=body)
            db.session.add(message)
            db.session.commit()
            flash("Message sent.", "success")
            return redirect(url_for("mentorship_messages", request_id=request_id))
        else:
            flash("Message cannot be empty.", "error")

    messages = mentorship.messages.order_by(Message.created_at.asc()).all()
    return render_template("messages.html", mentorship=mentorship, messages=messages)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=5000)
