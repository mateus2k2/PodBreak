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
