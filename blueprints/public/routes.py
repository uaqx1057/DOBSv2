import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from models import Driver
from datetime import datetime
from flask_mail import Message
from extensions import mail

public_bp = Blueprint("public", __name__)

@public_bp.route("/")
def index():
    return render_template("index.html")

@public_bp.route("/register", methods=["POST"])
def register():
    full_name = request.form["full_name"]
    iqama_number = request.form["iqama_number"]
    iqama_expiry_date = request.form["iqama_expiry_date"]
    saudi_driving_license = request.form["saudi_driving_license"] == "yes"
    nationality = request.form["nationality"]
    city = request.form.get("city")
    mobile_number = request.form["mobile_number"]
    previous_sponsor_number = request.form["previous_sponsor_number"]
    iqama_card_upload = request.files["iqama_card_upload"]

    upload_folder = "static/uploads/"
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    safe_name = full_name.replace(" ", "_").lower()
    safe_iqama = iqama_number.replace(" ", "_")
    extension = os.path.splitext(iqama_card_upload.filename)[1]
    file_name = f"{safe_name}_{safe_iqama}{extension}"
    file_path = os.path.join(upload_folder, file_name)
    iqama_card_upload.save(file_path)

    new_driver = Driver(
        full_name=full_name,
        iqama_number=iqama_number,
        iqama_expiry_date=iqama_expiry_date,
        saudi_driving_license=saudi_driving_license,
        nationality=nationality,
        city=city,
        mobile_number=mobile_number,
        previous_sponsor_number=previous_sponsor_number,
        iqama_card_upload=file_name,
        platform="Unknown",
        onboarding_stage="Ops Manager"

    )

    db.session.add(new_driver)
    db.session.commit()

    try:
        msg = Message(
            "New Driver Registration Submitted",
            recipients=["uaqx1057@gmail.com"],
            body=f"Driver {full_name} has submitted a new registration form. Please review the details."
        )
        mail.send(msg)
    except Exception as e:
        print(f"Error sending email: {e}")

    flash("✅ Driver data received successfully!", "success")
    return redirect(url_for("public.index"))
