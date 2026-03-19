# Streaming Workspace

This folder is reserved for external streaming adapters.

Current streaming engine:

- `backend/app/streaming/engine.py`

The engine supports:

- Redis Streams mode (preferred for production)
- In-memory queue fallback (for local development)
