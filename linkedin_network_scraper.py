"""LinkedIn network scraper.

Logs into LinkedIn and exports connections with best-effort current employer parsing.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from typing import Iterable, List

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


LOGGER = logging.getLogger("linkedin_scraper")
EMPLOYER_SPLIT_RE = re.compile(r"\s+at\s+|\s+@\s+", re.IGNORECASE)


@dataclass(frozen=True)
class Connection:
    name: str
    headline: str
    employer: str | None


def parse_employer(headline: str) -> str | None:
    if not headline:
        return None
    parts = EMPLOYER_SPLIT_RE.split(headline, maxsplit=1)
    if len(parts) == 2:
        employer = parts[1].strip()
        return employer or None
    return None


def ensure_credentials(username: str | None, password: str | None) -> tuple[str, str]:
    if not username or not password:
        raise ValueError(
            "Missing LinkedIn credentials. Provide LINKEDIN_USERNAME and LINKEDIN_PASSWORD."
        )
    return username, password


def wait_for_login_redirect(page) -> None:
    LOGGER.info("Waiting for LinkedIn redirect after login...")
    page.wait_for_url(re.compile(r"linkedin\.com/(feed|checkpoint|mynetwork)"), timeout=60000)


def login(page, username: str, password: str) -> None:
    LOGGER.info("Navigating to LinkedIn login page")
    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    page.fill("#username", username)
    page.fill("#password", password)
    LOGGER.info("Submitting login form")
    page.click("button[type='submit']")
    wait_for_login_redirect(page)
    LOGGER.info("Login flow completed")


def open_connections_page(page) -> None:
    LOGGER.info("Navigating to connections page")
    page.goto("https://www.linkedin.com/mynetwork/invite-connect/connections/", wait_until="domcontentloaded")
    page.wait_for_selector(".mn-connection-card", timeout=60000)


def load_all_connections(page) -> None:
    LOGGER.info("Scrolling connections page to load all entries")
    last_height = 0
    stable_rounds = 0
    while stable_rounds < 3:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)
        current_height = page.evaluate("document.body.scrollHeight")
        if current_height == last_height:
            stable_rounds += 1
        else:
            stable_rounds = 0
            last_height = current_height
        LOGGER.debug("Scroll height: %s (stable %s)", current_height, stable_rounds)


def scrape_connections(page) -> List[Connection]:
    LOGGER.info("Scraping connection cards")
    cards = page.query_selector_all(".mn-connection-card")
    LOGGER.info("Found %d connection cards", len(cards))
    connections: List[Connection] = []
    for card in cards:
        name = card.query_selector(".mn-connection-card__name")
        headline = card.query_selector(".mn-connection-card__occupation")
        name_text = name.inner_text().strip() if name else ""
        headline_text = headline.inner_text().strip() if headline else ""
        if not name_text:
            LOGGER.debug("Skipping card with no name")
            continue
        employer = parse_employer(headline_text)
        connections.append(Connection(name=name_text, headline=headline_text, employer=employer))
    return connections


def save_connections(connections: Iterable[Connection], output_path: str) -> None:
    payload = [connection.__dict__ for connection in connections]
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    LOGGER.info("Saved %d connections to %s", len(payload), output_path)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape LinkedIn network connections.")
    parser.add_argument("--output", default="connections.json", help="Output JSON path")
    parser.add_argument("--headless", default="true", choices=["true", "false"], help="Run browser headless")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    username, password = ensure_credentials(
        os.getenv("LINKEDIN_USERNAME"), os.getenv("LINKEDIN_PASSWORD")
    )
    headless = args.headless.lower() == "true"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()

            login(page, username, password)
            open_connections_page(page)
            load_all_connections(page)
            connections = scrape_connections(page)
            save_connections(connections, args.output)

            context.close()
            browser.close()
    except PlaywrightTimeoutError as exc:
        LOGGER.error("Timed out while interacting with LinkedIn: %s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - top-level safety
        LOGGER.exception("Unexpected error: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
