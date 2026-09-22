import os
from dotenv import load_dotenv
from flask import Flask

load_dotenv()

from config import config_by_name
from app.extensions import db, login_manager, csrf


def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True)

    config_name = config_name or os.environ.get("FLASK_ENV", "production")
    app.config.from_object(config_by_name[config_name])

    csrf.init_app(app)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from app.auth.routes import auth_bp
    from app.dashboard.routes import dashboard_bp
    from app.surveillance.routes import surveillance_bp
    from app.pipeline.routes import pipeline_bp
    from app.alerts.routes import alerts_bp
    from app.data_management.routes import data_management_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(surveillance_bp)
    app.register_blueprint(pipeline_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(data_management_bp)

    with app.app_context():
        from app import models  # noqa: F401
        db.create_all()

    return app