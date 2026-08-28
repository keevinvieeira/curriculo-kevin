"""
CLI tool to run the Graph-Driven Job Pipeline on one or all jobs.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.job_pipeline import JobPipeline, process_single_job
from job_store import JOBS_DIR, job_path, slugify, read_json


def main():
    parser = argparse.ArgumentParser(description="Process and activate jobs via Graph Pipeline.")
    parser.add_argument("target", nargs="?", help="Job slug or path to job JSON file")
    parser.add_argument("--batch", action="store_true", help="Process all jobs in data/jobs/")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
    parser.add_argument("--no-activate", action="store_true", help="Skip Streamlit activation")
    args = parser.parse_args()

    pipeline = JobPipeline()

    if args.batch:
        job_files = [f for f in JOBS_DIR.glob("*.json") if f.name != "active.json" and not f.name.endswith("-context-pack.json") and not f.name.endswith("-graph-work.json")]
        print(f"Processing {len(job_files)} jobs in batch...")
        for f in sorted(job_files):
            try:
                print(f"\n--> Processing: {f.name}")
                data = read_json(f)
                res = pipeline.process_job_artifact(
                    data,
                    generate_pdfs=not args.no_pdf,
                    auto_activate=not args.no_activate,
                )
                print(f"    [SUCCESS] {res['slug']} (Score: {res.get('fit_score', 'N/A')}%) - PDFs: {len(res['generated_pdfs'])}")
            except Exception as e:
                print(f"    [ERROR] Failed {f.name}: {e}")
        return

    if not args.target:
        print("Please provide a job slug or path, or use --batch.")
        return

    target_path = Path(args.target)
    if not target_path.exists():
        target_path = job_path(args.target)

    if not target_path.exists():
        print(f"Error: Job file not found at '{target_path}'")
        sys.exit(1)

    print(f"Processing job: {target_path.name}")
    result = process_single_job(target_path)
    print(f"\n[COMPLETED] Job: {result['slug']}")
    print(f"  Artifact: {result['artifact_path']}")
    print(f"  Fit Score: {result.get('fit_score', 'N/A')}%")
    print(f"  PDFs Generated:")
    for pdf in result['generated_pdfs']:
        print(f"    - {pdf}")


if __name__ == "__main__":
    main()
