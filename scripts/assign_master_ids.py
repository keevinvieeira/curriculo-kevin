"""Assign missing stable IDs in master_resume.json (idempotent) and validate them.

    python -m scripts.assign_master_ids            # assign + validate + write
    python -m scripts.assign_master_ids --check    # validate only, exit 1 on error

Run after adding a bullet/experience by hand. Existing IDs are never changed.
"""

from __future__ import annotations

import json
import sys

from job_store import ROOT
from resume_ids import assign_ids, validate_ids

MASTER_PATH = ROOT / "master_resume.json"


def main(argv: list[str]) -> int:
    with MASTER_PATH.open(encoding="utf-8") as file:
        master = json.load(file)

    created = [] if "--check" in argv else assign_ids(master)
    errors = validate_ids(master)
    if errors:
        print("\n".join(errors))
        return 1
    if created:
        with MASTER_PATH.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(master, file, ensure_ascii=False, indent=2)
        print(f"{len(created)} IDs atribuidos: {', '.join(created)}")
    else:
        print("master_resume.json ok — nenhum ID novo necessario.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
