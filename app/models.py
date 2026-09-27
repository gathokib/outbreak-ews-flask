from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="analyst")  # analyst | admin
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    pipeline_runs = db.relationship(
        "PipelineRun", backref="triggered_by", lazy="dynamic", cascade="all, delete-orphan"
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def __repr__(self):
        return f"<User {self.username}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class PipelineRun(db.Model):
    __tablename__ = "pipeline_runs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    country = db.Column(db.String(80), nullable=False, index=True)
    detection_method = db.Column(db.String(20), nullable=False)  # c1 | isolation_forest
    status = db.Column(db.String(20), nullable=False, default="queued")  # queued|running|completed|failed
    started_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    rows_processed = db.Column(db.Integer, nullable=True)
    anomalies_detected = db.Column(db.Integer, default=0)
    alerts_created = db.Column(db.Integer, default=0)
    alerts_skipped = db.Column(db.Integer, default=0)
    sms_sent = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)

    alerts = db.relationship(
        "Alert", backref="pipeline_run", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<PipelineRun {self.id} {self.country} {self.status}>"


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)

    pipeline_run_id = db.Column(
        db.Integer,
        db.ForeignKey("pipeline_runs.id"),
        nullable=False,
    )

    country = db.Column(
        db.String(80),
        nullable=False,
        index=True,
    )

    alert_date = db.Column(
        db.Date,
        nullable=False,
    )

    metric_value = db.Column(
        db.Float,
        nullable=False,
    )

    threshold_value = db.Column(
        db.Float,
        nullable=False,
    )

    detection_method = db.Column(
        db.String(30),
        nullable=False,
        default="c1",
    )

    reason = db.Column(
        db.Text,
        nullable=True,
    )

    severity = db.Column(
        db.String(20),
        nullable=False,
        default="medium",
    )

    sms_sent = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        default=utcnow,
        nullable=False,
    )

    def __repr__(self):
        return f"<Alert {self.id} {self.country} {self.severity}>"
    
class Country(db.Model):
    __tablename__ = "countries"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
        index=True
    )

    latitude = db.Column(
        db.Float,
        nullable=True
    )

    longitude = db.Column(
        db.Float,
        nullable=True
    )

    current_risk_level = db.Column(
        db.String(20),
        nullable=False,
        default="normal"
    )

    last_alert_id = db.Column(
        db.Integer,
        db.ForeignKey("alerts.id"),
        nullable=True
    )

    last_updated = db.Column(
        db.DateTime,
        default=utcnow,
        nullable=False
    )

    last_alert = db.relationship(
        "Alert",
        foreign_keys=[last_alert_id]
    )

class Observation(db.Model):
    __tablename__ = "observations"

    id = db.Column(db.Integer, primary_key=True)

    disease = db.Column(
        db.String(100),
        nullable=False,
        default="COVID-19",
        index=True,
    )

    country = db.Column(
        db.String(80),
        nullable=False,
        index=True,
    )

    location = db.Column(
        db.String(120),
        nullable=True,
        index=True,
    )

    observation_date = db.Column(
        db.Date,
        nullable=False,
        index=True,
    )

    cases = db.Column(
        db.Float,
        nullable=False,
    )

    deaths = db.Column(
        db.Float,
        nullable=True,
        default=0,
    )

    latitude = db.Column(
        db.Float,
        nullable=True,
    )

    longitude = db.Column(
        db.Float,
        nullable=True,
    )

    source = db.Column(
        db.String(255),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=utcnow,
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "disease",
            "country",
            "location",
            "observation_date",
            "source",
            name="uq_observation_record",
        ),
    )

    def __repr__(self):
        return (
            f"<Observation {self.country} "
            f"{self.observation_date} "
            f"{self.cases}>"
        )