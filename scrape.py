"""Scrape visitor counter for the event page and append to CSV.

Configuration priority (highest to lowest): CLI args → environment vars → defaults.
This keeps backward compatibility: running `python scrape.py` behaves exactly
like before, but with structured logging and resiliency improvements.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

DEFAULT_URL = "https://ungvetenskapssport.se/event/robotiklager-norrkoping-2026/"
DEFAULT_OUT_CSV = "data/visitor_counter.csv"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)


@dataclass
class ScrapeConfig:
    url: str = DEFAULT_URL
    out_csv: str = DEFAULT_OUT_CSV
    user_agent: str = DEFAULT_USER_AGENT
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    retries: int = 3
    backoff: float = 1.5

    @classmethod
    def from_env_and_args(cls, args: argparse.Namespace) -> "ScrapeConfig":
        def pick(arg_val, env_name: str, default):
            """Choose arg value, else non-empty env, else default."""
            if arg_val not in (None, ""):
                return arg_val
            env_val = os.getenv(env_name)
            if env_val not in (None, ""):
                return env_val
            return default

        def env_float(name: str, default: float) -> float:
            try:
                return float(os.getenv(name, default))
            except ValueError:
                return default

        return cls(
            url=pick(args.url, "SCRAPER_URL", DEFAULT_URL),
            out_csv=pick(args.out, "SCRAPER_OUT_CSV", DEFAULT_OUT_CSV),
            user_agent=pick(args.user_agent, "SCRAPER_USER_AGENT", DEFAULT_USER_AGENT),
            connect_timeout=env_float("SCRAPER_CONNECT_TIMEOUT", args.connect_timeout or 10.0),
            read_timeout=env_float("SCRAPER_READ_TIMEOUT", args.read_timeout or 30.0),
            retries=int(os.getenv("SCRAPER_RETRIES", args.retries or 3)),
            backoff=env_float("SCRAPER_BACKOFF", args.backoff or 1.5),
        )


def configure_logging(verbose: bool = False):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)sZ %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # Force UTC timestamps
    logging.Formatter.converter = time.gmtime


def extract_counter(html: str) -> Optional[int]:
    """Extract visitor counter integer from the event page.

    The selector targets the WordPress Events Manager counter element. The regex
    anchors to the last number in the string to reduce false positives.
    """

    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one("div.wpem-viewed-event")
    if not el:
        return None

    text = el.get_text(" ", strip=True)
    m = re.search(r"(\d+)(?!.*\d)", text)
    return int(m.group(1)) if m else None


def append_csv(out_csv: str, timestamp_utc: str, value: Optional[int], url: str):
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    new_file = not os.path.exists(out_csv)

    with open(out_csv, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp_utc", "value", "url"])
        w.writerow([timestamp_utc, value, url])


def build_session(cfg: ScrapeConfig) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=cfg.retries,
        connect=cfg.retries,
        read=cfg.retries,
        backoff_factor=cfg.backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log visitor counter for the event page")
    parser.add_argument("--url", help="Event URL to scrape")
    parser.add_argument("--out", help="CSV path to append to")
    parser.add_argument("--user-agent", help="User-Agent header")
    parser.add_argument("--connect-timeout", type=float, help="Connect timeout seconds")
    parser.add_argument("--read-timeout", type=float, help="Read timeout seconds")
    parser.add_argument("--retries", type=int, help="Number of retries on failure")
    parser.add_argument("--backoff", type=float, help="Retry backoff factor")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    cfg = ScrapeConfig.from_env_and_args(args)
    configure_logging(args.verbose)

    logging.info(
        "starting scrape",
        extra={
            "url": cfg.url,
            "out_csv": cfg.out_csv,
            "retries": cfg.retries,
            "backoff": cfg.backoff,
            "connect_timeout": cfg.connect_timeout,
            "read_timeout": cfg.read_timeout,
        },
    )

    session = build_session(cfg)
    headers = {
        "User-Agent": cfg.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    }

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        if not cfg.url:
            raise requests.RequestException("Empty URL after config resolution")
        response = session.get(
            cfg.url,
            headers=headers,
            timeout=(cfg.connect_timeout, cfg.read_timeout),
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error("http request failed", exc_info=exc)
        return 1

    value = extract_counter(response.text)
    if value is None:
        logging.warning("counter element not found or unparsable", extra={"url": cfg.url})
    else:
        logging.info("counter extracted", extra={"value": value})

    try:
        append_csv(cfg.out_csv, ts, value, cfg.url)
    except OSError as exc:
        logging.error("failed to write csv", exc_info=exc)
        return 1

    logging.info("scrape complete", extra={"timestamp_utc": ts, "value": value})
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
