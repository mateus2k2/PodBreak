import logging
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, current_app, Flask
from app.models import Post, Task, Identification, TranscriptSegment
from app import db
from datetime import datetime
from app.processor import get_processor
import uuid
from typing import cast
from sqlalchemy.orm import sessionmaker

main_bp = Blueprint("main", __name__)

executor = ThreadPoolExecutor(max_workers=1)

def process_post_async(post: Post, task: Task, app: Flask) -> None:
    with app.app_context():
        engine = db.get_engine()
        Session = sessionmaker(bind=engine)
        thread_session = Session()

        try:
            post_in_thread = thread_session.merge(post)
            task_in_thread = thread_session.merge(task)

            get_processor().process(post_in_thread, task_in_thread, blocking=True)

            task_in_thread.status = "completed"
            task_in_thread.updated_at = datetime.utcnow()
            thread_session.commit()
        except Exception as e:
            task_in_thread.status = "failed"
            task_in_thread.updated_at = datetime.utcnow()
            thread_session.commit()
            logging.error(f"Processing failed: {e}")
        finally:
            thread_session.close()


# route to register a post and process it
@main_bp.route("/process", methods=["POST"])
def process():
    database_session = db.session
    request_data = request.get_json()

    title = request_data["title"]
    guid = request_data["guid"]
    description = request_data.get("description", "")

    # Check if already processed
    existing_post = (
        database_session.query(Post)
        .filter(Post.guid == guid)
        .first()
    )
    if existing_post:
        existing_task = (
            database_session.query(Task)
            .filter(Task.post_id == existing_post.id)
            .order_by(Task.id.desc())
            .first()
        )

        task_status = existing_task.status if existing_task else None

        if task_status in ("completed", "pending"):
            logging.info(f"Post '{title}' - {guid} has task with status '{task_status}', skipping.")
            return {
                "post_id": existing_post.id,
                "task_id": existing_task.id,
                "already_processed": True,
                "task_status": task_status,
            }

        logging.info(f"Post '{title}' - {guid} has task with status '{task_status}', retrying.")
        task = Task(
            status="pending",
            post_id=existing_post.id,
        )
        database_session.add(task)
        database_session.commit()

        app = cast(Flask, current_app._get_current_object())
        executor.submit(process_post_async, existing_post, task, app)

        return {
            "post_id": existing_post.id,
            "task_id": task.id,
            "already_processed": False,
            "task_status": "pending",
        }

    post = Post(
        guid=guid,
        title=title,
        description=description,
        unprocessed_audio_path=request_data["file_path"],
        language=request_data["language"],
    )
    database_session.add(post)
    database_session.flush()  # get post.id before creating task

    task = Task(
        status="pending",
        post_id=post.id,
    )
    database_session.add(task)
    database_session.commit()

    app = cast(Flask, current_app._get_current_object())
    executor.submit(process_post_async, post, task, app)

    return {
        "post_id": post.id,
        "task_id": task.id,
        "already_processed": False,
    }

@main_bp.route("/identifications/<int:post_id>", methods=["GET"])
def identifications(post_id: str):
    identifications = TranscriptSegment.query.join(Identification).filter(TranscriptSegment.post_id == post_id).all()
    result = []
    for segment in identifications:
        segment_dict = {
            "id": segment.id,
            "post_id": segment.post_id,
            "sequence_num": segment.sequence_num,
            "start_time": segment.start_time,
            "end_time": segment.end_time,
            "text": segment.text,
            "identifications": [
                {
                    "id": ident.id,
                    "model_call_id": ident.model_call_id,
                    "label": ident.label,
                    "confidence": ident.confidence,
                }
                for ident in segment.identifications
            ],
        }
        result.append(segment_dict)

    return {
        "identifications": result
    }


@main_bp.route("/task/<int:task_id>", methods=["GET"])
def get_task(task_id: int):
    task = Task.query.get(task_id)
    if not task:
        return {"error": "Task not found"}, 404
    return {
        "task_id": task.id,
        "post_id": task.post_id,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }