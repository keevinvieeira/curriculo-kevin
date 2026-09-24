"""One-off (idempotent) migration: add status_history to every applications.json row.

    python -m scripts.migrate_applications_history          # write
    python -m scripts.migrate_applications_history --dry    # print what would change

Existing fields are kept untouched; `status_history` is inserted right after `status`.
Rows that already have a history are skipped.
"""

from __future__ import annotations

import json
import sys

from application_history import derive_history
from job_store import ROOT

APPLICATIONS_PATH = ROOT / "applications.json"


def migrate(applications: list[dict]) -> int:
    changed = 0
    for n, app in enumerate(applications):
        if "status_history" in app:
            continue
        migrated = {}
        for key, value in app.items():
            migrated[key] = value
            if key == "status":
                migrated["status_history"] = derive_history(app)
        migrated.setdefault("status_history", derive_history(app))
        applications[n] = migrated
        changed += 1
    return changed


def main(argv: list[str]) -> int:
    with APPLICATIONS_PATH.open(encoding="utf-8") as file:
        applications = json.load(file)
    changed = migrate(applications)
    if "--dry" in argv:
        for app in applications:
            print(app["id"], app["company"], json.dumps(app["status_history"], ensure_ascii=False))
        print(f"{changed} registros seriam migrados.")
        return 0
    if changed:
        with APPLICATIONS_PATH.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(applications, file, ensure_ascii=False, indent=2)
    print(f"{changed} registros migrados ({len(applications)} no total).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
