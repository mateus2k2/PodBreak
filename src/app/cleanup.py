import logging
import threading
from datetime import datetime, timedelta

from sqlalchemy.orm import sessionmaker

logger = logging.getLogger("global_logger")


def delete_failed_posts(session, older_than_hours: int) -> int:
    from app.models import Identification, ModelCall, Post, Task, TranscriptSegment

    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)

    failed_tasks = (
        session.query(Task)
        .filter(Task.status == "failed", Task.updated_at <= cutoff)
        .all()
    )

    post_ids_with_failed = {t.post_id for t in failed_tasks if t.post_id is not None}

    non_failed = (
        session.query(Task.post_id)
        .filter(Task.post_id.in_(post_ids_with_failed), Task.status != "failed")
        .distinct()
        .all()
    )
    post_ids_to_skip = {row.post_id for row in non_failed}

    post_ids = post_ids_with_failed - post_ids_to_skip
    if not post_ids:
        return 0

    segment_ids = [
        row.id
        for row in session.query(TranscriptSegment.id)
        .filter(TranscriptSegment.post_id.in_(post_ids))
        .all()
    ]
    model_call_ids = [
        row.id
        for row in session.query(ModelCall.id)
        .filter(ModelCall.post_id.in_(post_ids))
        .all()
    ]

    if segment_ids or model_call_ids:
        session.query(Identification).filter(
            Identification.transcript_segment_id.in_(segment_ids)
            | Identification.model_call_id.in_(model_call_ids)
        ).delete(synchronize_session=False)

    if segment_ids:
        session.query(TranscriptSegment).filter(
            TranscriptSegment.id.in_(segment_ids)
        ).delete(synchronize_session=False)

    if model_call_ids:
        session.query(ModelCall).filter(
            ModelCall.id.in_(model_call_ids)
        ).delete(synchronize_session=False)

    session.query(Task).filter(Task.post_id.in_(post_ids)).delete(
        synchronize_session=False
    )
    session.query(Post).filter(Post.id.in_(post_ids)).delete(
        synchronize_session=False
    )

    session.commit()
    logger.info(f"Cleanup deleted {len(post_ids)} failed post(s) older than {older_than_hours}h.")
    return len(post_ids)


def start_cleanup_scheduler(app, db, interval_hours: int, older_than_hours: int) -> None:
    def run():
        with app.app_context():
            Session = sessionmaker(bind=db.get_engine())
            session = Session()
            try:
                delete_failed_posts(session, older_than_hours)
            except Exception as e:
                logger.error(f"Cleanup job failed: {e}", exc_info=True)
            finally:
                session.close()

        t = threading.Timer(interval_hours * 3600, run)
        t.daemon = True
        t.start()

    t = threading.Timer(interval_hours * 3600, run)
    t.daemon = True
    t.start()
    logger.info(f"Cleanup scheduler started: runs every {interval_hours}h, deletes failed posts older than {older_than_hours}h.")
