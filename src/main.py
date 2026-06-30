import argparse
import json
import logging
import os
from typing import List, Optional

from src.models import RawRecord
from src.sources.csv_source import RecruiterCSVSource
from src.sources.github_source import GitHubSource
from src.pipeline.merge import merge_records
from src.pipeline.project import project_candidate, MissingRequiredFieldError
from src.pipeline.validate import validate_output

logger = logging.getLogger("main")


def configure_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def collect_raw_records(args) -> List[RawRecord]:
    raw_records: List[RawRecord] = []

    if args.csv:
        csv_records = RecruiterCSVSource().parse(args.csv)
        logger.info(f"Loaded {len(csv_records)} records from CSV: {args.csv}")
        raw_records.extend(csv_records)

    if args.github_urls:
        if not os.path.isfile(args.github_urls):
            logger.error(f"GitHub URLs file not found: {args.github_urls}")
        else:
            with open(args.github_urls, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip()]
            github_source = GitHubSource()
            for url in urls:
                records = github_source.parse(url)
                raw_records.extend(records)
            logger.info(f"Loaded {len(raw_records)} total records after GitHub URLs from {args.github_urls}")

    return raw_records


def load_config(config_path: Optional[str]) -> dict:
    path = config_path or os.path.join("configs", "default_config.json")
    if not os.path.isfile(path):
        logger.error(f"Config file not found: {path} — falling back to default_config.json")
        path = os.path.join("configs", "default_config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_pipeline(args) -> List[dict]:
    raw_records = collect_raw_records(args)
    if not raw_records:
        logger.warning("No raw records collected from any source — output will be empty.")
        return []

    config = load_config(args.config)
    candidates = merge_records(raw_records, field_priority=config.get("field_priority"))

    valid_outputs = []
    failed_count = 0

    for candidate in candidates:
        try:
            projected = project_candidate(candidate, config)
        except MissingRequiredFieldError as e:
            logger.warning(f"Skipping candidate {candidate.candidate_id} ({candidate.full_name}): {e}")
            failed_count += 1
            continue

        is_valid, errors = validate_output(projected, config)
        if not is_valid:
            logger.warning(
                f"Candidate {candidate.candidate_id} ({candidate.full_name}) failed validation: {errors}"
            )
            failed_count += 1
            continue

        valid_outputs.append(projected)

    logger.info(
        f"Processed {len(candidates)} candidates from {len(raw_records)} raw records, "
        f"{len(valid_outputs)} valid, {failed_count} failed validation."
    )
    return valid_outputs


def main():
    parser = argparse.ArgumentParser(description="Multi-source candidate data transformer")
    parser.add_argument("--csv", help="Path to recruiter CSV file")
    parser.add_argument("--github-urls", help="Path to a text file with one GitHub URL per line")
    parser.add_argument("--config", help="Path to runtime projection config JSON (default: configs/default_config.json)")
    parser.add_argument("--output", required=True, help="Path to write the resulting JSON array")
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args()
    configure_logging(args.log_level)

    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    results = run_pipeline(args)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"Wrote {len(results)} candidate records to {args.output}")


if __name__ == "__main__":
    main()