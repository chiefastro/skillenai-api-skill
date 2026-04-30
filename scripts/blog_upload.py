"""Upload a cover image for a Skillenai blog post.

Two-step flow that matches what the dashboard editor does:

    1. POST /content/uploads/presign — backend hands back a one-shot presigned
       PUT URL plus the public URL where the bytes will be served.
    2. PUT the bytes to the presigned URL.

The script accepts either a local file path OR an https URL it should fetch
first. The API key only ever exists inside this script's process (same
isolation contract as scripts/api.py) — it is not echoed to stdout, not
passed via curl argv, and not written to the conversation transcript.

Usage:
    blog_upload.py /local/path/cover.jpg
    blog_upload.py https://example.com/photo.jpg

On success, the public URL is the only thing written to stdout. Pipe it
directly into your `cover_image_url` field.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


DEFAULT_APP_URL = "https://app.skillenai.com/api/backend"
MAX_BYTES = 10 * 1024 * 1024  # backend caps at 10 MB
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def load_credentials() -> tuple[str, str]:
    """Resolve API key + app base URL with the same precedence as scripts/api.py."""
    if not os.environ.get("API_KEY"):
        load_dotenv(Path.home() / ".skillenai" / ".env")
    if not os.environ.get("API_KEY"):
        plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
        if plugin_root:
            load_dotenv(Path(plugin_root) / ".env")
    if not os.environ.get("API_KEY"):
        load_dotenv()

    key = os.environ.get("API_KEY", "")
    if not key:
        sys.stderr.write(
            "No API key found. Run `/skillenai:api setup` to authorize.\n"
        )
        sys.exit(2)

    app_url = os.environ.get("APP_URL", DEFAULT_APP_URL).rstrip("/")
    return key, app_url


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload a cover image for a Skillenai blog post.",
    )
    parser.add_argument(
        "source",
        help="Local file path or https URL to fetch and upload.",
    )
    parser.add_argument(
        "--filename",
        default=None,
        help="Override the filename sent to the backend (defaults to basename of source).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Request timeout in seconds for each step (default: 60).",
    )
    return parser.parse_args(argv)


def is_url(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"}


def fetch_to_temp(url: str, timeout: float) -> Path:
    """Stream the URL to a tempfile and return the path. Bounded by MAX_BYTES."""
    resp = requests.get(url, stream=True, timeout=timeout)
    if resp.status_code >= 400:
        sys.stderr.write(f"Source URL returned {resp.status_code}\n")
        sys.exit(3)

    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in ALLOWED_EXT:
        suffix = ".jpg"  # best guess; backend re-validates content_type anyway

    tmp = tempfile.NamedTemporaryFile(prefix="skn-cover-", suffix=suffix, delete=False)
    written = 0
    try:
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            written += len(chunk)
            if written > MAX_BYTES:
                sys.stderr.write(f"Source exceeds {MAX_BYTES} bytes; refusing to upload.\n")
                tmp.close()
                Path(tmp.name).unlink(missing_ok=True)
                sys.exit(3)
            tmp.write(chunk)
    finally:
        tmp.close()
    return Path(tmp.name)


def detect_content_type(path: Path) -> str:
    ctype, _ = mimetypes.guess_type(path.name)
    if ctype is None:
        # Fall back on extension; backend revalidates.
        ext = path.suffix.lower()
        ctype = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
        }.get(ext, "application/octet-stream")
    return ctype


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    key, app_url = load_credentials()

    fetched_temp: Path | None = None
    try:
        if is_url(args.source):
            local = fetch_to_temp(args.source, args.timeout)
            fetched_temp = local
        else:
            local = Path(args.source).expanduser()
            if not local.exists():
                sys.stderr.write(f"File not found: {local}\n")
                return 2

        size = local.stat().st_size
        if size > MAX_BYTES:
            sys.stderr.write(f"File exceeds {MAX_BYTES} bytes ({size}); refusing to upload.\n")
            return 3
        if size == 0:
            sys.stderr.write("File is empty.\n")
            return 3

        filename = args.filename or local.name
        if Path(filename).suffix.lower() not in ALLOWED_EXT:
            sys.stderr.write(
                f"Unsupported extension {Path(filename).suffix!r}; "
                f"allowed: {sorted(ALLOWED_EXT)}\n"
            )
            return 3

        content_type = detect_content_type(local)

        # Step 1: presign
        presign_resp = requests.post(
            f"{app_url}/content/uploads/presign",
            headers={"X-API-Key": key, "Content-Type": "application/json"},
            json={
                "filename": filename,
                "content_type": content_type,
                "content_length": size,
            },
            timeout=args.timeout,
        )
        if presign_resp.status_code >= 400:
            sys.stderr.write(
                f"Presign failed ({presign_resp.status_code}): {presign_resp.text}\n"
            )
            return 1
        presign = presign_resp.json()
        upload_url = presign["upload_url"]
        public_url = presign["public_url"]

        # Step 2: PUT the bytes. Stream from disk so memory usage stays bounded.
        with local.open("rb") as fh:
            put_resp = requests.put(
                upload_url,
                data=fh,
                headers={"Content-Type": content_type},
                timeout=args.timeout,
            )
        if put_resp.status_code >= 400:
            sys.stderr.write(
                f"PUT failed ({put_resp.status_code}): {put_resp.text}\n"
            )
            return 1

        sys.stdout.write(public_url + "\n")
        return 0
    finally:
        if fetched_temp is not None:
            fetched_temp.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
