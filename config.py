import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base config. Values are read from environment variables so nothing
    sensitive is hard-coded — set these in a .env file (see .env.example)
    or as real environment variables when you deploy to Azure."""

    SECRET_KEY = os.environ.get("SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "outbreak_ews.db").replace("\\", "/")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Africa's Talking credentials — used by app/pipeline/sms.py
    AT_USERNAME = os.environ.get("AT_USERNAME", "sandbox")
    AT_API_KEY = os.environ.get("AT_API_KEY", "")
    ALERT_RECIPIENT = os.environ.get("ALERT_RECIPIENT", "")

    # Detection thresholds, kept here (not hard-coded in detection logic)
    # so you can tune sensitivity without touching the algorithms themselves.
    C1_ALERT_THRESHOLD = float(os.environ.get("C1_ALERT_THRESHOLD", 2.0))
    ISOFOREST_CONTAMINATION = float(os.environ.get("ISOFOREST_CONTAMINATION", 0.05))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}