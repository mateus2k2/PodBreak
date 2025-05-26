import logging
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, current_app, Flask
from app.models import Post, Task, Identification, TranscriptSegment
from app import db
from datetime import date
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

            # You can update task status here, for example:
            task_in_thread.status = "completed"
            thread_session.commit()
        except Exception as e:
            task_in_thread.status = "failed"
            thread_session.commit()
            # Log error here if you want
        finally:
            thread_session.close()


# route to register a post and process it
@main_bp.route("/process", methods=["POST"])
def process():
    database_session = db.session   
    request_data = request.get_json()
    
    # TODO: Check if the post is already processed in the database
    existing_post = (
        database_session.query(Post)
        .filter(Post.title == post.title and Post.rss_feed_url == post.rss_feed_url)
        .first()
    )
    if existing_post:
        logging.info(f"Post '{post.title}' already processed.")
        return []

    # process the new post
    post = Post(
        guid=str(uuid.uuid4()),
        title=request_data["title"],
        unprocessed_audio_path=request_data["file_path"],
        description=request_data["description"],
        language=request_data["language"],
        rss_feed_url=request_data["rss_feed_url"],
    )
    database_session.add(post)
    task = Task(
        status="pending",
    )
    database_session.add(task)
    database_session.commit()

    app = cast(Flask, current_app._get_current_object())
    executor.submit(process_post_async, post, task, app)

    return {
        "post_id": post.id,
        "task_id": task.id,
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