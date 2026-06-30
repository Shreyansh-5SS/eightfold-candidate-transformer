import logging
import re
from datetime import datetime, timezone
from typing import List, Optional

import requests

from src.models import RawRecord
from src.sources.base import SourceParser

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
TIMEOUT_SECONDS = 5


def _extract_username(url_or_username: str) -> Optional[str]:
    url_or_username = (url_or_username or "").strip()
    if not url_or_username:
        return None
    match = re.match(r"^https?://(www\.)?github\.com/([A-Za-z0-9_-]+)/?$", url_or_username)
    if match:
        return match.group(2)
    if re.match(r"^[A-Za-z0-9_-]+$", url_or_username):
        return url_or_username
    return None


class GitHubSource(SourceParser):
    SOURCE_NAME = "github"

    def parse(self, url_or_username: str) -> List[RawRecord]:
        username = _extract_username(url_or_username)
        if not username:
            logger.warning(f"[github] could not extract username from: {url_or_username!r}")
            return []

        # Note: unauthenticated requests are rate-limited to ~60/hr by GitHub.
        # A token (passed via Authorization header) would raise this if needed later.
        try:
            user_resp = requests.get(f"{GITHUB_API_BASE}/users/{username}", timeout=TIMEOUT_SECONDS)
        except requests.RequestException as e:
            logger.warning(f"[github] network error fetching user {username}: {e}")
            return []

        if user_resp.status_code == 404:
            logger.warning(f"[github] user not found: {username}")
            return []
        if user_resp.status_code == 403:
            logger.warning(f"[github] rate-limited fetching user {username} (unauthenticated limit is low)")
            return []
        if user_resp.status_code != 200:
            logger.warning(f"[github] unexpected status {user_resp.status_code} for user {username}")
            return []

        user_json = user_resp.json()

        languages = []
        try:
            repos_resp = requests.get(
                f"{GITHUB_API_BASE}/users/{username}/repos",
                params={"per_page": 100},
                timeout=TIMEOUT_SECONDS,
            )
            if repos_resp.status_code == 200:
                repos_json = repos_resp.json()
                languages = sorted({
                    r["language"] for r in repos_json
                    if isinstance(r, dict) and r.get("language")
                })
            else:
                logger.warning(f"[github] could not fetch repos for {username}: status {repos_resp.status_code}")
        except requests.RequestException as e:
            logger.warning(f"[github] network error fetching repos for {username}: {e}")
            # languages stays [] — we still return the user profile data we got

        data = {
            "full_name": user_json.get("name") or username,
            "headline": user_json.get("bio"),
            "github_url": user_json.get("html_url") or f"https://github.com/{username}",
            "languages": languages,
            "location_raw": user_json.get("location"),
        }

        record = RawRecord(
            source=self.SOURCE_NAME,
            candidate_key=None,  # GitHub has no reliable email; matched on name in merge step
            data=data,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(f"[github] parsed profile for {username}")
        return [record]