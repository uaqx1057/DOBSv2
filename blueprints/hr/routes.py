# blueprints/hr/routes.py
from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from blueprints import hr
from models import Driver, User
from extensions import db, mail
from flask_mail import Message
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from models import Offboarding

hr_bp = Blueprint("hr", __name__, url_prefix='/hr')

UPLOAD_FOLDER = os.path.join(os.getcwd(), "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.pdf'}

def _allowed_filename(fn):
    _, ext = os.path.splitext(fn.lower())
    return ext in ALLOWED_EXT

def _serialize_driver(d):
    """Serialize driver to a JSON-friendly dict for dashboard_hr.html."""
    return {
        "id": d.id,
        "full_name": d.full_name,
        "iqama_number": d.iqama_number,
        "iqama_expiry_date": d.iqama_expiry_date.isoformat() if d.iqama_expiry_date else None,
        "nationality": d.nationality,
        "mobile_number": d.mobile_number,
        "previous_sponsor_number": d.previous_sponsor_number,
        "saudi_driving_license": bool(d.saudi_driving_license),
        "city": d.city,
        "platform": d.platform,
        "platform_id": d.platform_id,  # ✅ add this
        "car_details": d.car_details,  # ✅ add this
        "assignment_date": d.assignment_date.isoformat() if d.assignment_date else None,  # ✅ add this
        "issued_mobile_number": d.issued_mobile_number,  # ✅ add this
        "issued_device_id": d.issued_device_id,  # ✅ add this
        "mobile_issued": bool(d.mobile_issued),  # ✅ add this
        "iqama_card_upload": d.iqama_card_upload,
        "qiwa_contract_created": bool(d.qiwa_contract_created),
        "company_contract_created": bool(d.company_contract_created),
        "qiwa_contract_status": d.qiwa_contract_status,
        "ops_manager_approved_at": d.ops_manager_approved_at.isoformat() if d.ops_manager_approved_at else None,
        "ops_supervisor_approved_at": d.ops_supervisor_approved_at.isoformat() if d.ops_supervisor_approved_at else None,
        "fleet_manager_approved_at": d.fleet_manager_approved_at.isoformat() if d.fleet_manager_approved_at else None,
        "finance_approved_at": d.finance_approved_at.isoformat() if d.finance_approved_at else None,
        "hr_approved_at": d.hr_approved_at.isoformat() if d.hr_approved_at else None,
        "transfer_fee_paid": bool(d.transfer_fee_paid),  # ✅ add this
        "transfer_fee_amount": float(d.transfer_fee_amount) if d.transfer_fee_amount else None,  # ✅ add this
        "transfer_fee_paid_at": d.transfer_fee_paid_at.isoformat() if d.transfer_fee_paid_at else None,  # ✅ add this
        "transfer_fee_receipt": d.transfer_fee_receipt,  # ✅ add this
        "sponsorship_transfer_proof": d.sponsorship_transfer_proof,
        "tamm_authorization_ss": d.tamm_authorization_ss,  # ✅ add this
        "tamm_authorized": bool(d.tamm_authorized),  # ✅ add this
        "sponsorship_transfer_status": d.sponsorship_transfer_status,
        "onboarding_stage": d.onboarding_stage,
    }
def _serialize_offboarding(o):
    return {
        "offboarding_id": o.id,
        "driver_id": o.driver.id if o.driver else None,
        "full_name": o.driver.full_name if o.driver else "",
        "iqama_number": o.driver.iqama_number if o.driver else "",
        "status": o.status or "",
        "hr_note": o.hr_note or "",
        "tamm_revoked": bool(o.tamm_revoked),
        "company_contract_cancelled": bool(o.company_contract_cancelled),
        "qiwa_contract_cancelled": bool(o.qiwa_contract_cancelled),
        "pending_salary": float(getattr(o, "finance_adjustments", 0) or 0),
        "finance_note": getattr(o, "finance_note", "") or "",
        "fleet_damage_report": getattr(o, "fleet_damage_report", "") or "",
        "fleet_damage_cost": float(getattr(o, "fleet_damage_cost", 0) or 0),
        "salary_paid": bool(o.salary_paid),
    }

# -------------------------
# HR Dashboard (Handles HR + HR Final + Completed)
# -------------------------
@hr_bp.route("/dashboard")
@login_required
def dashboard_hr():
    if current_user.role != "HR":
        flash("Access denied. HR role required.", "danger")
        return redirect(url_for("auth.login"))

    # --------------------------
    # Get all drivers in HR/HR Final/Completed
    # --------------------------
    all_drivers = Driver.query.filter(
        Driver.onboarding_stage.in_(["HR", "HR Final", "Completed"])
    ).all()

    # --------------------------
    # Get all drivers currently in offboarding
    # --------------------------
    offboarding_driver_ids = {o.driver_id for o in Offboarding.query.filter(
        Offboarding.status.in_(["HR", "Completed"])
    ).all()}

    # --------------------------
    # Filter out drivers who are in offboarding
    # --------------------------
    drivers_data = [_serialize_driver(d) for d in all_drivers if d.id not in offboarding_driver_ids]

    # --------------------------
    # Keep your offboarding data as-is
    # --------------------------
    offboardings = Offboarding.query.filter(Offboarding.status.in_(["HR", "Completed"])).all()
    offboarding_data = []
    for o in offboardings:
        d = o.driver
        offboarding_data.append({
            "offboarding_id": o.id,
            "driver_id": d.id,
            "full_name": d.full_name or "",
            "iqama_number": d.iqama_number or "",
            "status": o.status or "",
            "hr_note": o.hr_note or "",
            "tamm_revoked": bool(o.tamm_revoked),
            "company_contract_cancelled": getattr(o, "company_contract_cancelled", False),
            "qiwa_contract_cancelled": getattr(o, "qiwa_contract_cancelled", False),
            "pending_salary": float(getattr(o, "finance_adjustments", 0) or 0),
            "finance_note": getattr(o, "finance_note", "") or "",
            "fleet_damage_report": getattr(o, "fleet_damage_report", "") or "",
            "fleet_damage_cost": float(getattr(o, "fleet_damage_cost", 0) or 0),
            "salary_paid": getattr(o, "salary_paid", False),
        })

    return render_template(
        "dashboard_hr.html",
        drivers=drivers_data,
        offboarding_drivers=offboarding_data
    )

# -------------------------
# Approve Driver & Send to Ops Supervisor (HR normal flow)
# -------------------------
@hr_bp.route("/approve_driver/<int:driver_id>", methods=["POST"])
@login_required
def approve_driver(driver_id):
    if current_user.role != "HR":
        flash("Access denied. HR role required.", "danger")
        return redirect(url_for("auth.login"))

    driver = Driver.query.get_or_404(driver_id)

    # Save form fields
    driver.qiwa_contract_created = bool(request.form.get("qiwa_contract_created"))
    driver.company_contract_created = bool(request.form.get("company_contract_created"))
    driver.qiwa_contract_status = request.form.get("qiwa_contract_status", "Pending")
    driver.sponsorship_transfer_status = request.form.get("sponsorship_transfer_status", "Pending")

    # Server-side validation
    if not driver.company_contract_created:
        flash("Company contract must be created before approval.", "danger")
        return redirect(url_for("hr.dashboard_hr"))

    if not driver.qiwa_contract_created:
        flash("Qiwa contract must be created before approval.", "danger")
        return redirect(url_for("hr.dashboard_hr"))

    if driver.qiwa_contract_status != "Approved":
        flash("Qiwa contract status must be 'Approved' before approval.", "danger")
        return redirect(url_for("hr.dashboard_hr"))

    driver.hr_approved_at = datetime.utcnow()
    driver.onboarding_stage = "Ops Supervisor"

    db.session.commit()

    # Notify Ops Supervisor(s)
    try:
        ops_supervisors = User.query.filter_by(role="OpsSupervisor").all()
        recipients = [op.email for op in ops_supervisors if op.email]
        if recipients:
            msg = Message(
                subject=f"Driver Ready for Ops Supervisor Stage: {driver.full_name}",
                recipients=recipients,
                body=f"Driver {driver.full_name} moved to Ops Supervisor stage. Iqama: {driver.iqama_number or 'N/A'}"
            )
            mail.send(msg)
    except Exception as e:
        print("[EMAIL ERROR]", e)

    flash(f"Driver {driver.full_name} approved and sent to Ops Supervisor stage.", "success")
    return redirect(url_for("hr.dashboard_hr"))


# -------------------------
# HR Final Stage: Complete Sponsorship Transfer
# -------------------------
@hr_bp.route("/complete_transfer/<int:driver_id>", methods=["POST"])
@login_required
def complete_sponsorship_transfer(driver_id):
    if current_user.role != "HR":
        flash("Access denied", "danger")
        return redirect(url_for("auth.login"))

    driver = Driver.query.get_or_404(driver_id)

    # handle file upload (optional)
    file = request.files.get("sponsorship_transfer_proof")
    if file and file.filename and _allowed_filename(file.filename):
        safe_name = secure_filename(file.filename)
        ext = os.path.splitext(safe_name)[1]  # keep original extension (.jpg, .png, etc.)

        # ✅ Custom file naming: full_name + iqama + transfer_proof
        driver_name = driver.full_name.replace(" ", "_") if driver.full_name else "driver"
        iqama = driver.iqama_number or "unknown"
        filename = f"{driver_name}_{iqama}_transfer_proof{ext}"

        dest = os.path.join(UPLOAD_FOLDER, filename)
        file.save(dest)

        # assign to the correct column
        if hasattr(driver, "sponsorship_transfer_proof"):
            driver.sponsorship_transfer_proof = filename
        else:
            driver.transfer_fee_receipt = filename  # fallback

    # update statuses and finish
    driver.sponsorship_transfer_status = "Completed"
    driver.sponsorship_transfer_completed_at = datetime.utcnow()
    driver.onboarding_stage = "Completed"

    db.session.commit()

    # notify superadmins
    try:
        superadmins = User.query.filter_by(role="SuperAdmin").all()
        recipients = [sa.email for sa in superadmins if sa.email]
        if recipients:
            msg = Message(
                subject=f"Driver Onboarding Completed: {driver.full_name}",
                recipients=recipients,
                body=f"Driver {driver.full_name} completed sponsorship transfer. Iqama: {driver.iqama_number or 'N/A'}"
            )
            mail.send(msg)
    except Exception as e:
        print("[EMAIL ERROR]", e)

    flash(f"Sponsorship transfer completed for {driver.full_name}.", "success")
    return redirect(url_for("hr.dashboard_hr"))


# -------------------------
# Change HR Password
# -------------------------
@hr_bp.route("/change_password", methods=["POST"])
@login_required
def change_password():
    if current_user.role != "HR":
        flash("Access denied. HR role required.", "danger")
        return redirect(url_for("auth.login"))

    current_password = request.form["current_password"]
    new_password = request.form["new_password"]
    confirm_password = request.form["confirm_password"]

    if not check_password_hash(current_user.password, current_password):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for("hr.dashboard_hr"))

    if new_password != confirm_password:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("hr.dashboard_hr"))

    current_user.password = generate_password_hash(new_password)
    db.session.commit()

    flash("Password updated successfully.", "success")
    return redirect(url_for("hr.dashboard_hr"))


# -------------------------
# Start Offboarding (contract cancellation)
# -------------------------
@hr_bp.route("/start_offboarding/<int:driver_id>", methods=["POST"])
@login_required
def start_offboarding(driver_id):
    if current_user.role != "HR":
        flash("Access denied", "danger")
        return redirect(url_for("auth.login"))

    driver = Driver.query.get_or_404(driver_id)
    driver.offboarding_stage = "HR"
    driver.offboarding_reason = request.form.get("offboarding_reason", "Not specified")
    driver.offboarding_requested_at = datetime.utcnow()

    db.session.commit()
    flash(f"Offboarding process started for {driver.full_name}.", "info")
    return redirect(url_for("hr.offboarding_hr"))


# -------------------------
# Complete Offboarding
# -------------------------

@hr_bp.route("/complete_offboarding/<int:offboarding_id>", methods=["POST"])
@login_required
def complete_offboarding(offboarding_id):
    if current_user.role != "HR":
        flash("Access denied", "danger")
        return redirect(url_for("auth.login"))

    offboarding = Offboarding.query.get_or_404(offboarding_id)
    note = request.form.get("hr_note")
    offboarding.mark_hr_cleared(note=note)

    db.session.commit()
    flash(f"HR clearance completed for {offboarding.driver.full_name}.", "success")
    return redirect(url_for("hr.dashboard_hr"))


@hr_bp.route("/offboarding/finalize", methods=["POST"])
@login_required
def finalize_offboarding():
    if current_user.role != "HR":
        if request.is_json:
            return jsonify({"success": False, "message": "Access denied"}), 403
        flash("Access denied", "danger")
        return redirect(url_for("auth.login"))

    # Determine if request is JSON or form
    if request.is_json:
        data = request.get_json()
        offboarding_id = data.get("offboarding_id")
        company_cancelled = data.get("company_contract_cancelled") == "yes"
        qiwa_cancelled = data.get("qiwa_contract_cancelled") == "yes"
        salary_paid = data.get("salary_paid") == "yes"
    else:
        offboarding_id = request.form.get("offboarding_id")
        company_cancelled = request.form.get("company_contract_cancelled") == "yes"
        qiwa_cancelled = request.form.get("qiwa_contract_cancelled") == "yes"
        salary_paid = request.form.get("salary_paid") == "yes"

    # Fetch Offboarding record
    offboarding = Offboarding.query.get_or_404(offboarding_id)

    # Update fields
    offboarding.company_contract_cancelled = company_cancelled
    offboarding.qiwa_contract_cancelled = qiwa_cancelled
    offboarding.salary_paid = salary_paid

    # Constraint check
    if not (company_cancelled and qiwa_cancelled and salary_paid):
        message = "Cannot clear: Company & Qiwa contracts must be cancelled and salary must be paid."
        if request.is_json:
            return jsonify({"success": False, "message": message}), 400
        flash(message, "danger")
        return redirect(url_for("hr.dashboard_hr"))

    # Mark HR cleared
    offboarding.hr_cleared = True
    offboarding.hr_cleared_at = datetime.utcnow()
    offboarding.status = "pending_tamm"

    db.session.commit()

    # Send email to Fleet Manager(s)
    try:
        fleet_managers = User.query.filter_by(role="FleetManager").all()
        recipients = [fm.email for fm in fleet_managers if fm.email]
        if recipients:
            msg = Message(
                subject=f"Offboarding Ready for TAMM: {offboarding.driver.full_name}",
                recipients=recipients,
                body=f"HR has cleared the offboarding for driver {offboarding.driver.full_name} "
                     f"(Iqama: {offboarding.driver.iqama_number or 'N/A'}). The record is ready for TAMM cancelation."
            )
            mail.send(msg)
    except Exception as e:
        print("[EMAIL ERROR to FleetManager]", e)
        if request.is_json:
            return jsonify({"success": False, "message": f"Email send failed: {str(e)}"}), 500
        flash(f"Email send failed: {str(e)}", "danger")
        return redirect(url_for("hr.dashboard_hr"))

    success_message = f"HR clearance completed for {offboarding.driver.full_name} and Fleet Manager notified."
    if request.is_json:
        return jsonify({"success": True, "message": success_message})
    flash(success_message, "success")
    return redirect(url_for("hr.dashboard_hr"))
