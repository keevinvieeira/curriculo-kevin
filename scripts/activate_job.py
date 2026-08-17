"""Activate a versioned job artifact in the Streamlit compatibility files."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from job_store import activate_job, clone_job, create_from_active, load_active_job, read_json, validate_job


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id", nargs="?")
    parser.add_argument("--migrate-active", action="store_true")
    parser.add_argument("--clone-from")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    if args.migrate_active:
        job = create_from_active(args.job_id or "active-job")
        print(f"Created {job['id']}")
        return

    if args.clone_from:
        if not args.job_id:
            raise SystemExit("job_id is required with --clone-from")
        job = clone_job(args.clone_from, args.job_id)
        print(f"Created {job['id']} from {args.clone_from}")
        return

    job = load_active_job() if args.job_id is None else None
    if args.job_id:
        master = read_json(ROOT / "master_resume.json")
        job = activate_job(args.job_id, master)
        print(f"Activated {job['id']}")

    if args.validate:
        if not job:
            raise SystemExit("No active job artifact")
        errors = validate_job(job, read_json(ROOT / "master_resume.json"))
        if errors:
            raise SystemExit("\n".join(errors))
        print(f"Validated {job['id']}")


if __name__ == "__main__":
    main()
