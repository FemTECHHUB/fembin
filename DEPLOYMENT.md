# Deploying fembin on cPanel

This is a step-by-step checklist for getting this FastAPI backend running on a cPanel
host via **Setup Python App** (Phusion Passenger). Check items off in order — several
steps depend on the one before it actually having worked, not just been attempted.

Two things about this app matter for every step below:

- **It's ASGI (FastAPI), Passenger wants WSGI.** `passenger_wsgi.py` at the repo root
  bridges the two via `a2wsgi`. Don't delete or "simplify" it — without it, Passenger
  can't call the app at all.
- **Background loops don't survive a Passenger-managed process reliably.** This app has
  an in-process outbox worker and catalog-sync loop (`OUTBOX_WORKER_ENABLED`,
  `CATALOG_SYNC_ENABLED`) designed for a VPS/Docker deployment that stays up. On cPanel,
  **leave both `false`** and use cPanel Cron Jobs calling `scripts/drain_outbox_once.py`
  / `scripts/run_catalog_sync_once.py` instead — see step 9. This isn't a workaround, the
  outbox queue (CLAUDE.md §2.2) is specifically designed so a job just waits safely
  through a gap between cron runs rather than being lost or double-posted.

---

## 0. Prerequisites — confirm before starting

- [ ] The host offers **cPanel's "Setup Python App"** (needs CloudLinux + Passenger —
      not every shared host has this; check with your host if you don't see it in
      cPanel).
- [ ] The Python version dropdown in Setup Python App includes **3.12 or newer**.
      `app/busy/xml_util.py` uses the `type X = ...` alias statement, which is
      Python 3.12+ only syntax — the app will fail to import on 3.11 or earlier. If your
      host only offers 3.11, that one line needs rewriting to a plain assignment before
      deploying there; don't attempt to work around it by changing the Python version
      requirement without also fixing the syntax.
- [ ] You have (or can create) a MySQL database on this host with enough quota for the
      catalog + outbox tables (small — this is not a data-heavy app).
- [ ] You have SSH or cPanel **Terminal** access. Running Alembic migrations and
      bootstrapping the first superadmin both need a real shell — there's no
      point-and-click way to do either from the cPanel UI.
- [ ] You've decided the domain or subdomain this will live on.

---

## 1. Push the code somewhere cPanel can get it

Two ways to get the repo onto the server — pick one:

**A — cPanel's Git™ Version Control (clones directly from GitHub)**
- [ ] cPanel → Git™ Version Control → Create → paste the GitHub repo's clone URL.
- [ ] If the repo is private, cPanel will need credentials: use a GitHub **Personal
      Access Token** as the password (not your actual GitHub password — GitHub no longer
      accepts those for Git operations), or a deploy key if cPanel's version supports it.
- [ ] Point it at the branch you actually want live (e.g. `main` once this work is
      merged in — not a feature branch, unless that's a deliberate staging deploy).

**B — Upload a zip**
- [ ] `git archive` (or just zip the repo, excluding `.venv/`, `.git/`, `__pycache__/`)
      and upload via cPanel File Manager, then extract in place.
- [ ] Simpler, no GitHub credentials touch the server at all — worth it for a first
      deploy while you're still confirming everything else works.

Either way, the app's root directory (the one **containing** `passenger_wsgi.py`) is
what you'll point Setup Python App at in step 3.

---

## 2. Create the MySQL database

- [ ] cPanel → MySQL® Databases → create a database (cPanel will prefix it with your
      account username, e.g. `youruser_fembin`).
- [ ] Create a database user, set a real generated password, and **add that user to the
      database** with full privileges (a separate step in cPanel — easy to forget).
- [ ] Note the final connection string shape:
      `mysql+pymysql://youruser_dbuser:PASSWORD@localhost/youruser_fembin`
      — you'll need this exact string in step 5.

---

## 3. Set up the Python App

- [ ] cPanel → Setup Python App → Create Application.
- [ ] **Python version:** 3.12+ (see prerequisites above).
- [ ] **Application root:** the directory from step 1 (containing `passenger_wsgi.py`).
- [ ] **Application URL:** the domain/subdomain from step 0.
- [ ] **Application startup file:** `passenger_wsgi.py`.
- [ ] **Application Entry point:** `application` (the WSGI callable `passenger_wsgi.py`
      exports).

<div></div>

> **Gotcha:** cPanel auto-generates its *own* placeholder `passenger_wsgi.py` when you
> create the app, and it will silently overwrite or conflict with the real one from the
> repo depending on how you ordered steps 1 and 3. **After creating the app, re-check
> that `passenger_wsgi.py` in the application root is still this repo's version** (it
> imports `a2wsgi` and `app.main` — cPanel's generated stub won't). Re-upload it if not.

- [ ] Note the exact virtualenv path cPanel shows you (something like
      `/home/youruser/virtualenv/app_dir/3.12/bin/`) — you'll need it for every command
      below and for the cron jobs in step 9.

---

## 4. Install dependencies

Via SSH/Terminal, using the venv path from step 3:

```bash
source /home/youruser/virtualenv/app_dir/3.12/bin/activate
cd ~/app_dir
pip install -r requirements.txt
```

- [ ] Installs cleanly with no compiler errors. `requirements.txt` is deliberately
      trimmed of `uvicorn` and its C/Rust-extension "standard" extras (uvloop, httptools,
      watchfiles, websockets) — Passenger never invokes uvicorn, so those aren't needed
      and are exactly the kind of dependency that can fail to build on shared hosting.
      If `pip install` fails on something, check it's actually still needed before
      forcing a workaround.

---

## 5. Environment variables

Set these in cPanel → Setup Python App → your app → **Environment variables** (not a
committed `.env` file — this app root may be web-servable, and `.env` should never be).

| Variable | Value |
|---|---|
| `DATABASE_URL` | The connection string from step 2 |
| `BUSY_HOST` / `BUSY_PORT` | Your BUSY server's address (port 981 by default) |
| `BUSY_USERNAME` / `BUSY_PASSWORD` | The dedicated BUSY service account (CLAUDE.md §6/NFR5 — not a human's login) |
| `JWT_SECRET_KEY` | **A real random secret** — generate one: `python -c "import secrets; print(secrets.token_hex(32))"`. Do **not** deploy with the `dev-only-change-me...` placeholder from `.env.example`. |
| `JWT_ALGORITHM` | `HS256` (default, fine to leave) |
| `JWT_EXPIRE_MINUTES` | `480` (default — one shift) or adjust |
| `CATALOG_SYNC_ENABLED` | `false` — cron handles this (step 9) |
| `OUTBOX_WORKER_ENABLED` | `false` — cron handles this (step 9) |
| `WOO_SITE_URL` / `WOO_CONSUMER_KEY` / `WOO_CONSUMER_SECRET` | Only if the WooCommerce store exists yet — leave blank otherwise, the push is skipped cleanly rather than failing |
| `LOG_LEVEL` | `INFO` |

- [ ] Every value above is a **real production value**, not copied from `.env.example`.
- [ ] Restart the app (button in Setup Python App, or `touch tmp/restart.txt` in the app
      root) after saving — env var changes don't take effect until Passenger restarts.

---

## 6. Run migrations

```bash
source /home/youruser/virtualenv/app_dir/3.12/bin/activate
cd ~/app_dir
alembic upgrade head
```

- [ ] Runs clean, no errors. Check `alembic current` afterward shows the latest revision.

---

## 7. First catalog sync (populates material centers — needed before step 8)

```bash
python scripts/run_catalog_sync_once.py --full
```

- [ ] Confirms it can actually reach BUSY from this server (this is often where a
      firewall/IP problem first surfaces — see step 11's security notes on BUSY's port
      981).
- [ ] Logs show `material_centers`, `products`, and `salesmen` all synced with
      `failed=0`.

---

## 8. Bootstrap the first superadmin

There's deliberately no HTTP endpoint for this (`POST /api/v1/auth/users` requires an
*existing* superadmin — see CLAUDE.md, this file's own docs at `/`):

```bash
python scripts/create_superadmin.py \
  --username admin --password 'a-real-password' \
  --full-name "Your Name" --material-center-code <a real code from step 7>
```

- [ ] Succeeds — if it fails with "material_center_code does not match," step 7 didn't
      actually sync anything; check that before retrying this.
- [ ] Log in at `/` → `/console` (or `POST /api/v1/auth/login`) with these credentials to
      confirm the token works end to end.

---

## 9. Cron jobs (replaces the in-process background loops — see the top of this file)

cPanel → Cron Jobs. Use the **full venv python path**, not a bare `python`:

```
* * * * * /home/youruser/virtualenv/app_dir/3.12/bin/python /home/youruser/app_dir/scripts/drain_outbox_once.py >> /home/youruser/app_dir/logs/outbox.log 2>&1
```

```
*/10 * * * * /home/youruser/virtualenv/app_dir/3.12/bin/python /home/youruser/app_dir/scripts/run_catalog_sync_once.py >> /home/youruser/app_dir/logs/sync.log 2>&1
```

- [ ] `logs/` directory exists and is writable (create it — `mkdir logs` in the app
      root — cron won't create it for you, and a missing directory means silently lost
      log output, not a cron failure).
- [ ] Outbox cron interval is short (every 1 minute) — this is the queue a rep is
      actively waiting on; catalog sync can be sparser (every 5-15 minutes) since it's
      just keeping the mirror fresh.
- [ ] After ~2 minutes, check `logs/outbox.log` shows real run output, not silence or
      Python tracebacks.

---

## 10. Verify the deployed app for real

- [ ] `https://yourdomain/` → the frontend integration guide loads (this confirms
      Passenger → `passenger_wsgi.py` → `app.main:app` is wired correctly end to end).
- [ ] `https://yourdomain/health` → `{"status": "ok"}`.
- [ ] `https://yourdomain/console` → log in with the superadmin from step 8, confirm the
      product/sales-person dropdowns populate with real synced data.
- [ ] Create one real test quotation through `/console` and watch it move
      `queued → running → done` (or `failed`, with a real error) via the cron-driven
      outbox worker from step 9 — this is the actual end-to-end proof the deployment
      works, not just that pages load.

---

## 11. Security hardening — don't skip this section

- [ ] **HTTPS is on.** cPanel → SSL/TLS Status → AutoSSL (Let's Encrypt), and confirm
      HTTP actually redirects to HTTPS, not just that HTTPS *works* alongside plain HTTP.
- [ ] **`JWT_SECRET_KEY` is the real generated one from step 5**, confirmed by checking
      the environment variables panel, not assumed.
- [ ] **BUSY's port 981 is restricted to this server's outbound IP**, not open to the
      internet — this is Sprint 5's NFR7 in `docs/sprints/sprint-05-pilot-rollout-hardening.md`,
      still unresolved as of this checklist being written. Verify with an actual external
      port scan against the BUSY host, don't just configure a firewall rule and assume it
      worked.
- [ ] **The BUSY account in `BUSY_USERNAME`/`BUSY_PASSWORD` is a dedicated service
      account**, not a human's real login (NFR5) — if it's still a placeholder/shared
      login at this point, that's a real gap, not a formality.
- [ ] `.env` is not present in the deployed app root (env vars come from cPanel's UI —
      step 5). If you did use a `.env` file instead, confirm it's **outside**
      `public_html` or blocked by an `.htaccess` deny rule — a `.env` sitting in a
      web-servable directory is a real credential leak, not a theoretical one.
- [ ] Double-check `git status`/the deployed file list doesn't include anything from
      `.gitignore` that shouldn't have made it here (it's already configured to exclude
      `.env`, `__pycache__/`, etc. — this is just confirming the exclusion actually held).

---

## 12. Known limitations to carry forward, not silently accept

- BUSY's session drops unpredictably (documented behavior, not a bug — CLAUDE.md §8).
  The cron scripts in step 9 will just log a failure and try again next run; that's
  correct behavior, but someone should be watching `logs/outbox.log` for a *sustained*
  gap, not just trusting it's fine.
- Stock is not derived or shown anywhere in this deployment — that's still an unverified
  mechanism (`app/domain/catalog/stock.py`), deliberately not wired in.
- WooCommerce push only does anything once real `WOO_*` credentials exist (step 5).
- This checklist gets the *app* running correctly. It does not by itself satisfy Sprint
  5's full Definition of Done (measured write latency for a real Sale, not just a
  Quotation; the port-981 external scan; the BUSY-session-drop runbook actually being
  rehearsed) — those are tracked in `docs/sprints/sprint-05-pilot-rollout-hardening.md`
  and shouldn't be marked done because a deployment happened.
