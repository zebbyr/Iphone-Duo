# iPhone Duo stock tracker (92075)

Checks Apple's store-pickup availability for **iPhone Duo 512GB Night Sky (MK1H4LL/A)**
at Apple Stores within 50 miles of 92075 and pushes an alert to your phone the moment
one shows "available". Runs on GitHub Actions. Nothing to host.

## Setup (5 minutes)
1. Install the **ntfy** app (iOS/Android, free).
2. In the app, subscribe to a hard-to-guess topic, e.g. `iphoneduo-92075-k8q2x7`.
   Anyone who knows the topic name can read it, so don't use something obvious.
3. In this repo: **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `NTFY_TOPIC` — Value: your topic name.
4. **Actions** tab → "iPhone Duo stock check" → **Run workflow** → tick
   "Send a test notification only". You should get a push within a few seconds.
5. Done. It checks every 30 minutes on its own.

## How often it checks
- **Private repo (current):** once every ~30 min, to stay inside the free 2,000 Actions minutes/month.
- **Public repo:** polls every 60 seconds continuously (Actions minutes are free for public repos).
  The code holds no secrets, so making the repo public is safe; your topic stays in Secrets.

## When an alert fires
Tap it → Apple's buy page → choose pickup → pick the listed store. Stock disappears in
minutes, so check out immediately. You get one alert per store per restock.

## If it breaks
If Apple blocks the request, the run fails and GitHub emails you. Check the Actions logs.
