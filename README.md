# AI Meeting Intelligence System

## Overview

The **AI Meeting Intelligence System** is an AI-powered web application designed to convert unstructured meeting audio and video recordings into structured, actionable business intelligence. 

Rather than stopping at basic transcription, the system analyzes meeting conversations in depth to identify and extract:

* **Meeting Summaries**: Concise and executive-level summaries of discussions.
* **Participants**: Identification of meeting attendees and active speakers.
* **Key Discussion Points**: Core topics, themes, and perspectives covered.
* **Decisions**: Explicit conclusions, agreements, and approved items.
* **Action Items**: Concrete tasks and deliverables assigned during the call.
* **Task Owners**: Responsible individuals associated with each action item.
* **Deadlines**: Targeted completion dates and milestones.
* **Unresolved Issues**: Open questions, blockers, and debated topics requiring further input.
* **Follow-up Items**: Next steps, scheduled check-ins, and future agenda items.
* **Meeting Sentiment**: Overall tone, engagement level, and conversational dynamics.
* **Contextual Meeting Q&A**: Interactive search and question answering across meeting transcripts.

---

## Objective

The primary objective of the AI Meeting Intelligence System is to go beyond simple speech-to-text by transforming unstructured meeting conversations into structured business intelligence. It streamlines post-meeting workflows, enhances accountability, and makes institutional knowledge searchable and accessible across teams.

---

## Planned Architecture

The high-level data processing and AI pipeline is structured as follows:

```text
Audio/Video
    ↓
Speech-to-Text
    ↓
Speaker Identification
    ↓
Timestamped Transcript
    ↓
LLM Analysis
    ↓
Structured Meeting Intelligence
    ↓
Vector Database
    ↓
Contextual Meeting Q&A
```

---

## Technology Stack

### Frontend
* **Next.js**: React framework for production-grade web applications.
* **React**: Component-based UI library.
* **TypeScript**: Type-safe JavaScript for frontend scalability.

### Backend
* **Python**: Core programming language for data processing and AI integration.
* **FastAPI**: High-performance asynchronous API framework.

### Database
* **PostgreSQL**: Relational database for metadata, users, and meeting records.
* **pgvector**: Vector similarity search extension for meeting embeddings.

### AI & Speech Services
* **Speech-to-Text**: Whisper (or equivalent transcription engines) with diarization.
* **Large Language Models (LLM)**: OpenAI, Gemini, or Claude for summarization, entity extraction, and Q&A.

### Storage
* **S3-Compatible Object Storage**: Secure storage for audio/video uploads and artifacts (e.g., AWS S3, MinIO).

---

## Planned Modules

The system is architected across 8 core modules:

1. **Authentication & User Management**: User registration, login, role-based access control (RBAC), and session security.
2. **Meeting & File Management**: Audio/video upload pipelines, file validation, storage orchestration, and metadata management.
3. **Speech-to-Text & Speaker Identification**: Audio transcription, timestamp alignment, and speaker diarization.
4. **AI Meeting Intelligence**: LLM extraction of summaries, action items, decisions, task owners, sentiment, and key points.
5. **Meeting Dashboard & Search**: Centralized dashboard for exploring meetings, metrics, status tracking, and multi-parameter filtering.
6. **Meeting Details & Transcript**: Interactive transcript viewer with synchronized playback, speaker tags, and structured outputs.
7. **AI Q&A & RAG**: Retrieval-Augmented Generation system allowing users to ask questions and retrieve answers grounded in meeting context.
8. **Integration, Testing & Deployment**: CI/CD pipelines, end-to-end testing, Docker containerization, and cloud deployment.

---

## Project Structure

```text
meeting-intelligence-system/
├── frontend/
│   ├── src/
│   │   └── app/
│   │       ├── layout.tsx
│   │       └── page.tsx
│   ├── .env.example
│   ├── next.config.mjs
│   ├── package.json
│   └── tsconfig.json
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── tests/
│   │   └── .gitkeep
│   ├── .env.example
│   └── requirements.txt
├── docs/
│   └── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

---

## Development Status

This repository is currently in the **initial setup phase**. The base project scaffold, directory structure, environment templates, and container configurations have been initialized. Application functionality will be implemented module by module according to the planned roadmap.




---

