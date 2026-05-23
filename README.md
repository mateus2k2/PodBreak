# PodBreak — Podcast Ad Segment Detector 🎧🔎

> Detect ad segments in podcast audio using Whisper-powered transcription and an any open OpenAPI-compliant LLM backend .

## Overview
AdSleuth transcribes podcast audio (local Whisper or remote OpenAI Whisper API), analyzes audio + transcript to detect ad segments (timestamps + confidence), and exposes OpenAPI-compatible endpoints for easy integration.

## Features
- Transcription via Whisper (local model or OpenAI Whisper API)
- Ad segment detection (timestamps, type, confidence)

## Tech stack
- Backend: Flask
- Transcription: Whisper (local or remote)
- Optional: Docker / Docker Dev Container

## TODOs
- Rename git repo 
- https://github.com/mateus2k2/PodBreak

jdbc:sqlite:file:\\wsl$\Ubuntu\home\mateus\WSL\PROJETOS\audiobookshelf\audiobookshelf-ai\src\instance\sqlite3.db?nolock=1
jdbc:sqlite:file:\\wsl$\Ubuntu\home\mateus\WSL\PROJETOS\audiobookshelf\audiobookshelf-web\config\absdatabase.sqlite?nolock=1


python src/main.py
python src/main.py > logs.ans 2>&1
flask --app ./src/main.py db init
flask --app ./src/main.py db migrate -m "change"
flask --app ./src/main.py db upgrade

QUANDO CRIAR A BASE DE DADOS PELO DEV CONTAINER ELE CRIA COM ROOT TEM Q AJUSTAR A PERMISSÃO DO ARQUIVO PARA EDITAR NO DBEAVER
sudo chown mateus:mateus /home/mateus/WSL/PROJETOS/whisper/src/instance/sqlite3.db
chmod 664 /home/mateus/WSL/PROJETOS/whisper/src/instance/sqlite3.db
