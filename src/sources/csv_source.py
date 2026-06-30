import csv
import logging
import os
from datetime import datetime, timezone
from typing import List

from src.models import RawRecord
from src.sources.base import SourceParser

logger = logging.getLogger(__name__)

# accepted header variants -> canonical field name
HEADER_MAP = {
    "name": "full_name",
    "full_name": "full_name",
    "email": "email",
    "phone": "phone",
    "current_company": "current_company",
    "company": "current_company",
    "title": "title",
}


class RecruiterCSVSource(SourceParser):
    SOURCE_NAME = "recruiter_csv"

    def parse(self, path: str) -> List[RawRecord]:
        records: List[RawRecord] = []

        if not path or not os.path.isfile(path):
            logger.error(f"[recruiter_csv] file not found: {path}")
            return records

        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    logger.error(f"[recruiter_csv] empty/no header in {path}")
                    return records

                normalized_headers = {
                    h: HEADER_MAP.get(h.strip().lower())
                    for h in reader.fieldnames
                }

                for i, row in enumerate(reader, start=2):  # row 1 = header
                    try:
                        data = {}
                        for raw_header, value in row.items():
                            canon = normalized_headers.get(raw_header)
                            if canon:
                                data[canon] = (value or "").strip() or None

                        name = data.get("full_name")
                        email = data.get("email")

                        if not name and not email:
                            logger.warning(
                                f"[recruiter_csv] row {i} skipped: no name and no email"
                            )
                            continue

                        candidate_key = email.lower().strip() if email else None

                        records.append(
                            RawRecord(
                                source=self.SOURCE_NAME,
                                candidate_key=candidate_key,
                                data=data,
                                fetched_at=datetime.now(timezone.utc).isoformat(),
                            )
                        )
                    except Exception as e:
                        logger.warning(f"[recruiter_csv] row {i} skipped: {e}")
                        continue

        except Exception as e:
            logger.error(f"[recruiter_csv] failed to read {path}: {e}")
            return []

        logger.info(f"[recruiter_csv] parsed {len(records)} valid rows from {path}")
        return records