import os
import sys

# Add the project root to Python's import path
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)


from sqlalchemy import text

from app import create_app
from app.extensions import db


app = create_app()

with app.app_context():

    columns = {
        "anomalies_detected": "INTEGER DEFAULT 0",
        "alerts_created": "INTEGER DEFAULT 0",
        "alerts_skipped": "INTEGER DEFAULT 0",
        "sms_sent": "INTEGER DEFAULT 0",
    }

    existing_columns = {
        row[1]
        for row in db.session.execute(
            text("PRAGMA table_info(pipeline_runs)")
        )
    }

    for column_name, column_definition in columns.items():

        if column_name not in existing_columns:

            db.session.execute(
                text(
                    f"ALTER TABLE pipeline_runs "
                    f"ADD COLUMN {column_name} "
                    f"{column_definition}"
                )
            )

            print(f"Added: {column_name}")

        else:
            print(f"Already exists: {column_name}")

    db.session.commit()

    print("Pipeline run metrics migration complete.")