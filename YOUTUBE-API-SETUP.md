# 🎯 YouTube Data API v3 — the exact setup (forever refresh token)

This is the precise, click-by-click ritual. Do it once, top to bottom, and you
end up with a refresh token that **never expires**. Total time: ~10 minutes
per channel.

**The single most important fact in this file:**

> Google OAuth apps have two statuses on the consent screen:
>
> | Status | Refresh token lifetime |
> |---|---|
> | **Testing** | dies after **7 days** |
> | **In production** (published) | **runs forever** |
>
> Publishing requires a home page + privacy policy on your branding —
> that's exactly why the website URL matters. Both are already live for you:
>
> - **Home page:** `https://hablhabl334.github.io`
> - **Privacy policy:** `https://hablhabl334.github.io/privacy.html`
>
> Fill those two URLs into the branding section (step 3.3 below), click
> **PUBLISH APP**, and your token runs forever.

---

## Part 1 — Google Cloud project (repeat once per channel)

You already have channel projects named `tube-zenith-mindset`,
`tube-fact-vault`, `tube-ai-chronicle`, `tube-wealth-signals`.
If a project already exists, jump straight to step 3.

1. Go to **https://console.cloud.google.com** signed in with the Gmail
   that **owns** that channel.
2. Top bar → project picker → **New project** → name it `tube-<channel>` →
   **Create**. Make sure it is the selected project in the top bar.
   (Skip billing if asked — the YouTube API free quota never needs it.)

### 1.1 Enable the API

**https://console.cloud.google.com/apis/library** → search
**YouTube Data API v3** → **Enable**.

### 1.2 OAuth consent screen (where the branding URL goes)

Left menu → **APIs & Services → OAuth consent screen** (may say
"Google Auth Platform" → **Get started / Configure"):

| Field | What to enter |
|---|---|
| App name | `Zenith Factory` (any name you like) |
| User support email | your Gmail for this channel |
| Audience / User type | **External** |
| **App home page** (branding) | `https://hablhabl334.github.io` |
| **App privacy policy** (branding) | `https://hablhabl334.github.io/privacy.html` |
| Authorized domain | `hablhabl334.github.io` |
| Developer contact | your Gmail |

Then:
- **Scopes** → add `https://www.googleapis.com/auth/youtube.upload` and
  `https://www.googleapis.com/auth/youtube.readonly`
- **Test users** → **+ Add users** → add that same Gmail (yourself)
- **Back on the OAuth consent screen summary page**

### 1.3 🚀 THE FOREVER STEP — PUBLISH APP

On the consent screen summary page, next to **Publishing status**, click
**PUBLISH APP → Confirm**.

- If Google says "verification required" → **you can safely ignore it for
  personal use.** Verification only matters when 100+ OTHER people use your
  app. You are the only user, and your own account (added as test user)
  authorizes fine.
- The status must now read **In production**.
- ⚠️ If it still says "Testing", refresh tokens for it die in 7 days.

### 1.4 Create the OAuth client

**APIs & Services → Credentials → + Create credentials → OAuth client ID**:

| Field | What to enter |
|---|---|
| Application type | **Desktop app** |
| Name | anything (`tube-autopilot`) |

→ **Create** → **Download JSON** → save it as
`client_secret_<channel>.json` on your computer.

> Desktop app is the right type: it matches `tools/auth.py`, which runs a
> tiny local browser flow on your machine. No redirect URIs to configure.

---

## Part 2 — Mint the forever refresh token (once per channel)

On your own computer, in this repo's folder:

```bash
pip install -r requirements.txt

python tools/auth.py --channel mindset --client-secret client_secret_mindset.json
python tools/auth.py --channel facts   --client-secret client_secret_facts.json
python tools/auth.py --channel tech    --client-secret client_secret_tech.json
python tools/auth.py --channel money   --client-secret client_secret_money.json
```

A browser opens → log in with the Gmail that OWNS that channel → if you see
**"Warning: this app isn't verified"** click
**Advanced → Go to (app name) (unsafe)** — normal for personal unverified
apps in production → **Continue/Allow**.

The script then prints the three values for that channel:

```
YT_CLIENT_ID_<CH>      (also visible in the JSON you downloaded)
YT_CLIENT_SECRET_<CH>  (also visible in the JSON you downloaded)
YT_REFRESH_TOKEN_<CH>  (the forever token — minted AFTER you published)
```

**Mint the token only AFTER clicking PUBLISH APP** — tokens minted while
the app is in Testing status carry the 7-day expiry. If you minted one
earlier by mistake, just re-run `tools/auth.py` now.

---

## Part 3 — GitHub secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**.

### Style A — one secret for everything (recommended)

Create **one** secret named `FACTORY_ENV` whose value is all lines at once:

```
YT_CLIENT_ID=xxxxx.apps.googleusercontent.com
YT_CLIENT_SECRET=xxxxx
YT_REFRESH_TOKEN_MINDSET=xxxxx
YT_REFRESH_TOKEN_FACTS=xxxxx
YT_REFRESH_TOKEN_TECH=xxxxx
YT_REFRESH_TOKEN_MONEY=xxxxx
GEMINI_API_KEY=xxxxx
```

Every workflow in this repo reads it automatically.

### Style B — individual secrets

`YT_REFRESH_TOKEN_MINDSET`, `YT_REFRESH_TOKEN_FACTS`,
`YT_REFRESH_TOKEN_TECH`, `YT_REFRESH_TOKEN_MONEY` (+ shared
`YT_CLIENT_ID` / `YT_CLIENT_SECRET`, or per-channel `YT_CLIENT_ID_<CH>` /
`YT_CLIENT_SECRET_<CH>` if each project has its own client).

---

## Part 4 — Test it in GitHub (the proof)

1. Repo → **Actions** tab → pick **verify-token** → **Run workflow** → Run.
2. Green ✅ with your channel name + subscriber count = the forever token
   is alive and pulling data from YouTube's servers. Done, forever.
3. Also run **smoke-test** (Actions → smoke-test → Run workflow) to prove
   the whole video factory renders offline on GitHub's servers.

Locally you can do the same: `python tools/check_token.py`.

---

## Why the token "runs forever" — and the 4 ways to kill it

A production refresh token stays valid **indefinitely** as long as:

1. **You keep using it** at least once every 6 months (a scheduled GitHub
   Action does that automatically — yours posts daily).
2. You don't **revoke** it: Google account →
   https://myaccount.google.com/permissions → remove the app.
3. You don't flip the OAuth consent screen **back to Testing** or delete
   the Google Cloud project.
4. You don't change the Google account password (some flows invalidate
   tokens; if a 401 ever appears, re-run `tools/auth.py` — takes 30 seconds).

If a check ever fails with `invalid_grant`, that's what happened —
re-run `tools/auth.py` for that channel and update the secret.

---

## Quota cheat sheet (why this stays free)

| Action | API quota units |
|---|---|
| Access-token refresh | 0 |
| `channels.list` (the verify-token check) | 1 |
| Video upload | 1,600 |
| Thumbnail set | 50 |

Free tier = **10,000 units/day per project**. With one project per channel
that's ~6 uploads/day/channel — this repo's default (5/day) fits with room
to spare, and `src/youtube.py` refuses to cross the line locally.
