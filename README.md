# Social Media Marketing Portal MVP

Separate project workspace for the customer portal.

## Stack
- Frontend: Next.js
- Backend: FastAPI
- DB: Postgres
- Queue: Redis
- Hosting: Coolify
- Auth: email/password first, then teams/roles
- Storage: local

## Layout
- `frontend/` — customer portal UI
- `backend/` — API and worker-ready backend
- `docker-compose.yml` — local + Coolify-friendly service layout

## Deploy notes
- `docker-compose.yml` is the primary deployment target
- the backend starts a small publish worker on boot so queued jobs advance automatically
- set production secrets before deploying: database URL, Telegram bridge token, social platform API tokens, and frontend API base URL
- the publish flow now talks to live providers when the relevant secrets are set:
  - Telegram Bot API
  - X/Twitter API v2
  - LinkedIn UGC API
  - Meta Graph API for Facebook and Instagram
  - TikTok via configured publish gateway
  - Custom Gateway via configured HTTP endpoint

