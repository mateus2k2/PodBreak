import json
import logging
import os
import sys

os.environ["LITELLM_DEBUG"] = "False"

from flask import Flask
from flask_migrate import Migrate, upgrade
from flask_sqlalchemy import SQLAlchemy

from app.logger import setup_logger
from shared.config import get_config

setup_logger("global_logger", "config/app.log")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("podcast_processor")
config = get_config("./config/config.yml")

for _noisy in ("litellm", "LiteLLM", "matplotlib", "torio", "urllib3",
               "httpcore", "filelock", "fsspec", "lightning",
               "lightning.pytorch", "pyannote"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

def setup_dirs() -> None:
    for d in ("in", "srv", "data/instance"):
        if not os.path.exists(d):
            os.makedirs(d)


class SchedulerConfig:
    SCHEDULER_API_ENABLED = True
    SCHEDULER_JOBSTORES = {
        "default": {
            "type": "sqlalchemy",
            "url": "sqlite:///data/db/jobs.sqlite",
        }
    }
    SCHEDULER_EXECUTORS = {"default": {"type": "threadpool", "max_workers": 1}}
    SCHEDULER_JOB_DEFAULTS = {"coalesce": False, "max_instances": config.threads}

def create_app() -> Flask:
    app = Flask(__name__, static_folder="static")

    app.config["SQLALCHEMY_DATABASE_URI"] = config.database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    groq_logger = logging.getLogger("groq")
    groq_logger.setLevel(logging.INFO)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.routes import main_bp  # pylint: disable=import-outside-toplevel
    app.register_blueprint(main_bp)

    from app import models  # pylint: disable=import-outside-toplevel, unused-import
    with app.app_context():
        upgrade()

    if config.failed_cleanup_after_hours is not None:
        from app.cleanup import start_cleanup_scheduler  # pylint: disable=import-outside-toplevel
        start_cleanup_scheduler(
            app=app,
            db=db,
            interval_hours=config.failed_cleanup_after_hours,
            older_than_hours=config.failed_cleanup_after_hours,
        )

    return app

db = SQLAlchemy()
# scheduler = APScheduler()
migrate = Migrate(directory="./src/migrations")

print("Config:\n", json.dumps(config.redacted().model_dump(), indent=2))
