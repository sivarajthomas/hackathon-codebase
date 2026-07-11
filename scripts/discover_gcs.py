"""Read-only discovery for the rate card GCS bucket.

Lists objects under the configured ``GCS_BUCKET`` / ``GCS_PREFIX``, groups them
by file extension (count + total size), and prints a short text sample of one
JSON and one CSV object so the rate card parsing/field names can be tuned.

This script performs NO writes. Run it once with your credentials configured:

    # .env at the repo root (or real environment variables) must define:
    #   GOOGLE_APPLICATION_CREDENTIALS, GCP_PROJECT, GCS_BUCKET  (GCS_PREFIX optional)
    python scripts/discover_gcs.py
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional convenience
    load_dotenv = None

_SAMPLE_BYTES = 800


def _load_env() -> None:
    if load_dotenv is not None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(os.path.join(repo_root, ".env"))


def _ext(name: str) -> str:
    _, dot, ext = name.rpartition(".")
    return f".{ext.lower()}" if dot else "(none)"


def main() -> int:
    _load_env()
    project = os.environ.get("GCP_PROJECT")
    bucket = os.environ.get("GCS_BUCKET")
    prefix = os.environ.get("GCS_PREFIX", "") or None
    if not bucket:
        print("ERROR: GCS_BUCKET is not set.", file=sys.stderr)
        return 2

    from google.cloud import storage

    client = storage.Client(project=project)
    blobs = list(client.list_blobs(bucket, prefix=prefix))

    print(f"== Bucket gs://{bucket}/{prefix or ''} : {len(blobs)} object(s) ==")
    counts: dict[str, int] = defaultdict(int)
    sizes: dict[str, int] = defaultdict(int)
    first_by_ext: dict[str, storage.Blob] = {}
    for blob in blobs:
        ext = _ext(blob.name)
        counts[ext] += 1
        sizes[ext] += blob.size or 0
        first_by_ext.setdefault(ext, blob)

    print("\n== By extension ==")
    for ext in sorted(counts):
        print(f"  {ext:<10} count={counts[ext]:<6} total_bytes={sizes[ext]}")

    for ext in (".json", ".csv"):
        blob = first_by_ext.get(ext)
        if blob is None:
            continue
        print(f"\n== Sample of first {ext} object: {blob.name} ==")
        try:
            data = blob.download_as_bytes(end=_SAMPLE_BYTES - 1)
            print(data.decode("utf-8-sig", errors="replace"))
        except Exception as exc:  # pragma: no cover - depends on live data
            print(f"  (could not read sample: {exc})")

    print(
        "\nNext: confirm the JSON keys / CSV headers so the rate card "
        "field names (card_id, customer_id, entries, ...) can be aligned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
