from extensions import db
from flask_login import UserMixin
from datetime import datetime

class Driver(db.Model):
    __tablename__ = "driver"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    iqama_number = db.Column(db.String(20), unique=True, nullable=False)
    iqama_expiry_date = db.Column(db.Date, nullable=True)
    saudi_driving_license = db.Column(db.Boolean, default=False)
    nationality = db.Column(db.String(100), nullable=True)
    mobile_number = db.Column(db.String(15), nullable=True)
    previous_sponsor_number = db.Column(db.String(50), nullable=True)
    iqama_card_upload = db.Column(db.String(200), nullable=True)
    platform = db.Column(db.String(100), nullable=True)
    platform_id = db.Column(db.String(100), nullable=True)
    issued_mobile_number = db.Column(db.String(20), nullable=True)
    issued_device_id = db.Column(db.String(100), nullable=True)
    mobile_issued = db.Column(db.Boolean, default=False)
    city = db.Column(db.String(100), nullable=True)
    car_details = db.Column(db.String(200), nullable=True)
    assignment_date = db.Column(db.Date, nullable=True)
    onboarding_stage = db.Column(db.String(50), default="Ops Manager", nullable=False)
    ops_manager_approved = db.Column(db.Boolean, default=False)
    ops_manager_approved_at = db.Column(db.DateTime, nullable=True)
    qiwa_contract_created = db.Column(db.Boolean, default=False)
    company_contract_created = db.Column(db.Boolean, default=False)
    qiwa_contract_status = db.Column(db.String(20), default="Pending")
    sponsorship_transfer_status = db.Column(db.String(20), default="Pending")
    hr_approved_at = db.Column(db.DateTime, nullable=True)
    hr_approved_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    hr_approved_by_user = db.relationship("User", foreign_keys=[hr_approved_by])
    ops_supervisor_approved_at = db.Column(db.DateTime, nullable=True)
    fleet_manager_approved_at = db.Column(db.DateTime, nullable=True)
    finance_approved_at = db.Column(db.DateTime, nullable=True)
    tamm_authorized = db.Column(db.Boolean, default=False)
    tamm_authorization_ss = db.Column(db.String(200))
    transfer_fee_paid = db.Column(db.Boolean, default=False)
    transfer_fee_amount = db.Column(db.Float, nullable=True)
    transfer_fee_paid_at = db.Column(db.DateTime, nullable=True)
    transfer_fee_receipt = db.Column(db.String(200), nullable=True)
    sponsorship_transfer_proof = db.Column(db.String(200))  

    # ✅ Correct relationship
    offboarding_records = db.relationship("Offboarding", backref="driver", lazy=True)

    # Helper methods
    def mark_ops_manager_approved(self):
        self.ops_manager_approved = True
        self.ops_manager_approved_at = datetime.utcnow()
        self.onboarding_stage = "HR"

    def mark_hr_approved(self, user_id):
        self.hr_approved_at = datetime.utcnow()
        self.hr_approved_by = user_id
        self.onboarding_stage = "Ops Supervisor"

    def mark_ops_supervisor_approved(self):
        self.ops_supervisor_approved_at = datetime.utcnow()
        self.onboarding_stage = "Fleet Manager"

    def mark_fleet_manager_approved(self):
        self.fleet_manager_approved_at = datetime.utcnow()
        self.onboarding_stage = "Finance"

    def mark_finance_approved(self):
        self.finance_approved_at = datetime.utcnow()
        self.onboarding_stage = "Completed"

    def __repr__(self):
        return f"<Driver {self.full_name} - Stage: {self.onboarding_stage}>"



class User(db.Model, UserMixin):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # Hash stored
    role = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    designation = db.Column(db.String(100), nullable=True)
    branch_city = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Offboarding(db.Model):
    __tablename__ = "offboarding"

    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("driver.id"), nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(30), default="Requested")
    # Possible values: Requested, OpsSupervisor, Fleet, Finance, HR, Completed

    # Ops Supervisor section
    ops_supervisor_cleared = db.Column(db.Boolean, default=False)
    ops_supervisor_cleared_at = db.Column(db.DateTime)
    ops_supervisor_note = db.Column(db.Text)

    # Fleet section
    fleet_cleared = db.Column(db.Boolean, default=False)
    fleet_cleared_at = db.Column(db.DateTime)
    fleet_damage_report = db.Column(db.Text)
    fleet_damage_cost = db.Column(db.Float)

    # Finance section
    finance_cleared = db.Column(db.Boolean, default=False)
    finance_cleared_at = db.Column(db.DateTime)
    finance_invoice_file = db.Column(db.String(200))
    finance_adjustments = db.Column(db.Float)
    finance_note = db.Column(db.Text)

    # HR section
    hr_cleared = db.Column(db.Boolean, default=False)
    hr_cleared_at = db.Column(db.DateTime)
    hr_note = db.Column(db.Text)

    # TAMM revoke info
    tamm_revoked = db.Column(db.Boolean, default=False)
    tamm_revoked_at = db.Column(db.DateTime)

    company_contract_cancelled = db.Column(db.Boolean, default=False)
    qiwa_contract_cancelled = db.Column(db.Boolean, default=False)
    salary_paid = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    #offboarding_records = db.relationship('Offboarding', backref='driver', lazy=True)
    #offboarding_records = db.relationship('Offboarding', backref='driver', lazy=True)


    
    # Relationships
    #db.relationship("Driver", backref="offboarding_records")

    def mark_ops_supervisor_cleared(self, note=None):
        self.ops_supervisor_cleared = True
        self.ops_supervisor_cleared_at = datetime.utcnow()
        self.ops_supervisor_note = note
        self.status = "Fleet"

    def mark_fleet_cleared(self, report=None, cost=0):
        self.fleet_cleared = True
        self.fleet_cleared_at = datetime.utcnow()
        self.fleet_damage_report = report
        self.fleet_damage_cost = cost
        self.status = "Finance"

    def mark_finance_cleared(self, adjustments=0, note=None, invoice=None):
        self.finance_cleared = True
        self.finance_cleared_at = datetime.utcnow()
        self.finance_adjustments = adjustments
        self.finance_note = note
        self.finance_invoice_file = invoice
        self.status = "HR"

    def mark_hr_cleared(self, note=None):
        self.hr_cleared = True
        self.hr_cleared_at = datetime.utcnow()
        self.hr_note = note
        self.status = "Completed"

        # driver.py

