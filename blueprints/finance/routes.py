import os
import re
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import Driver, User
from extensions import db, mail
from flask_mail import Message
from models import Offboarding


finance_bp = Blueprint("finance", __name__)

# Configure upload folder & allowed file types
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def make_safe_filename(driver, filename):
    """Rename uploaded file as: fullName_iqama_transfer_payment_proof.ext"""
    ext = filename.rsplit(".", 1)[1].lower()
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", driver.full_name.strip())
    safe_iqama = re.sub(r"[^0-9]", "", driver.iqama_number or "")
    return f"{safe_name}_{safe_iqama}_transfer_payment_proof.{ext}"

# -------------------------
# Finance Dashboard
# -------------------------
from sqlalchemy import not_, exists

@finance_bp.route("/dashboard")
@login_required
def dashboard_finance():
    """Display pending and completed drivers for Finance stage."""
    if current_user.role != "FinanceManager":
        flash("Access denied. Finance Manager role required.", "danger")
        return redirect(url_for("auth.login"))

    # Pending drivers: onboarding stage = Finance
    pending_drivers = Driver.query.filter_by(onboarding_stage="Finance").all()

    # Completed drivers: onboarding_stage = Completed AND NOT in Offboarding
    completed_drivers = (
        Driver.query
        .filter(
            Driver.onboarding_stage == "Completed",
            ~exists().where(Offboarding.driver_id == Driver.id)
        )
        .all()
    )

    # Offboarding requests (pending in finance)
    offboarding_requests = (
        Offboarding.query
        .filter_by(status="Finance")
        .order_by(Offboarding.requested_at.desc())
        .all()
    )

    return render_template(
        "dashboard_finance.html",
        pending_drivers=pending_drivers,
        completed_drivers=completed_drivers,
        offboarding_requests=offboarding_requests,
        datetime=datetime
    )


# -------------------------
# Approve Driver & Mark as Completed
# -------------------------
@finance_bp.route("/approve_driver/<int:driver_id>", methods=["POST"])
@login_required
def approve_driver(driver_id):
    """Mark driver as financially cleared, with validation on fee payment date and secure file saving."""
    if current_user.role != "FinanceManager":
        flash("Access denied. Finance Manager role required.", "danger")
        return redirect(url_for("auth.login"))

    driver = Driver.query.get_or_404(driver_id)

    # ✅ Collect finance form fields
    driver.transfer_fee_paid = bool(request.form.get("transfer_fee_paid"))
    amount = request.form.get("transfer_fee_amount")
    driver.transfer_fee_amount = float(amount) if amount else None

    # Validate payment date
    paid_at_str = request.form.get("transfer_fee_paid_at")
    if paid_at_str:
        try:
            # detect datetime-local vs date-only
            paid_at = datetime.strptime(paid_at_str, "%Y-%m-%dT%H:%M")

            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            if "T" in paid_at_str:
                paid_at = datetime.strptime(paid_at_str, "%Y-%m-%dT%H:%M")
            else:
                paid_at = datetime.strptime(paid_at_str, "%Y-%m-%d")

            # ✅ Allow yesterday & today, block tomorrow+
            if paid_at.date() > date.today():
                flash("❌ Transfer fee payment date cannot be in the future.", "danger")
                return redirect(url_for("finance.dashboard_finance"))

            driver.transfer_fee_paid_at = paid_at

        except ValueError:
            flash("❌ Invalid date format for transfer fee payment.", "danger")
            return redirect(url_for("finance.dashboard_finance"))

    # ✅ Handle receipt upload securely
    file = request.files.get("transfer_fee_receipt")
    if file and file.filename:
        if not allowed_file(file.filename):
            flash("❌ Invalid file type. Allowed: JPG, JPEG, PNG, PDF.", "danger")
            return redirect(url_for("finance.dashboard_finance"))

        # Ensure upload folder exists
        upload_folder = current_app.config.get("UPLOAD_FOLDER")
        if not upload_folder:
            flash("❌ Upload folder not configured.", "danger")
            return redirect(url_for("finance.dashboard_finance"))

        os.makedirs(upload_folder, exist_ok=True)

        new_filename = make_safe_filename(driver, file.filename)
        filepath = os.path.join(upload_folder, secure_filename(new_filename))
        file.save(filepath)
        driver.transfer_fee_receipt = new_filename

    # ✅ Mark as finance approved
    driver.transfer_fee_paid = True
    driver.transfer_fee_paid_at = datetime.utcnow()
    driver.finance_approved_at = datetime.utcnow()
    driver.onboarding_stage = "HR Final"

    try:
        db.session.commit()

        # ✅ Send Notifications
        hr_users = User.query.filter_by(role="HR").all()
        ops_users = User.query.filter_by(role="OpsManager").all()
        fleet_users = User.query.filter_by(role="FleetManager").all()
        recipients = [u.email for u in (hr_users + ops_users + fleet_users) if u.email]

        if recipients:
            msg = Message(
                subject=f"Driver Onboarding Completed: {driver.full_name}",
                recipients=recipients,
                body=f"""
Hello Team,


Driver {driver.full_name} has been approved by Finance.
Please complete sponsorship transfer and finalize onboarding.
Summary:
- Transfer Fee: {"✅ Paid" if driver.transfer_fee_paid else "❌ Not Paid"}
- Amount: {driver.transfer_fee_amount or "N/A"}
- Paid At: {driver.transfer_fee_paid_at.strftime('%Y-%m-%d %H:%M') if driver.transfer_fee_paid_at else "N/A"}
- Vehicle: {driver.car_details or "N/A"}
- TAMM Authorized: {"✅ Yes" if driver.tamm_authorized else "❌ No"}
- Finance Cleared: {driver.finance_approved_at.strftime('%Y-%m-%d %H:%M')}

Regards,
Finance Department
"""
            )
            mail.send(msg)

        flash(f"✅ Driver {driver.full_name} has been financially cleared and marked as Completed.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error saving finance data: {str(e)}", "danger")

    return redirect(url_for("finance.dashboard_finance"))

# -------------------------
# Change Password
# -------------------------
@finance_bp.route("/change_password", methods=["POST"])
@login_required
def change_password():
    """Allow Finance Manager to change their own password."""
    from werkzeug.security import check_password_hash, generate_password_hash

    if current_user.role != "FinanceManager":
        flash("Access denied. Finance Manager role required.", "danger")
        return redirect(url_for("auth.login"))

    current_password = request.form["current_password"]
    new_password = request.form["new_password"]
    confirm_password = request.form["confirm_password"]

    if not check_password_hash(current_user.password, current_password):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for("finance.dashboard_finance"))

    if new_password != confirm_password:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("finance.dashboard_finance"))

    current_user.password = generate_password_hash(new_password)
    db.session.commit()

    flash("Password updated successfully.", "success")
    return redirect(url_for("finance.dashboard_finance"))

from flask import jsonify

@finance_bp.route("/offboarding/clear/<int:offboarding_id>", methods=["POST"])
@login_required
def clear_offboarding(offboarding_id):
    if current_user.role != "FinanceManager":
        return jsonify({"success": False, "message": "Access denied. Finance Manager role required."}), 403

    record = Offboarding.query.get_or_404(offboarding_id)

    try:
        # Collect inputs
        record.finance_cleared = True
        record.finance_cleared_at = datetime.utcnow()
        record.finance_adjustments = float(request.form.get("finance_adjustments") or 0)
        record.finance_note = request.form.get("finance_note", "").strip()

        # File upload (invoice)
        file = request.files.get("finance_invoice_file")
        if file and file.filename:
            if not allowed_file(file.filename):
                return jsonify({"success": False, "message": "Invalid file type. Allowed: JPG, JPEG, PNG, PDF."}), 400

            upload_folder = current_app.config.get("UPLOAD_FOLDER") or "static/uploads"
            os.makedirs(upload_folder, exist_ok=True)

            # Sanitize name
            base_name = re.sub(r"[^a-zA-Z0-9_-]", "_", record.driver.full_name.strip())
            iqama_clean = re.sub(r"[^0-9]", "", record.driver.iqama_number or "")
            ext = file.filename.rsplit(".", 1)[1].lower()
            safe_name = secure_filename(f"offboarding_{base_name}_{iqama_clean}_invoice.{ext}")

            file.save(os.path.join(upload_folder, safe_name))
            record.finance_invoice_file = safe_name

        # Move to HR stage
        record.status = "HR"

        db.session.commit()

        # Notify HR
        try:
            hr_users = User.query.filter_by(role="HR").all()
            emails = [u.email for u in hr_users if u.email]
            if emails:
                msg = Message(
                    subject=f"Driver Offboarding Ready for HR: {record.driver.full_name}",
                    recipients=emails,
                    body=f"""
Dear HR Team,

Driver {record.driver.full_name} (Iqama: {record.driver.iqama_number}) 
has been financially cleared by Finance.

Finance Notes: {record.finance_note or "N/A"}
Adjustments: {record.finance_adjustments or "None"}

Please proceed with final clearance.

Regards,
Finance Department
"""
                )
                mail.send(msg)
        except Exception as e:
            current_app.logger.warning(f"[FINANCE][EMAIL] Failed to notify HR: {e}")

        return jsonify({"success": True, "message": f"Driver {record.driver.full_name} offboarding cleared!"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[FINANCE][OFFBOARD ERROR] {e}")
        return jsonify({"success": False, "message": "Error processing offboarding clearance."}), 500
