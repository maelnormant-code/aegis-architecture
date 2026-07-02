#!/usr/bin/env python3
"""aegis-doc-forwarder.py — Documentation Request Forwarder (runs in sys-copilot).

Watches /var/lib/aegis/requested_documentation.txt for new entries appended
by Heimdall's request_documentation() tool. For each new entry, it forwards
a structured JSON request to Dom0 via the aegis.RequestDocBuild qrexec RPC,
which triggers sys-knowledge-builder to fetch the documentation, rebuild the
knowledge index, and auto-deploy it to sys-knowledge.

Design:
  - Polls file mtime every 10 seconds (inotify not required)
  - Persists file offset to survive restarts
  - Rate-limits to 1 forwarded request per 60 seconds
  - SIGTERM handler for clean systemd shutdown
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time

# ── Configuration ──────────────────────────────────────────
WATCH_FILE    = "/var/lib/aegis/requested_documentation.txt"
OFFSET_FILE   = "/var/lib/aegis/doc-forwarder.offset"
LOG_FILE      = "/var/log/aegis-doc-forwarder.log"
POLL_INTERVAL = 10      # seconds between file checks
RATE_LIMIT    = 60      # minimum seconds between forwarded requests
RPC_TARGET    = "dom0"
RPC_SERVICE   = "aegis.RequestDocBuild"
RPC_TIMEOUT   = 60      # seconds

# ── Logging ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("aegis-doc-forwarder")

# ── State ──────────────────────────────────────────────────
_running = True
_last_forward_ts = 0.0


def _handle_sigterm(signum, frame):
    global _running
    log.info("Received SIGTERM — shutting down gracefully.")
    _running = False


signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT, _handle_sigterm)


# ── Offset persistence ─────────────────────────────────────

def _load_offset() -> int:
    try:
        with open(OFFSET_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _save_offset(offset: int) -> None:
    tmp = OFFSET_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write(str(offset))
    os.replace(tmp, OFFSET_FILE)


# ── Entry parser ───────────────────────────────────────────

def _parse_entries(text: str) -> list[dict]:
    """Parse request entries from newly-read text block.

    Each entry is delimited by a line starting with '--- ' and contains:
        Topic: <topic>
        Description: <description>
        Timestamp: <ts>
    """
    entries = []
    for block in text.split("--- \n"):
        block = block.strip()
        if not block:
            continue
        entry = {}
        for line in block.splitlines():
            if line.startswith("Topic: "):
                entry["topic"] = line[7:].strip()[:200]
            elif line.startswith("Description: "):
                entry["description"] = line[13:].strip()[:1000]
        if "topic" in entry and "description" in entry:
            entries.append(entry)
    return entries


# ── qrexec forwarding ──────────────────────────────────────

def _forward_request(entry: dict) -> bool:
    """Send entry to Dom0 via aegis.RequestDocBuild qrexec. Returns True on success."""
    payload = json.dumps(entry).encode("utf-8")
    try:
        proc = subprocess.run(
            ["qrexec-client-vm", RPC_TARGET, RPC_SERVICE],
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=RPC_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        log.error("qrexec call to %s timed out after %ds", RPC_SERVICE, RPC_TIMEOUT)
        return False
    except Exception as exc:
        log.error("qrexec call failed: %s", exc)
        return False

    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        log.error("aegis.RequestDocBuild returned exit %d: %s", proc.returncode, stdout)
        return False

    try:
        response = json.loads(stdout)
    except json.JSONDecodeError:
        log.warning("Non-JSON response from Dom0: %r", stdout)
        return proc.returncode == 0

    if response.get("status") == "ok":
        log.info(
            "Documentation rebuild triggered for topic=%r: %s",
            entry["topic"],
            response.get("message", ""),
        )
        return True
    else:
        log.warning(
            "Dom0 rejected doc request for topic=%r: %s",
            entry["topic"],
            response.get("message", "unknown error"),
        )
        return False


# ── Main loop ──────────────────────────────────────────────

def main():
    global _last_forward_ts

    log.info("aegis-doc-forwarder starting. Watching: %s", WATCH_FILE)
    offset = _load_offset()
    log.info("Resuming from file offset %d", offset)

    while _running:
        try:
            if not os.path.exists(WATCH_FILE):
                time.sleep(POLL_INTERVAL)
                continue

            current_size = os.path.getsize(WATCH_FILE)
            if current_size <= offset:
                time.sleep(POLL_INTERVAL)
                continue

            # New content available — read only the new bytes
            with open(WATCH_FILE, "r", errors="replace") as fh:
                fh.seek(offset)
                new_text = fh.read()

            new_offset = offset + len(new_text.encode("utf-8"))
            entries = _parse_entries(new_text)

            if not entries:
                # Advance offset even if no parseable entries
                _save_offset(new_offset)
                offset = new_offset
                time.sleep(POLL_INTERVAL)
                continue

            log.info("Detected %d new documentation request(s).", len(entries))

            for entry in entries:
                # Enforce rate limit
                now = time.monotonic()
                wait = RATE_LIMIT - (now - _last_forward_ts)
                if wait > 0:
                    log.info(
                        "Rate limiting: waiting %.0fs before forwarding topic=%r",
                        wait,
                        entry["topic"],
                    )
                    # Sleep in small increments so SIGTERM is handled promptly
                    deadline = time.monotonic() + wait
                    while _running and time.monotonic() < deadline:
                        time.sleep(1)
                    if not _running:
                        break

                success = _forward_request(entry)
                if success:
                    _last_forward_ts = time.monotonic()

            _save_offset(new_offset)
            offset = new_offset

        except Exception as exc:
            log.exception("Unexpected error in forwarder loop: %s", exc)

        time.sleep(POLL_INTERVAL)

    log.info("aegis-doc-forwarder stopped.")


if __name__ == "__main__":
    main()
