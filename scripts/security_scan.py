from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

FORBIDDEN_SUFFIXES = {".pdf", ".db", ".sqlite", ".sqlite3", ".duckdb"}
TEXT_SUFFIXES = {
    ".cfg",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\bgh[oprsu]_[A-Za-z0-9_]{30,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "nonempty_account_id": re.compile(r"(?m)^\s*ACCOUNT_ID\s*=\s*[\"'][^\"']+[\"']\s*$"),
}


def main() -> int:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
    )
    files = [Path(line) for line in completed.stdout.splitlines() if line.strip()]
    findings: list[dict[str, str]] = []
    scanned = 0
    for path in files:
        if not path.is_file():
            continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append({"path": str(path), "rule": "forbidden_public_artifact"})
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 2_000_000:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append({"path": str(path), "rule": name})
    result = {
        "ok": not findings,
        "files_considered": len(files),
        "text_files_scanned": scanned,
        "findings": findings,
    }
    output = Path("reports/reproduction/security_scan.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
