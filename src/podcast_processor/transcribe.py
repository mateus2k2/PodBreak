import logging
import shutil
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List

from groq import Groq
from openai import OpenAI
from openai.types.audio.transcription_segment import TranscriptionSegment
from pydantic import BaseModel

from podcast_processor.audio import split_audio
from shared.config import GroqWhisperConfig, RemoteWhisperConfig

def get_mock_result():
    segments = {
        "segments": [
            {
                "id": i,
                "seek": 0,
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
                "tokens": [1, 2, 3],
                "temperature": 0.0,
                "avg_logprob": -0.123,
                "compression_ratio": 1.5,
                "no_speech_prob": 0.01,
            }
            for i, seg in enumerate([
                {"start": 2.765, "end": 7.493, "text": " Você está ouvindo Nerdcast, no Jovem Nerd."},
                {"start": 14.813, "end": 16.315, "text": " Lambda, lambda, lambda, nerds!"},
                {"start": 16.355, "end": 19.378, "text": "Aqui é o Alexandre Antônio do Jovem Nerd, de Animal Staking."},
                {"start": 19.598, "end": 23.442, "text": "Aqui é a Catiúcha Barcelos, e eu espero não ter que enfrentar nenhum gorila."},
                {"start": 23.642, "end": 28.006, "text": "Aqui é o Tucano, e nem que os 100 caras fossem 100 Shaquille O'Neal, não dava."},
            ])
        ]
    }
    return segments


class Segment(BaseModel):
    start: float
    end: float
    text: str


class Transcriber(ABC):

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    def transcribe(self, audio_file_path: str) -> List[Segment]:
        pass


class LocalTranscriptSegment(BaseModel):
    id: int
    # seek: int
    start: float
    end: float
    text: str
    # tokens: List[int]
    # temperature: float
    # avg_logprob: float
    # compression_ratio: float
    # no_speech_prob: float

    def to_segment(self) -> Segment:
        return Segment(start=self.start, end=self.end, text=self.text)


class LocalWhisperTranscriber(Transcriber):
    def __init__(self, logger: logging.Logger, whisper_model: str, batch_size: int, compute_type: str, device: str):
        self.logger = logger
        self.whisper_model = whisper_model
        self.batch_size = batch_size
        self.compute_type = compute_type
        self.device = device

    @property
    def model_name(self) -> str:
        return f"local_{self.whisper_model}"

    @staticmethod
    def convert_to_pydantic(
        transcript_data: List[Any],
    ) -> List[LocalTranscriptSegment]:
        return [
        LocalTranscriptSegment(
            id=i,
            start=item["start"],
            end=item["end"],
            text=item["text"]
        )
        for i, item in enumerate(transcript_data)
        ]

    @staticmethod
    def local_seg_to_seg(local_segments: List[LocalTranscriptSegment]) -> List[Segment]:
        return [seg.to_segment() for seg in local_segments]

    def transcribe(self, audio_file_path: str, language: str) -> List[Segment]:
        # Import whisper only when needed to avoid CUDA dependencies during module import
        try:
            import whisperx as whisper  # type: ignore[import-untyped]
        except ImportError as e:
            self.logger.error(f"Failed to import whisper: {e}")
            raise ImportError(
                "whisper library is required for LocalWhisperTranscriber"
            ) from e

        self.logger.info("Using local whisper: %s", audio_file_path)
        model = whisper.load_model(self.whisper_model, self.device, compute_type=self.compute_type, download_root="./models")
        self.logger.info("Beginning transcription")
        start = time.time()
        result = get_mock_result()  
        audio = whisper.load_audio(audio_file_path)
        result = model.transcribe(audio, batch_size=self.batch_size, language=language)
        model_a, metadata = whisper.load_align_model(language_code=language, device=self.device)
        result = whisper.align(result["segments"], model_a, metadata, audio, self.device, return_char_alignments=False)
        end = time.time()
        elapsed = end - start
        self.logger.info(f"Transcription completed in {elapsed}")
        segments = result["segments"]
        typed_segments = self.convert_to_pydantic(segments)

        return self.local_seg_to_seg(typed_segments)

class OpenAIWhisperTranscriber(Transcriber):

    def __init__(self, logger: logging.Logger, config: RemoteWhisperConfig):
        self.logger = logger
        self.config = config

        self.openai_client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout_sec,
        )

    @property
    def model_name(self) -> str:
        return self.config.model  # e.g. "whisper-1"

    def transcribe(self, audio_file_path: str) -> List[Segment]:
        self.logger.info("Using remote whisper")
        audio_chunk_path = audio_file_path + "_parts"

        chunks = split_audio(
            Path(audio_file_path),
            Path(audio_chunk_path),
            self.config.chunksize_mb * 1024 * 1024,
        )

        all_segments: List[TranscriptionSegment] = []

        for chunk in chunks:
            chunk_path, offset = chunk
            segments = self.get_segments_for_chunk(str(chunk_path))
            all_segments.extend(self.add_offset_to_segments(segments, offset))

        shutil.rmtree(audio_chunk_path)
        return self.convert_segments(all_segments)

    @staticmethod
    def convert_segments(segments: List[TranscriptionSegment]) -> List[Segment]:
        return [
            Segment(
                start=seg.start,
                end=seg.end,
                text=seg.text,
            )
            for seg in segments
        ]

    @staticmethod
    def add_offset_to_segments(
        segments: List[TranscriptionSegment], offset_ms: int
    ) -> List[TranscriptionSegment]:
        offset_sec = float(offset_ms) / 1000.0
        for segment in segments:
            segment.start += offset_sec
            segment.end += offset_sec

        return segments

    def get_segments_for_chunk(self, chunk_path: str) -> List[TranscriptionSegment]:
        with open(chunk_path, "rb") as f:
            self.logger.info(f"Transcribing chunk {chunk_path}")

            transcription = self.openai_client.audio.transcriptions.create(
                model=self.config.model,
                file=f,
                timestamp_granularities=["segment"],
                language=self.config.language,
                response_format="verbose_json",
            )

            self.logger.debug("Got transcription")

            segments = transcription.segments
            assert segments is not None

            self.logger.debug(f"Got {len(segments)} segments")

            return segments


class GroqTranscriptionSegment(BaseModel):
    start: float
    end: float
    text: str


class GroqWhisperTranscriber(Transcriber):

    def __init__(self, logger: logging.Logger, config: GroqWhisperConfig):
        self.logger = logger
        self.config = config
        self.client = Groq(
            api_key=config.api_key,
            max_retries=config.max_retries,
        )

    @property
    def model_name(self) -> str:
        return f"groq_{self.config.model}"

    def transcribe(self, audio_file_path: str) -> List[Segment]:
        self.logger.info("Using Groq whisper")
        audio_chunk_path = audio_file_path + "_parts"

        chunks = split_audio(
            Path(audio_file_path), Path(audio_chunk_path), 12 * 1024 * 1024
        )

        all_segments: List[GroqTranscriptionSegment] = []

        for chunk in chunks:
            chunk_path, offset = chunk
            segments = self.get_segments_for_chunk(str(chunk_path))
            all_segments.extend(self.add_offset_to_segments(segments, offset))

        shutil.rmtree(audio_chunk_path)
        return self.convert_segments(all_segments)

    @staticmethod
    def convert_segments(segments: List[GroqTranscriptionSegment]) -> List[Segment]:
        return [
            Segment(
                start=seg.start,
                end=seg.end,
                text=seg.text,
            )
            for seg in segments
        ]

    @staticmethod
    def add_offset_to_segments(
        segments: List[GroqTranscriptionSegment], offset_ms: int
    ) -> List[GroqTranscriptionSegment]:
        offset_sec = float(offset_ms) / 1000.0
        for segment in segments:
            segment.start += offset_sec
            segment.end += offset_sec

        return segments

    def get_segments_for_chunk(self, chunk_path: str) -> List[GroqTranscriptionSegment]:

        self.logger.info(f"Transcribing chunk {chunk_path} using groq client")
        transcription = self.client.audio.transcriptions.create(
            file=Path(chunk_path),
            model=self.config.model,
            response_format="verbose_json",  # Ensure segments are included
            language=self.config.language,
        )
        self.logger.debug("Got transcription from groq client")

        if transcription.segments is None:  # type: ignore [attr-defined]
            self.logger.warning(f"No segments found in transcription for {chunk_path}")
            return []

        groq_segments = [
            GroqTranscriptionSegment(
                start=seg["start"], end=seg["end"], text=seg["text"]
            )
            for seg in transcription.segments  # type: ignore [attr-defined]
        ]

        self.logger.debug(f"Got {len(groq_segments)} segments")
        return groq_segments
