import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from models import User
from extensions import db, login_manager

auth_bp = Blueprint("auth", __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user:
            # ✅ Handle both hashed + plaintext for migration
            if check_password_hash(user.password, password) or user.password == password:
                # If user.password was plaintext, upgrade to hashed
                if user.password == password:
                    user.password = generate_password_hash(password)
                    db.session.commit()

                login_user(user)
                flash("Login successful!", "success")

                # redirect based on role
                if user.role == "SuperAdmin":
                    return redirect(url_for("admin.dashboard"))
                elif user.role == "HR":
                    return redirect(url_for("hr.dashboard_hr"))
                elif user.role == "OpsManager":
                    return redirect(url_for("ops_manager.dashboard_ops"))
                elif user.role == "OpsSupervisor":
                    return redirect(url_for("ops_supervisor.dashboard_ops_supervisor"))
                elif user.role == "FleetManager":
                    return redirect(url_for("fleet.dashboard_fleet"))
                elif user.role == "FinanceManager":
                    return redirect(url_for("finance.dashboard_finance"))

                return redirect(url_for("auth.login"))

        flash("Invalid username or password", "danger")
    return render_template("login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
