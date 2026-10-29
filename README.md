# iPhone Duo stock tracker (92075, AT&T)

Watches in-store pickup stock for **iPhone Duo 512GB Night Sky** within 50 miles of 92075
and pushes an alert to your phone when any store has it. Runs on GitHub Actions.

| Source | What it checks | Notes |
|---|---|---|
| Apple Store | Part MK1H4LL/A | Pick **AT&T** at checkout, or buy unlocked; both work on AT&T |
| Best Buy | AT&T model, SKU 6525562 | Off unless you have a Best Buy API key (they now require a business email) |
| AT&T stores | Not covered | AT&T has no public stock API |

## Setup
1. Install the **ntfy** app and subscribe to a hard-to-guess topic, e.g. `iphoneduo-92075-k8q2x7`.
2. Optional: Best Buy API key from https://developer.bestbuy.com (requires a business/custom-domain email).
3. Repo **Settings → Secrets and variables → Actions → New repository secret**:
   - `NTFY_TOPIC` = your topic name
   - `BESTBUY_API_KEY` = your Best Buy key (without it, only Apple is checked)
4. **Settings → General → Danger Zone → Change visibility → Public.**
   Public repos get unlimited free Actions minutes, so it checks every 5 minutes, around the clock.
   Private repos only check every ~30 minutes. Secrets stay hidden either way.
5. **Actions** tab → "iPhone Duo stock check" → **Run workflow** → tick
   "Send a test notification only". The push lists which stores are being watched.

## When an alert fires
Tap it to open that retailer's page and reserve pickup immediately. One alert per store per restock.

## If it breaks
If a retailer blocks the request or a key is wrong, the run fails and GitHub emails you.
The other retailer keeps being checked. See the Actions logs for details.
