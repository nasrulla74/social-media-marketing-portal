# Coolify deployment notes

This repo is Coolify-ready as a Docker Compose app.

## Services
- web: Next.js customer portal
- api: FastAPI backend
- db: Postgres
- redis: queue/cache

## Required environment variables
- `DATABASE_URL`
- `REDIS_URL`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `NEXT_PUBLIC_API_BASE_URL`
- `TELEGRAM_BRIDGE_TOKEN`
- `DEFAULT_TELEGRAM_TEAM_ID`
- `TELEGRAM_PUBLISH_BOT_TOKEN`
- `TELEGRAM_PUBLISH_CHAT_ID`
- `TWITTER_API_BEARER_TOKEN`
- `TWITTER_API_BASE_URL`
- `LINKEDIN_ACCESS_TOKEN`
- `LINKEDIN_AUTHOR_URN`
- `META_PAGE_ACCESS_TOKEN`
- `META_PAGE_ID`
- `META_IG_USER_ID`
- `META_DEFAULT_IMAGE_URL`
- `TIKTOK_PUBLISH_URL`
- `TIKTOK_PUBLISH_TOKEN`
- `CUSTOM_PUBLISH_URL`
- `CUSTOM_PUBLISH_TOKEN`
- `PUBLISH_WORKER_INTERVAL_SECONDS`

## Telegram workflow
- Internal Telegram commands can be forwarded to `POST /integrations/telegram/webhook`
- Set Telegram's webhook secret to the same value as `TELEGRAM_BRIDGE_TOKEN`
- The webhook uses `DEFAULT_TELEGRAM_TEAM_ID` to decide which team receives the commands

## Suggested Coolify setup
1. Create a new Docker Compose application.
2. Point it at this repository.
3. Add the env vars from `.env.example`.
4. Let Coolify build and expose the `web` service.
5. Keep `api` and `web` on the same private network.
6. Mount persistent storage only for Postgres if you want long-lived local data.

## Notes
- The portal currently uses email/password auth and team delegation inside the app.
- Payment is intentionally not included yet.
- Local storage is used for the MVP only; move uploads to object storage later if needed.
