import logging
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
            self.logger.info(f"Processing podcast: '{post.title}' - {post.guid} started")

            # Step 1: Transcribe audio
            transcript_segments = self.transcription_manager.transcribe(post)

            # Step 2: Classify ad segments
            user_prompt_template = self.get_user_prompt_template(
                self.config.processing.resolve_user_prompt_template_path(post.language)
            )
            system_prompt = self.get_system_prompt(
                self.config.processing.resolve_system_prompt_path(post.language)
            )
            self.ad_classifier.classify(
                transcript_segments=transcript_segments,
                system_prompt=system_prompt,
                user_prompt_template=user_prompt_template,
                post=post,
            )


            self.logger.info(f"Processing podcast: {post} complete")
            return []
        finally:
            PodcastProcessor.locks[unprocessed_audio_path].release()


    def get_system_prompt(self, system_prompt_path: str) -> str:
        with open(system_prompt_path, "r") as f:
            return f.read()

    def get_user_prompt_template(self, prompt_template_path: str) -> Template:
        """Load the user prompt template from a file."""
        with open(prompt_template_path, "r") as f:
            return Template(f.read())

class ProcessorException(Exception):
    """Exception raised for podcast processing errors."""
