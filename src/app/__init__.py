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
    if not os.path.exists("in"):
        os.makedirs("in")
    if not os.path.exists("srv"):
        os.makedirs("srv")


class SchedulerConfig:
    SCHEDULER_API_ENABLED = True
    SCHEDULER_JOBSTORES = {
        "default": {
            "type": "sqlalchemy",
            "url": "sqlite:///src/instance/jobs.sqlite",
        }
    }
    SCHEDULER_EXECUTORS = {"default": {"type": "threadpool", "max_workers": 1}}
    SCHEDULER_JOB_DEFAULTS = {"coalesce": False, "max_instances": config.threads}

def create_app() -> Flask:
    app = Flask(__name__, static_folder="static")

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sqlite3.db?timeout=90"
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

    return app

db = SQLAlchemy()
# scheduler = APScheduler()
migrate = Migrate(directory="./src/migrations")

# setup_dirs()
print("Config:\n", json.dumps(config.redacted().model_dump(), indent=2))
