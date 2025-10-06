from flask import Blueprint, render_template, request, redirect, url_for, flash , jsonify
from flask_login import login_required, current_user
from extensions import db, mail
from flask_mail import Message
from datetime import datetime, date
import os
from flask import current_app
from werkzeug.utils import secure_filename
from models import Offboarding, Driver, User
from sqlalchemy import or_


fleet_bp = Blueprint("fleet", __name__)

# -------------------------
# Fleet Manager Dashboard
# -------------------------
@fleet_bp.route("/dashboard")
@login_required
def dashboard_fleet():
    if current_user.role != "FleetManager":
        flash("Access denied", "danger")
        return redirect(url_for("auth.login"))

    onboarding_drivers = Driver.query.filter_by(onboarding_stage="Fleet Manager").all()

    offboarding_requests = (
        Offboarding.query
        .filter(
            or_(
                Offboarding.status == "Fleet",
                Offboarding.status == "pending_tamm"
            ),
            Offboarding.ops_supervisor_cleared_at.isnot(None)
        )
        .order_by(Offboarding.requested_at.desc())
        .all()
    )

    return render_template(
        "dashboard_fleet.html",
        onboarding_drivers=onboarding_drivers,
        offboarding_requests=offboarding_requests
    )
# -------------------------
# Assign Vehicle & Send to Finance
# -------------------------
@fleet_bp.route("/assign_vehicle/<int:driver_id>", methods=["POST"])
@login_required
def assign_vehicle(driver_id):
    """Assign vehicle to driver, upload TAMM authorization screenshot, and move to Finance stage."""
    if current_user.role != "FleetManager":
        flash("Access denied. Fleet Manager role required.", "danger")
        return redirect(url_for("auth.login"))

    driver = Driver.query.get_or_404(driver_id)

    # ✅ Collect & validate form data
    vehicle_plate = request.form.get("vehicle_plate", "").strip()
    vehicle_details = request.form.get("vehicle_details", "").strip()
    assignment_date = request.form.get("assignment_date", "").strip()
    tamm_authorized = request.form.get("tamm_authorized")

    current_app.logger.info(f"[DEBUG] request.files: {request.files}")
    current_app.logger.info(f"[DEBUG] tamm_file: {request.files.get('tamm_authorization_ss')}")

    tamm_file = request.files.get("tamm_authorization_ss")

    # ✅ Ensure required fields
    if not (vehicle_plate and vehicle_details and assignment_date and tamm_authorized):
        flash("All fields including TAMM Authorization must be filled before approval.", "danger")
        return redirect(url_for("fleet.dashboard_fleet"))

    # ✅ Ensure TAMM file uploaded
    if not tamm_file or not tamm_file.filename:
        flash("⚠️ TAMM Authorization Screenshot is required before approval.", "danger")
        return redirect(url_for("fleet.dashboard_fleet"))

    try:
        # ✅ Validate assignment date
        parsed_date = datetime.strptime(assignment_date, "%Y-%m-%d").date()
        if parsed_date > date.today():
            flash("Assignment date cannot be in the future.", "danger")
            return redirect(url_for("fleet.dashboard_fleet"))

        # ✅ Save uploaded TAMM screenshot with unique name
        ext = os.path.splitext(tamm_file.filename)[1].lower()
        safe_name = secure_filename(
            f"{driver.full_name}_{driver.iqama_number}_{vehicle_plate}_TAMM_Authorisation{ext}"
        )
        upload_path = os.path.join(current_app.config["UPLOAD_FOLDER"], safe_name)
        tamm_file.save(upload_path)

        # ✅ Store assignment + file info in DB
        driver.car_details = f"{vehicle_plate} - {vehicle_details}"
        driver.assignment_date = parsed_date
        driver.tamm_authorized = True
        driver.tamm_authorization_ss = safe_name  # <-- store filename

        # ✅ Mark Fleet Manager approval & move to Finance stage
        driver.mark_fleet_manager_approved()
        db.session.commit()

        # ✅ Notify Finance Team (Finance + FinanceManager)
        try:
            finance_users = User.query.filter(User.role.in_(["Finance", "FinanceManager"])).all()
            recipients = [f.email for f in finance_users if f.email]

            if recipients:
                msg = Message(
                    subject=f"Driver Ready for Finance Stage: {driver.full_name}",
                    recipients=recipients,
                    body=f"""
Hello Finance Team,

Driver {driver.full_name} has been assigned a vehicle by Fleet Manager.

Assigned Vehicle:
- Plate: {vehicle_plate}
- Details: {vehicle_details}
- Assignment Date: {driver.assignment_date.strftime('%Y-%m-%d')}
- TAMM Authorized: ✅ Yes (Screenshot uploaded)

Please log in and complete financial processing.

Login here: http://127.0.0.1:5000/dashboard/finance

Regards,
Fleet Team
"""
                )
                mail.send(msg)
                current_app.logger.info("[FLEET] Finance notification email sent successfully.")
            else:
                current_app.logger.warning("[FLEET] No finance users with email found. Skipping notification.")
        except Exception as e:
            current_app.logger.error(f"[FLEET] Could not notify Finance: {e}")

        flash(f"✅ Vehicle assigned to {driver.full_name} and driver moved to Finance stage.", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[FLEET] Error assigning vehicle: {e}")
        flash(f"❌ Error assigning vehicle: {str(e)}", "danger")

    return redirect(url_for("fleet.dashboard_fleet"))


# -------------------------
# Change Password
# -------------------------
@fleet_bp.route("/change_password", methods=["POST"])
@login_required
def change_password():
    """Allow Fleet Manager to change password securely."""
    from werkzeug.security import check_password_hash, generate_password_hash

    if current_user.role != "FleetManager":
        flash("Access denied. Fleet Manager role required.", "danger")
        return redirect(url_for("auth.login"))

    current_password = request.form["current_password"]
    new_password = request.form["new_password"]
    confirm_password = request.form["confirm_password"]

    if not check_password_hash(current_user.password, current_password):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for("fleet.dashboard_fleet"))

    if new_password != confirm_password:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("fleet.dashboard_fleet"))

    current_user.password = generate_password_hash(new_password)
    db.session.commit()

    flash("Password updated successfully.", "success")
    return redirect(url_for("fleet.dashboard_fleet"))


# -------------------------
# Fleet Manager Offboarding
# -------------------------

fleet_manager_bp = Blueprint("fleet_manager", __name__)

@fleet_bp.route("/api/clear_offboarding/<int:offboarding_id>", methods=["POST"])
@login_required
def fleet_clear_offboarding(offboarding_id):
    if current_user.role != "FleetManager":
        return jsonify({"success": False, "message": "Access denied"}), 403

    record = Offboarding.query.get_or_404(offboarding_id)

    try:
        data = request.get_json()
        record.fleet_cleared = True
        record.fleet_cleared_at = datetime.utcnow()
        record.fleet_damage_report = data.get("fleet_damage_report")
        record.fleet_damage_cost = float(data.get("fleet_damage_cost") or 0)

        # 🚀 Move to Finance stage
        record.status = "Finance"

        db.session.commit()

        # 📧 Notify Finance Team
        finance_users = User.query.filter(User.role.in_(["Finance", "FinanceManager"])).all()
        emails = [f.email for f in finance_users if f.email]
        if emails:
            msg = Message(
                subject=f"Driver sent to Finance for Offboarding: {record.driver.full_name}",
                recipients=emails,
                body=(
                    f"Dear Finance Team,\n\n"
                    f"Driver {record.driver.full_name} (Iqama: {record.driver.iqama_number}) "
                    f"has been cleared by Fleet Manager.\n\n"
                    f"Damage Report: {record.fleet_damage_report or 'N/A'}\n"
                    f"Damage Cost: {record.fleet_damage_cost or 0} SAR\n\n"
                    f"Please log in and proceed with settlement."
                )
            )
            mail.send(msg)

        return jsonify({
            "success": True,
            "driver_name": record.driver.full_name,
            "cleared_at": record.fleet_cleared_at.strftime("%Y-%m-%d %H:%M"),
            "damage_cost": record.fleet_damage_cost,
            "damage_report": record.fleet_damage_report
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[FLEET CLEAR OFFBOARDING ERROR] {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# -------------------------
# Fleet Manager Tamm revoking
# -------------------------
@fleet_bp.route("/api/revoke_tamm/<int:offboarding_id>", methods=["POST"])
@login_required
def revoke_tamm(offboarding_id):
    if current_user.role != "FleetManager":
        return jsonify({"success": False, "message": "Access denied"}), 403

    record = Offboarding.query.get_or_404(offboarding_id)
    data = request.get_json()

    try:
        # Only proceed if TAMM revocation is requested
        if not data.get("tamm_revoked"):
            return jsonify({"success": False, "message": "TAMM not revoked"}), 400

        # ✅ Mark driver as fully offboarded
        record.status = "Completed"
        record.fleet_cleared = True
        record.fleet_cleared_at = datetime.utcnow()

        # ✅ Mark TAMM revoked fields
        record.tamm_revoked = True
        record.tamm_revoked_at = datetime.utcnow()   # << add timestamp

        db.session.commit()

        # ✅ Send email to HR/Admin
        recipients = [u.email for u in User.query.filter(User.role.in_(["HR", "Admin"])).all() if u.email]
        if recipients:
            msg = Message(
                subject=f"Driver Fully Offboarded: {record.driver.full_name}",
                recipients=recipients,
                body=f"""
Dear HR / Admin Team,

Driver {record.driver.full_name} (Iqama: {record.driver.iqama_number}) has been fully offboarded by the Fleet Manager after TAMM revocation.

Offboarding completed at: {record.fleet_cleared_at.strftime('%Y-%m-%d %H:%M')}
TAMM Revoked at: {record.tamm_revoked_at.strftime('%Y-%m-%d %H:%M')}

Please update your records accordingly.

Regards,
Fleet Team
"""
            )
            mail.send(msg)

        return jsonify({
            "success": True,
            "message": f"Driver {record.driver.full_name} fully offboarded and email sent.",
            "tamm_revoked_at": record.tamm_revoked_at.strftime("%Y-%m-%d %H:%M")
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[TAMM REVOCATION ERROR] {e}")
        return jsonify({"success": False, "message": str(e)}), 500

