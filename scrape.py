import csv
import os
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL = "https://ungvetenskapssport.se/event/robotiklager-norrkoping-2026/"
OUT_CSV = "data/visitor_counter.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

def extract_counter(html: str) -> int | None:
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one("div.wpem-viewed-event")
    if not el:
        return None

    # Example text often becomes: "205 205 people viewed this event."
    text = el.get_text(" ", strip=True)
    m = re.search(r"\b(\d+)\b", text)
    return int(m.group(1)) if m else None

def append_csv(timestamp_utc: str, value: int | None):
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    new_file = not os.path.exists(OUT_CSV)

    with open(OUT_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp_utc", "value", "url"])
        w.writerow([timestamp_utc, value, URL])

def main():
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()

    value = extract_counter(r.text)
    append_csv(ts, value)

    print(f"{ts} value={value}")

if __name__ == "__main__":
    main()
