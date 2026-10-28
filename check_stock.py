#!/usr/bin/env python3
"""Check Apple Store pickup availability for one iPhone part near a ZIP code
and push a phone notification (ntfy.sh) when it shows up in stock.

Standard library only. Config via environment variables:
  PART           Apple part number          (default MK1H4LL/A = iPhone Duo 512GB Night Sky, US)
  ZIP            Search location            (default 92075)
  MAX_MILES      Ignore stores farther away (default 50)
  NTFY_TOPIC     ntfy.sh topic to push to   (required for alerts)
  LOOP_SECONDS   Keep polling this long     (default 0 = check once)
  INTERVAL       Seconds between polls      (default 60)
  STATE_FILE     Remembers stores already alerted (default state.json)
  TEST_NOTIFY    "true" sends a test push and exits
"""
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request

PART = os.environ.get("PART", "MK1H4LL/A")
ZIP = os.environ.get("ZIP", "92075")
MAX_MILES = float(os.environ.get("MAX_MILES", "50"))
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
LOOP_SECONDS = int(os.environ.get("LOOP_SECONDS", "0"))
INTERVAL = int(os.environ.get("INTERVAL", "60"))
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
PRODUCT = "iPhone Duo 512GB Night Sky"
BUY_URL = "https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-512gb-night-sky-unlocked"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BUY_URL,
}


def fetch_availability():
    qs = urllib.parse.urlencode({
        "pl": "true",
        "mts.0": "regular",
        "parts.0": PART,
        "location": ZIP,
    })
    url = f"https://www.apple.com/shop/fulfillment-messages?{qs}"
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:  # HTTP errors, timeouts, bad JSON
            last_err = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Apple request failed: {last_err}")


def parse_stores(data):
    """Return list of dicts for stores within MAX_MILES, with availability flag."""
    stores = (data.get("body", {}).get("content", {})
                  .get("pickupMessage", {}).get("stores", [])) or []
    out = []
    for s in stores:
        try:
            miles = float(s.get("storedistance", 9999))
        except (TypeError, ValueError):
            miles = 9999.0
        if miles > MAX_MILES:
            continue
        pa = (s.get("partsAvailability") or {}).get(PART, {})
        quote = (pa.get("messageTypes", {}).get("regular", {}).get("storePickupQuote")
                 or pa.get("pickupSearchQuote") or "")
        out.append({
            "id": s.get("storeNumber", ""),
            "name": s.get("storeName", "?"),
            "city": s.get("city", ""),
            "miles": miles,
            "available": pa.get("pickupDisplay") == "available",
            "quote": quote,
        })
    return sorted(out, key=lambda x: x["miles"])


def notify(title, message, click=BUY_URL, priority="urgent", tags="iphone,rotating_light"):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC not set; skipping push:", title, "|", message)
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{urllib.parse.quote(NTFY_TOPIC)}",
        data=message.encode(),
        headers={"Title": title, "Priority": priority, "Tags": tags, "Click": click},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        print("Push sent:", r.status)


def load_state():
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f).get("alerted", []))
    except (OSError, ValueError):
        return set()


def save_state(alerted):
    with open(STATE_FILE, "w") as f:
        json.dump({"alerted": sorted(alerted)}, f)


def check_once(alerted):
    stores = parse_stores(fetch_availability())
    stamp = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    if not stores:
        print(f"[{stamp}] No stores returned within {MAX_MILES} mi of {ZIP}.")
    for s in stores:
        mark = "IN STOCK" if s["available"] else "-"
        print(f"[{stamp}] {s['miles']:5.1f} mi  {s['name']:<22} {mark:<9} {s['quote']}")

    in_stock = {s["id"]: s for s in stores if s["available"]}
    new = [s for sid, s in in_stock.items() if sid not in alerted]
    if new:
        lines = [f"{s['name']} ({s['city']}, {s['miles']:.0f} mi): {s['quote'] or 'available'}"
                 for s in new]
        notify(f"{PRODUCT} IN STOCK", "\n".join(lines) + "\nTap to reserve pickup.")
    # Forget stores that sold out so a restock alerts again.
    return set(in_stock)


def main():
    if os.environ.get("TEST_NOTIFY", "").lower() == "true":
        notify("Tracker test", f"Notifications work. Watching {PRODUCT} near {ZIP}.",
               priority="default", tags="white_check_mark")
        return 0

    alerted = load_state()
    deadline = time.time() + LOOP_SECONDS
    failures = 0
    while True:
        try:
            alerted = check_once(alerted)
            save_state(alerted)
            failures = 0
        except Exception as e:
            failures += 1
            print(f"Check failed ({failures}): {e}", file=sys.stderr)
            if LOOP_SECONDS == 0 or failures >= 5:
                return 1  # fail the run so GitHub emails you that the tracker is broken
        if time.time() + INTERVAL > deadline:
            return 0
        time.sleep(INTERVAL + random.uniform(-5, 5))


if __name__ == "__main__":
    sys.exit(main())
