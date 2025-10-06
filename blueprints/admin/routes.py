from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import Offboarding, User, Driver
from extensions import db, mail
from flask_mail import Message
from datetime import datetime
import os
from werkzeug.security import check_password_hash, generate_password_hash

# ✅ Blueprint for SuperAdmin/Admin
admin_bp = Blueprint("admin", __name__)

UPLOAD_FOLDER = "static/uploads"

def safe_date(value):
    """Return formatted date if value is datetime/date, else return value or None."""
    if not value:
        return None
    try:
        return value.strftime("%Y-%m-%d")
    except Exception:
        return value  # already a string

def safe_datetime(value):
    """Return formatted datetime if value is datetime, else return value or None."""
    if not value:
        return None
    try:
        return value.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value

# -------------------------
# SuperAdmin Dashboard
# -------------------------
@admin_bp.route("/")
@login_required
def dashboard():
    if current_user.role != "SuperAdmin":
        return "Forbidden", 403

    # --------------------------
    # Users
    # --------------------------
    users = User.query.filter(User.id != current_user.id).all()
    users_dicts = [
        {
            "id": u.id,
            "username": u.username,
            "name": u.name,
            "designation": u.designation,
            "branch_city": u.branch_city,
            "email": u.email,
            "role": u.role,
        }
        for u in users
    ]

    # --------------------------
    # Drivers & Offboarding
    # --------------------------
    drivers = Driver.query.all()
    offboarding_records = Offboarding.query.all()

    total_drivers = int(len(drivers) or 0)
    total_users = int(len(users) or 0)

    # Separate offboarding by status
    pending_offboarding_records = [o for o in offboarding_records if o.status != "Completed"]
    completed_offboarding_records = [o for o in offboarding_records if o.status == "Completed"]

    pending_offboarding_drivers = [o.driver for o in pending_offboarding_records]
    completed_offboarding_drivers = [o.driver for o in completed_offboarding_records]

    # --------------------------
    # Counts logic
    # --------------------------
    offboarded_ids = {o.driver_id for o in offboarding_records}

    # Pending onboarding = not yet completed
    total_pending_onboarded = int(sum(1 for d in drivers if d.onboarding_stage != "Completed") or 0)

    # Completed onboarding = completed but NOT offboarded
    total_completed_onboarded = int(
        sum(1 for d in drivers if d.onboarding_stage == "Completed" and d.id not in offboarded_ids)
    )

    # Offboarding counts
    total_pending_offboarded = int(len(pending_offboarding_drivers) or 0)
    total_completed_offboarded = int(len(completed_offboarding_drivers) or 0)

    # --------------------------
    # Helpers
    # --------------------------
    def safe_date(value):
        if not value:
            return None
        try:
            return value.strftime("%Y-%m-%d")
        except Exception:
            return value

    def safe_datetime(value):
        if not value:
            return None
        try:
            return value.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return value

    # Get all offboarding driver IDs
    offboarded_ids = {o.driver_id for o in offboarding_records}

    def serialize_driver(d):
        return {
            "id": d.id,
            "full_name": d.full_name,
            "iqama_number": d.iqama_number,
            "platform": d.platform,
            "platform_id": d.platform_id,
            "car_details": d.car_details,
            "onboarding_stage": d.onboarding_stage,
            "assignment_date": safe_date(d.assignment_date),
            "finance_approved_at": safe_datetime(d.finance_approved_at),
            "tamm_authorized": d.tamm_authorized,
            # ✅ New flags for template
            "fully_onboarded": d.onboarding_stage == "Completed",
            "in_offboarding": d.id in offboarded_ids
    }


    driver_dicts = [serialize_driver(d) for d in drivers]
    pending_offboarding_driver_dicts = [serialize_driver(d) for d in pending_offboarding_drivers]
    completed_offboarding_driver_dicts = [serialize_driver(d) for d in completed_offboarding_drivers]

    # ✅ Filter fully onboarded drivers who are NOT in offboarding
    fully_onboarded_only = [d for d in driver_dicts if d["fully_onboarded"] and not d["in_offboarding"]]

    # --------------------------
    # Render Dashboard
    # --------------------------
    return render_template(
        "dashboard.html",
        users=users_dicts,
        drivers=driver_dicts,
        fully_onboarded_drivers=fully_onboarded_only,  # ✅ new variable for tab
        total_users=total_users,
        total_drivers=total_drivers,
        total_pending_onboarded=total_pending_onboarded,
        total_completed_onboarded=total_completed_onboarded,
        total_pending_offboarded=total_pending_offboarded,
        total_completed_offboarded=total_completed_offboarded,
        pending_offboarding_drivers=pending_offboarding_driver_dicts,
        completed_offboarding_drivers=completed_offboarding_driver_dicts,
    )



# -------------------------
# Add Driver (NEW)
# -------------------------
@admin_bp.route("/driver/add", methods=["POST"])
@login_required
def add_driver():
    if current_user.role != "SuperAdmin":
        flash("Access Denied", "danger")
        return redirect(url_for("admin.dashboard"))

    # Collect form data
    full_name = request.form.get("full_name")
    iqama_number = request.form.get("iqama_number")
    iqama_expiry_date = request.form.get("iqama_expiry_date")
    nationality = request.form.get("nationality")
    mobile_number = request.form.get("mobile_number")
    platform = request.form.get("platform")
    platform_id = request.form.get("platform_id")
    car_details = request.form.get("car_details")
    assignment_date = request.form.get("assignment_date")

    # Handle uploads
    iqama_card_upload = None
    if "iqama_card_upload" in request.files:
        file = request.files["iqama_card_upload"]
        if file.filename:
            filename = f"iqama_{datetime.utcnow().timestamp()}_{file.filename}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            iqama_card_upload = filename

    tamm_authorization_ss = None
    if "tamm_authorization_ss" in request.files:
        file = request.files["tamm_authorization_ss"]
        if file.filename:
            filename = f"tamm_{datetime.utcnow().timestamp()}_{file.filename}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            tamm_authorization_ss = filename

    new_driver = Driver(
        full_name=full_name,
        iqama_number=iqama_number,
        iqama_expiry_date=datetime.strptime(iqama_expiry_date, "%Y-%m-%d").date() if iqama_expiry_date else None,
        nationality=nationality,
        mobile_number=mobile_number,
        platform=platform,
        platform_id=platform_id,
        car_details=car_details,
        assignment_date=datetime.strptime(assignment_date, "%Y-%m-%d").date() if assignment_date else None,
        iqama_card_upload=iqama_card_upload,
        tamm_authorization_ss=tamm_authorization_ss,
    )

    db.session.add(new_driver)
    db.session.commit()

    flash(f"Driver {new_driver.full_name} added successfully.", "success")
    return redirect(url_for("admin.dashboard"))

# -------------------------
# Update Driver (Enhanced)
# -------------------------
@admin_bp.route("/driver/<int:driver_id>/update", methods=["POST"])
@login_required
def update_driver(driver_id):
    driver = Driver.query.get_or_404(driver_id)

    # Update fields
    driver.full_name = request.form.get("full_name", driver.full_name)
    driver.iqama_number = request.form.get("iqama_number", driver.iqama_number)
    driver.nationality = request.form.get("nationality", driver.nationality)
    driver.mobile_number = request.form.get("mobile_number", driver.mobile_number)
    driver.previous_sponsor_number = request.form.get("previous_sponsor_number", driver.previous_sponsor_number)
    driver.platform = request.form.get("platform", driver.platform)
    driver.platform_id = request.form.get("platform_id", driver.platform_id)
    driver.issued_mobile_number = request.form.get("issued_mobile_number", driver.issued_mobile_number)
    driver.issued_device_id = request.form.get("issued_device_id", driver.issued_device_id)
    driver.mobile_issued = request.form.get("mobile_issued") == "true"
    driver.car_details = request.form.get("car_details", driver.car_details)
    driver.tamm_authorized = request.form.get("tamm_authorized") == "true"
    driver.transfer_fee_paid = request.form.get("transfer_fee_paid") == "true"

    # Dates
    iqama_expiry_date = request.form.get("iqama_expiry_date")
    if iqama_expiry_date:
        driver.iqama_expiry_date = datetime.strptime(iqama_expiry_date, "%Y-%m-%d").date()

    assignment_date = request.form.get("assignment_date")
    if assignment_date:
        driver.assignment_date = datetime.strptime(assignment_date, "%Y-%m-%d").date()

    transfer_fee_paid_at = request.form.get("transfer_fee_paid_at")
    if transfer_fee_paid_at:
        driver.transfer_fee_paid_at = datetime.strptime(transfer_fee_paid_at, "%Y-%m-%dT%H:%M")

    driver.transfer_fee_amount = request.form.get("transfer_fee_amount") or None

    # File uploads
    if "tamm_authorization_ss" in request.files:
        file = request.files["tamm_authorization_ss"]
        if file.filename:
            filename = f"tamm_{datetime.utcnow().timestamp()}_{file.filename}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            driver.tamm_authorization_ss = filename

    if "transfer_fee_receipt" in request.files:
        file = request.files["transfer_fee_receipt"]
        if file.filename:
            filename = f"receipt_{datetime.utcnow().timestamp()}_{file.filename}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            driver.transfer_fee_receipt = filename

    db.session.commit()
    flash("Driver details updated successfully.", "success")
    return redirect(url_for("admin.dashboard"))

# -------------------------
# Delete Driver
# -------------------------
@admin_bp.route("/driver/<int:driver_id>/delete", methods=["POST"])
@login_required
def delete_driver(driver_id):
    if current_user.role != "SuperAdmin":
        flash("Access Denied", "danger")
        return redirect(url_for("admin.dashboard"))

    driver = Driver.query.get_or_404(driver_id)
    db.session.delete(driver)
    db.session.commit()

    flash(f"Driver {driver.full_name} deleted successfully.", "success")
    return redirect(url_for("admin.dashboard"))

# -------------------------
# Add/Edit/Delete Users (unchanged)
# -------------------------
@admin_bp.route("/add_user", methods=["POST"])
@login_required
def add_user():
    
    if current_user.role != "SuperAdmin":
        return "Access Denied", 403

    username = request.form["username"]
    password = generate_password_hash(request.form["password"])
    role = request.form["role"]
    name = request.form["name"]
    designation = request.form["designation"]
    branch_city = request.form["branch_city"]
    email = request.form["email"]

    new_user = User(username=username, password=password, role=role,
                    name=name, designation=designation, branch_city=branch_city, email=email)
    db.session.add(new_user)
    db.session.commit()

    # Send email notification
    try:
        msg = Message("Your Account Has Been Created", recipients=[email])
        msg.body = f"Hello {name},\n\nYour account has been created.\nUsername: {username}\nUsername: {password}\n"
        mail.send(msg)
    except Exception as e:
        print(f"Email error: {e}")

    flash("User created successfully and email sent.", "success")
    return redirect(url_for("admin.dashboard"))


# -------------------------
# Edit User
# -------------------------
@admin_bp.route("/edit_user/<int:user_id>", methods=["POST"])
@login_required
def edit_user(user_id):
    if current_user.role != "SuperAdmin":
        flash("Access Denied", "danger")
        return redirect(url_for("admin.dashboard"))

    user = User.query.get_or_404(user_id)
    user.username = request.form.get("username", user.username)
    user.name = request.form.get("name", user.name)
    user.designation = request.form.get("designation", user.designation)
    user.branch_city = request.form.get("branch_city", user.branch_city)
    user.email = request.form.get("email", user.email)
    user.role = request.form.get("role", user.role)

    db.session.commit()
    flash(f"User {user.username} updated successfully.", "success")
    return redirect(url_for("admin.dashboard"))

# -------------------------
# Delete User
# -------------------------
@admin_bp.route("/delete_user/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if current_user.role != "SuperAdmin":
        flash("Access Denied", "danger")
        return redirect(url_for("admin.dashboard"))

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()

    flash(f"User {user.username} deleted successfully.", "success")
    return redirect(url_for("admin.dashboard"))

# -------------------------
# Change Password (for SuperAdmin)
# -------------------------
@admin_bp.route("/change_password", methods=["POST"])
@login_required
def change_password():
    if current_user.role != "SuperAdmin":
        flash("Access Denied", "danger")
        return redirect(url_for("admin.dashboard"))

    current_password = request.form["current_password"]
    new_password = request.form["new_password"]
    confirm_password = request.form["confirm_password"]

    if not check_password_hash(current_user.password, current_password):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for("admin.dashboard"))

    if new_password != confirm_password:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("admin.dashboard"))

    current_user.password = generate_password_hash(new_password)
    db.session.commit()
    flash("Your password has been updated successfully.", "success")
    return redirect(url_for("admin.dashboard"))
