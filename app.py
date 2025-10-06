from flask import Flask
from config import Config
from extensions import db, mail, login_manager

# ✅ Import all blueprints
from blueprints.public.routes import public_bp      # <-- ADDED
from blueprints.auth.routes import auth_bp
from blueprints.admin.routes import admin_bp
from blueprints.hr.routes import hr_bp
from blueprints.ops_manager.routes import ops_manager_bp
from blueprints.ops_supervisor.routes import ops_supervisor_bp
from blueprints.fleet.routes import fleet_bp
from blueprints.finance.routes import finance_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)

    # ✅ Register blueprints
    app.register_blueprint(public_bp)  # <-- ADDED (handles / and /register)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/dashboard")
    app.register_blueprint(hr_bp, url_prefix="/dashboard/hr")
    app.register_blueprint(ops_manager_bp, url_prefix="/dashboard/ops")
    app.register_blueprint(ops_supervisor_bp, url_prefix="/dashboard/ops_supervisor")
    app.register_blueprint(fleet_bp, url_prefix="/dashboard/fleet")
    app.register_blueprint(finance_bp, url_prefix="/dashboard/finance")

    with app.app_context():
        db.create_all()

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
