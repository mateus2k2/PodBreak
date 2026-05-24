import os
from datetime import datetime

from app import db


class Post(db.Model):  # type: ignore[name-defined, misc]
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    guid = db.Column(db.Text, unique=True, nullable=False)
    title = db.Column(db.Text, nullable=False)
    unprocessed_audio_path = db.Column(db.Text)
    description = db.Column(db.Text)
    language = db.Column(db.Text)

    segments = db.relationship(
        "TranscriptSegment",
        backref="post",
        lazy="dynamic",
        order_by="TranscriptSegment.sequence_num",
    )

    def audio_len_bytes(self) -> int:
        audio_len_bytes = 0
        if self.processed_audio_path is not None and os.path.isfile(
            self.processed_audio_path
        ):
            audio_len_bytes = os.path.getsize(self.processed_audio_path)

        return audio_len_bytes


class TranscriptSegment(db.Model):  # type: ignore[name-defined, misc]
    __tablename__ = "transcript_segment"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    sequence_num = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Float, nullable=False)
    end_time = db.Column(db.Float, nullable=False)
    text = db.Column(db.Text, nullable=False)

    identifications = db.relationship(
        "Identification", backref="transcript_segment", lazy="dynamic"
    )

    __table_args__ = (
        db.Index(
            "ix_transcript_segment_post_id_sequence_num",
            "post_id",
            "sequence_num",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<TranscriptSegment {self.id} P:{self.post_id} S:{self.sequence_num} T:{self.start_time:.1f}-{self.end_time:.1f}>"


class ModelCall(db.Model):  # type: ignore[name-defined, misc]
    __tablename__ = "model_call"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)

    first_segment_sequence_num = db.Column(db.Integer, nullable=False)
    last_segment_sequence_num = db.Column(db.Integer, nullable=False)

    model_name = db.Column(db.String, nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String, nullable=False, default="pending")
    error_message = db.Column(db.Text, nullable=True)
    retry_attempts = db.Column(db.Integer, nullable=False, default=0)

    identifications = db.relationship(
        "Identification", backref="model_call", lazy="dynamic"
    )
    post = db.relationship("Post", backref=db.backref("model_calls", lazy="dynamic"))

    __table_args__ = (
        db.Index(
            "ix_model_call_post_chunk_model",
            "post_id",
            "first_segment_sequence_num",
            "last_segment_sequence_num",
            "model_name",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<ModelCall {self.id} P:{self.post_id} Segs:{self.first_segment_sequence_num}-{self.last_segment_sequence_num} M:{self.model_name} S:{self.status}>"


class Identification(db.Model):  # type: ignore[name-defined, misc]
    __tablename__ = "identification"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    transcript_segment_id = db.Column(
        db.Integer, db.ForeignKey("transcript_segment.id"), nullable=False
    )
    model_call_id = db.Column(
        db.Integer, db.ForeignKey("model_call.id"), nullable=False
    )
    confidence = db.Column(db.Float, nullable=True)
    label = db.Column(db.String, nullable=False)

    __table_args__ = (
        db.Index(
            "ix_identification_segment_call_label",
            "transcript_segment_id",
            "model_call_id",
            "label",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        # Ensure confidence is handled if None for f-string formatting
        confidence_str = (
            f"{self.confidence:.2f}" if self.confidence is not None else "N/A"
        )
        return f"<Identification {self.id} TS:{self.transcript_segment_id} MC:{self.model_call_id} L:{self.label} C:{confidence_str}>"

class Task(db.Model):  # type: ignore[name-defined, misc]
    __tablename__ = "task"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=True)
    status = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)

    post = db.relationship("Post", backref=db.backref("tasks", lazy="dynamic"))

    def __repr__(self) -> str:
        return f"<Task {self.id} Post:{self.post_id} Status:{self.status}>"