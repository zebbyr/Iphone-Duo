#!/usr/bin/env python3
"""Watch in-store pickup stock for iPhone Duo 512GB Night Sky near a ZIP code
and push a phone notification (ntfy.sh) when any nearby store has it.

Sources:
  apple    Apple Store pickup (part MK1H4LL/A; activate on AT&T at checkout)
  bestbuy  Best Buy AT&T model (SKU 6525562), via Best Buy's official API

Standard library only. Config via environment variables:
  ZIP              Search location               (default 92075)
  MAX_MILES        Ignore stores farther away    (default 50)
  NTFY_TOPIC       ntfy.sh topic to push to      (required for alerts)
  BESTBUY_API_KEY  Free key from developer.bestbuy.com (Best Buy skipped if unset)
  APPLE_PART       default MK1H4LL/A
  BESTBUY_SKU      default 6525562 (AT&T)
  LOOP_SECONDS     Keep polling this long        (default 0 = check once)
  INTERVAL         Seconds between polls         (default 60)
  STATE_FILE       Remembers stores already alerted (default state.json)
  TEST_NOTIFY      "true" sends a test push and exits
"""
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request

ZIP = os.environ.get("ZIP", "92075")
MAX_MILES = float(os.environ.get("MAX_MILES", "50"))
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
BESTBUY_API_KEY = os.environ.get("BESTBUY_API_KEY", "").strip()
APPLE_PART = os.environ.get("APPLE_PART", "MK1H4LL/A")
BESTBUY_SKU = os.environ.get("BESTBUY_SKU", "6525562")
LOOP_SECONDS = int(os.environ.get("LOOP_SECONDS", "0"))
INTERVAL = int(os.environ.get("INTERVAL", "60"))
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
PRODUCT = "iPhone Duo 512GB Night Sky"

APPLE_URL = "https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-512gb-night-sky-unlocked"
BESTBUY_URL = f"https://www.bestbuy.com/site/sku/{BESTBUY_SKU}.p?skuId={BESTBUY_SKU}"

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")


def get_json(url, headers=None):
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:  # HTTP errors, timeouts, bad JSON
            last_err = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"request failed: {last_err}")


def to_miles(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 9999.0


# Each source returns a list of stores: {id, name, city, miles, available, quote, url}

def check_apple():
    qs = urllib.parse.urlencode({"pl": "true", "mts.0": "regular",
                                 "parts.0": APPLE_PART, "location": ZIP})
    data = get_json(f"https://www.apple.com/shop/fulfillment-messages?{qs}", {
        "User-Agent": BROWSER_UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": APPLE_URL,
    })
    stores = (data.get("body", {}).get("content", {})
                  .get("pickupMessage", {}).get("stores", [])) or []
    out = []
    for s in stores:
        pa = (s.get("partsAvailability") or {}).get(APPLE_PART, {})
        out.append({
            "id": f"apple:{s.get('storeNumber', '')}",
            "name": f"Apple {s.get('storeName', '?')}",
            "city": s.get("city", ""),
            "miles": to_miles(s.get("storedistance")),
            "available": pa.get("pickupDisplay") == "available",
            "quote": (pa.get("messageTypes", {}).get("regular", {}).get("storePickupQuote")
                      or pa.get("pickupSearchQuote") or ""),
            "url": APPLE_URL,
        })
    return out


def check_bestbuy():
    # Official API: lists only stores that have the SKU in stock.
    qs = urllib.parse.urlencode({"postalCode": ZIP, "apiKey": BESTBUY_API_KEY})
    data = get_json(f"https://api.bestbuy.com/v1/products/{BESTBUY_SKU}/stores.json?{qs}")
    out = []
    for s in data.get("stores", []) or []:
        out.append({
            "id": f"bestbuy:{s.get('storeID', '')}",
            "name": f"Best Buy {s.get('name', '?')}",
            "city": s.get("city", ""),
            "miles": to_miles(s.get("distance")),
            "available": True,
            "quote": "Low stock" if s.get("lowStock") else "In stock",
            "url": BESTBUY_URL,
        })
    return out


SOURCES = [("apple", check_apple)]
if BESTBUY_API_KEY:
    SOURCES.append(("bestbuy", check_bestbuy))


def notify(title, message, click=APPLE_URL, priority="urgent", tags="iphone,rotating_light"):
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


def check_once(alerted, failed):
    """Run every source; alert on newly in-stock stores. Returns new alerted set.
    Adds names of sources that errored to `failed`."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    in_stock, ok_prefixes = {}, []
    for name, fn in SOURCES:
        try:
            stores = [s for s in fn() if s["miles"] <= MAX_MILES]
        except Exception as e:
            print(f"[{stamp}] {name}: {e}", file=sys.stderr)
            failed.add(name)
            continue
        ok_prefixes.append(f"{name}:")
        if not any(s["available"] for s in stores):
            print(f"[{stamp}] {name}: none in stock within {MAX_MILES:.0f} mi "
                  f"({len(stores)} stores checked)")
        for s in sorted(stores, key=lambda x: x["miles"]):
            mark = "IN STOCK" if s["available"] else "-"
            print(f"[{stamp}] {s['miles']:5.1f} mi  {s['name']:<28} {mark:<9} {s['quote']}")
            if s["available"]:
                in_stock[s["id"]] = s

    new = [s for sid, s in in_stock.items() if sid not in alerted]
    if new:
        new.sort(key=lambda x: x["miles"])
        lines = [f"{s['name']} ({s['city']}, {s['miles']:.0f} mi): {s['quote'] or 'available'}"
                 for s in new]
        notify(f"{PRODUCT} IN STOCK", "\n".join(lines) + "\nTap to reserve pickup.",
               click=new[0]["url"])
    # Keep memory for sources that errored this round; forget sold-out stores
    # from sources that answered, so a restock alerts again.
    kept = {sid for sid in alerted if not any(sid.startswith(p) for p in ok_prefixes)}
    return kept | set(in_stock)


def main():
    if not NTFY_TOPIC:
        print("ERROR: NTFY_TOPIC secret is not set, so alerts can't reach your phone.",
              file=sys.stderr)
    if os.environ.get("TEST_NOTIFY", "").lower() == "true":
        if not NTFY_TOPIC:
            return 1
        names = ", ".join(n for n, _ in SOURCES)
        notify("Tracker test", f"Notifications work. Watching {PRODUCT} near {ZIP} at: {names}.",
               priority="default", tags="white_check_mark")
        return 0
    if not BESTBUY_API_KEY:
        print("BESTBUY_API_KEY not set; checking Apple only.")

    alerted = load_state()
    deadline = time.time() + LOOP_SECONDS
    ever_ok = {n: False for n, _ in SOURCES}
    while True:
        failed = set()
        alerted = check_once(alerted, failed)
        save_state(alerted)
        for n in ever_ok:
            ever_ok[n] |= n not in failed
        if time.time() + INTERVAL > deadline:
            break
        time.sleep(INTERVAL + random.uniform(-5, 5))

    if not NTFY_TOPIC:
        return 1  # fail so GitHub emails you; a tracker that can't alert is broken
    broken = [n for n, ok in ever_ok.items() if not ok]
    if broken:
        # Fail the run so GitHub emails you that part of the tracker is broken.
        print(f"Source(s) failed every check this run: {', '.join(broken)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
