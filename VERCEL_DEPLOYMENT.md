# SafarLedger — Vercel deployment

This project is prepared for Vercel's Python/Flask runtime.

## 1. Database

Vercel does not provide a persistent PostgreSQL filesystem/database for this Flask app. Keep using a hosted PostgreSQL database such as Neon or another Postgres provider.

Set `DATABASE_URL` in Vercel Project Settings -> Environment Variables.

For Neon on Vercel, use Neon's **pooled** connection string (the hostname normally
contains `-pooler`). SafarLedger also uses a small SQLAlchemy connection pool with
connection health checks so each Vercel instance does not open a large number of
idle PostgreSQL connections.

## 2. Required environment variables

- `SECRET_KEY`
- `DATABASE_URL`

Optional:
- `WEATHER_API_KEY`
- `SESSION_COOKIE_SECURE=true`
- `RATELIMIT_STORAGE_URI` (use a persistent Redis/Upstash URL for production rate limiting)

Do not upload `.env`; production secrets belong in Vercel Environment Variables.

## 3. Database migration

Run migrations against the production database before/after the first deployment from a machine with the project dependencies installed:

```powershell
flask db upgrade
```

Do not put `flask db upgrade` inside every request.

## 4. Deploy

Install Vercel CLI:

```powershell
npm i -g vercel
```

From this folder:

```powershell
vercel
vercel --prod
```

Or connect the Git repository in Vercel and deploy.

## 5. Region

The production Neon database used by this project is in AWS ap-southeast-1
(Singapore). `vercel.json` pins the Vercel Function region to `sin1` so database
round trips stay in the same general region. Redeploy after changing the region.

The Flask entry point is the root `index.py`, which exposes `app = create_app()` to Vercel's Python runtime.


## Receipt / Bill Storage

SafarLedger stores uploaded bill images directly in **Neon PostgreSQL** as binary (`BYTEA`) data. The authenticated Flask route streams the saved receipt back only to the user who owns the expense.

No Vercel Blob store or `BLOB_READ_WRITE_TOKEN` is required. The receipt image, filename, and content type are stored with the expense in NeonDB.

The current server-upload flow limits receipt images to 4 MB, which stays below Vercel Functions' 4.5 MB request-body limit.
