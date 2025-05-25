import logging
import os
import threading
from typing import Any, Dict, Optional

import litellm
from jinja2 import Template
import requests

from app import db, logger
from app.models import Post, Task, Identification, TranscriptSegment
from podcast_processor.ad_classifier import AdClassifier
from podcast_processor.transcription_manager import TranscriptionManager
from shared.config import Config
from shared.processing_paths import ProcessingPaths, paths_from_unprocessed_path


class PodcastProcessor:
    """
    Main coordinator for podcast processing workflow.
    Delegates to specialized components for transcription, ad classification, and audio processing.
    """

    lock_lock = threading.Lock()
    locks: Dict[str, threading.Lock] = {}

    def __init__(
        self,
        config: Config,
        logger: Optional[logging.Logger] = None,
        transcription_manager: Optional[TranscriptionManager] = None,
        ad_classifier: Optional[AdClassifier] = None,
        db_session: Optional[Any] = None,
    ) -> None:
        super().__init__()
        self.logger = logger or logging.getLogger("global_logger")
        self.output_dir = "srv"
        self.config: Config = config
        self.db_session = db_session or db.session

        litellm.api_base = self.config.openai_base_url
        litellm.api_key = self.config.llm_api_key

        # Initialize components with default implementations if not provided
        if transcription_manager is None:
            self.transcription_manager = TranscriptionManager(self.logger, config)
        else:
            self.transcription_manager = transcription_manager

        if ad_classifier is None:
            self.ad_classifier = AdClassifier(config)
        else:
            self.ad_classifier = ad_classifier

    def process(self, post: Post, task: Task, blocking: bool) -> str:
        """
        Process a podcast by transcribing, identifying ads, and removing ad segments.

        Args:
            post: The Post object containing the podcast to process
            blocking: Whether to block if another process is already processing this podcast

        Returns:
            The adds segments
        """
        locked = False

        unprocessed_audio_path = post.unprocessed_audio_path
        with PodcastProcessor.lock_lock:
            if unprocessed_audio_path not in PodcastProcessor.locks:
                PodcastProcessor.locks[unprocessed_audio_path] = threading.Lock()
                PodcastProcessor.locks[unprocessed_audio_path].acquire()  # no contention expected
                locked = True

        if not locked and not PodcastProcessor.locks[unprocessed_audio_path].acquire(
            blocking=blocking
        ):
            raise ProcessorException("Processing job in progress")

        try:
            self.logger.info(f"Processing podcast: '{post.title}' started")

            # Check if the post is already processed in the database
            existing_post = (
                self.db_session.query(Post)
                .filter(Post.title == post.title and Post.rss_feed_url == post.rss_feed_url)
                .first()
            )
            if existing_post:
                self.logger.info(f"Post '{post.title}' already processed.")
                # return []

            # Step 1: Transcribe audio
            transcript_segments = self.transcription_manager.transcribe(post)

            # Step 2: Classify ad segments
            user_prompt_template = self.get_user_prompt_template(
                self.config.processing.user_prompt_template_path
            )
            system_prompt = self.get_system_prompt(
                self.config.processing.system_prompt_path
            )
            self.ad_classifier.classify(
                transcript_segments=transcript_segments,
                system_prompt=system_prompt,
                user_prompt_template=user_prompt_template,
                post=post,
            )

            # Step 3: Set task status to "completed" and callback URL
            self.callback(post, task)

            self.logger.info(f"Processing podcast: {post} complete")
            return []
        finally:
            PodcastProcessor.locks[unprocessed_audio_path].release()

    def callback(self, post: Post, task: Task) -> None:
        """
        Callback function to be called after processing is complete.
        This can be used to update the database or notify other services.

        Args:
            post: The Post object containing the podcast to process
            task: The Task object containing the processing task
        """
        # Update the database or notify other services as needed
        task.status = "completed"
        self.db_session.commit()

        # for the given post, get all the transcript_segments that is present in the  identification where its transcript_segment_id has the same post_id from the current post
        identifications = TranscriptSegment.query.join(Identification).filter(TranscriptSegment.post_id == post.id).all()
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

        # make request fot config.callback_url
        self.logger.info(f"Callback for post {post.id} and task {task.id} completed.")
        try:
            response = requests.post(self.config.callback_url, json={"segments": result})
            response.raise_for_status()  # <- This can raise HTTPError
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Callback failed")
            # raise ProcessorException(f"Callback failed")

    
    def get_system_prompt(self, system_prompt_path: str) -> str:
        """Load the system prompt from a file."""
        with open(system_prompt_path, "r") as f:
            return f.read()

    def get_user_prompt_template(self, prompt_template_path: str) -> Template:
        """Load the user prompt template from a file."""
        with open(prompt_template_path, "r") as f:
            return Template(f.read())

class ProcessorException(Exception):
    """Exception raised for podcast processing errors."""
