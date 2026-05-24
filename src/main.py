import logging
import os
from waitress import serve
from shared.config import get_config
from podcast_processor.podcast_processor import PodcastProcessor
from app.models import Post, Task, Identification, TranscriptSegment
from app import create_app, config, logger
import requests
from app.models import Post, Task
import litellm

def main():
    app = create_app()
    
    # with app.app_context():
    #     processor = PodcastProcessor(config=config, logger=logger)
    #     post = processor.db_session.query(Post).filter_by(id=1).first()
    #     task = processor.db_session.query(Task).filter_by(id=1).first()
    #     processor.process(post, task, blocking=True)
    #     logger.info("Post processed successfully.")

    serve(
        app,
        host="0.0.0.0",
        threads=config.threads,
        port=config.server_port,
    )

        
if __name__ == "__main__":
    main() 



# from litellm import completion

# response = completion(
#     model="ollama/gemma3:4b", 
#     messages=[{ "content": "respond in 20 words. who are you?","role": "user"}], 
#     api_base="http://localhost:11333"
# )
# print(response)