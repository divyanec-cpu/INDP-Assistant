# Deployment Guide — defence-kb

A step-by-step runbook for getting the web page live on the internet via Render, so people on
different networks (not just your home Wi-Fi) can use it from a phone or laptop. This is a
different kind of document from the other four — it's a checklist you follow once (and again
each time you redeploy), not a standing reference.

Everything up through "local commit" is already done for you. From here on, the steps below are
things only you can do — creating accounts, entering payment/signup details, and clicking
through dashboards aren't things Claude can do on your behalf.

## What's already done

- The project is a local git repository with one commit containing everything the app needs to
  run (code, the embedded vector database, the chunked text) — but nothing secret (`config/.env`
  is excluded) and nothing unnecessary (the raw PDFs and intermediate text files are excluded,
  since the running app doesn't need them).
- `scripts/webapp.py` is a Flask app with a password gate (`SHARED_ACCESS_PASSWORD`), tested
  locally: the auth gate correctly blocks unauthenticated/wrong-password requests, and a real
  question flows through correctly with citations rendered.
- `Procfile` tells Render how to start the app in production (`gunicorn`, not Flask's own dev
  server — gunicorn doesn't run on Windows, so this only gets exercised on Render's Linux build).

## Step 1 — Create a GitHub repository

1. Go to github.com (sign in, or create a free account if you don't have one — that part's on
   you, Claude can't create accounts).
2. Click **New repository**. Recommended: name it `defence-kb`, set it to **Private** (the app
   logic and aggregated procurement corpus live here, even though the individual source documents
   are public — you can switch it to public later if you want).
3. Do **not** initialize it with a README, .gitignore, or license — this project already has all
   of that; adding them on GitHub's side would conflict with the push in Step 2.
4. Once created, copy the repository's URL (the green **Code** button, HTTPS tab — looks like
   `https://github.com/your-username/defence-kb.git`).

## Step 2 — Push the code

Give Claude that URL and ask it to push. It will run:
```
git remote add origin <your-repo-url>
git push -u origin master
```
Claude will ask for your explicit go-ahead before this step, since pushing puts the code
somewhere externally visible (even on a private repo, it's leaving your machine).

## Step 3 — Create a Render account and connect the repo

1. Go to render.com and sign up (again, your own account — Claude can't do this step).
2. From the Render dashboard, click **New +** → **Web Service**.
3. Connect your GitHub account when prompted, and select the `defence-kb` repository.
4. Render should auto-detect it as a Python app. Leave the build command as the default
   (`pip install -r requirements.txt`) — the `Procfile` in the repo tells Render how to actually
   start it, so you shouldn't need to set a separate start command.
5. Pick the **Free** instance type.

## Step 4 — Set environment variables

Still on Render's service setup page (or under the service's **Environment** tab after creation),
add three environment variables:

| Key | Value |
|---|---|
| `VOYAGE_API_KEY` | The same key from your local `config/.env` |
| `ANTHROPIC_API_KEY` | The same key from your local `config/.env` |
| `SHARED_ACCESS_PASSWORD` | A password you choose — share this only with people you want using the tool |

**Never commit these to git or paste them anywhere else** — Render's dashboard is the only place
they should live for the deployed app.

## Step 5 — Deploy and test

1. Click **Create Web Service** (or **Deploy** if you already created it). Render will build and
   start the app — this can take a few minutes the first time.
2. Once it shows "Live," open the URL Render gives you (looks like
   `https://defence-kb.onrender.com`) in a browser. Your browser will prompt for a
   username/password — leave the username blank or anything, and enter the
   `SHARED_ACCESS_PASSWORD` you set in Step 4.
3. Ask a real question and confirm you get a real, cited answer.
4. **Test from your phone, on mobile data (not your home Wi-Fi)** — this is the one thing Claude
   cannot verify itself. If it works there, it'll work from anywhere.

## What to expect

- **Free tier sleeps.** After a period of inactivity, Render spins the app down. The next
  request wakes it back up, but that first request can take 30-60 seconds — not a bug, just how
  the free tier works.
- **Every question costs real money** from your Voyage/Anthropic API keys, once anyone with the
  shared password can reach this. Share the password only with people you actually want using it.
- **Redeploying:** any time you want to update the live app with local changes, ask Claude to
  commit and push again — Render redeploys automatically on a new push to the connected branch.
