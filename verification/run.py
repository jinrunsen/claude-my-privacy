#!/usr/bin/env python3
"""Exercise the real CLI with synthetic model streams and all network denied."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from synthetic_config import write_config


ROOT = Path(__file__).resolve().parent
PRODUCTION = ROOT.parent / "plugins" / "my-privacy"
SANDBOX = Path("/usr/bin/sandbox-exec")
RAW = ("Cedarbyte", "audit.person@example.invalid", "+1 202-555-0199")
PROMPT = (
    "Run offline synthetic audit: employer Cedarbyte, "
    "email audit.person@example.invalid, phone +1 202-555-0199."
)


def analyze(workspace):
    audit = json.loads((workspace / "audit.json").read_text())
    output = (workspace / "output.txt").read_text()
    transcript = max(
        (workspace / "config" / "projects").rglob("*.jsonl"),
        key=lambda path: path.stat().st_mtime,
    )
    rows = [json.loads(line) for line in transcript.read_text().splitlines() if line]
    message_rows = [row for row in rows if isinstance(row.get("message"), dict)]
    content = "\n".join(
        json.dumps(row["message"].get("content"), ensure_ascii=False)
        for row in message_rows
    )
    metadata = "\n".join(
        json.dumps({k: v for k, v in row.items() if k != "message"}, ensure_ascii=False)
        for row in message_rows
    )
    captures = audit.get("captured", [])
    checks = {
        "completedFiveSyntheticSteps": audit.get("completed") is True and len(captures) == 5,
        "allModelConversationViewsSanitized": bool(captures) and all(
            row.get("array") is True and row.get("rawVisible") is False
            and row.get("hasCompanyAlias") is True
            and row.get("hasEmailToken") is True
            and row.get("hasPhoneToken") is True
            for row in captures
        ),
        "readRan": audit.get("sawRead") is True,
        "writeRan": audit.get("sawWrite") is True,
        "editRan": audit.get("sawEdit") is True,
        "localCompanyRestored": RAW[0] in output,
        "localEmailRestored": RAW[1] in output,
        "localPhoneRestored": RAW[2] in output,
        "localEditSucceeded": "Version: after" in output,
        "localOutputHasNoTokens": "<PII_" not in output,
        "savedMessageContentsSanitized": len(message_rows) >= 10
        and not any(value in content for value in RAW),
        "savedMessageContentsHaveAliasesAndTokens": all(
            marker in content for marker in ("Harborwave", "<PII_EMAIL_", "<PII_PHONE_")
        ),
    }
    observations = {
        "rawSyntheticPiiInQueue": any(
            row.get("type") == "queue-operation"
            and any(value in json.dumps(row) for value in RAW)
            for row in rows
        ),
        "rawSyntheticPiiInOtherMessageMetadata": any(value in metadata for value in RAW),
        "absoluteCwdInMessageMetadata": any(
            isinstance(row.get("cwd"), str) and row["cwd"].startswith("/")
            for row in message_rows
        ),
    }
    return checks, observations, transcript.stem


def main():
    os.umask(0o077)
    cli = shutil.which("claude")
    report = {
        "prerequisites": {
            "macOS": sys.platform == "darwin",
            "sandboxAvailable": SANDBOX.is_file(),
            "claudeAvailable": cli is not None,
            "productionPluginAvailable": (PRODUCTION / ".claude-plugin/plugin.json").is_file(),
        },
        "execution": {"freshRunSucceeded": False, "resumeRunSucceeded": False},
        "passed": False,
    }
    if all(report["prerequisites"].values()):
        try:
            # No user's auth, settings, transcripts, or environment credentials are copied.
            with tempfile.TemporaryDirectory(prefix="claude-my-privacy-e2e-") as directory:
                workspace = Path(directory)
                config = workspace / "config"
                config.mkdir(mode=0o700)
                mock = workspace / "mock-model"
                shutil.copytree(ROOT / "mock-model", mock)
                shutil.copyfile(ROOT / "fixtures/input.txt", workspace / "input.txt")
                (mock / "hooks/paths.js").write_text("\n".join(
                    f"export const {key} = {json.dumps(str(workspace / filename))};"
                    for key, filename in (
                        ("INPUT", "input.txt"), ("OUTPUT", "output.txt"), ("REPORT", "audit.json")
                    )
                ) + "\n")
                # HOME remains the actual user's HOME; CLAUDE_CONFIG_DIR isolates state.
                permitted = ("PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "TERM")
                env = {key: os.environ[key] for key in permitted if key in os.environ}
                env.update({
                    "CLAUDE_MY_PRIVACY_CONFIG": str(write_config(workspace)),
                    "CLAUDE_CONFIG_DIR": str(config),
                    "ANTHROPIC_API_KEY": "offline-audit-placeholder",
                    "DISABLE_TELEMETRY": "1",
                    "DISABLE_ERROR_REPORTING": "1",
                    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                })
                command = [
                    str(SANDBOX), "-p", "(version 1)(allow default)(deny network*)", cli,
                    "--setting-sources", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                    "--settings", '{"prependPlugins":["my-privacy@inline"]}',
                    "--permission-mode", "acceptEdits", "--tools", "Read,Write,Edit",
                    "--plugin-dir", str(PRODUCTION), "--plugin-dir", str(mock),
                ]
                fresh = subprocess.run(
                    command + ["-p", PROMPT], cwd=workspace, env=env,
                    capture_output=True, text=True, timeout=55, check=False,
                )
                # Child output is never printed or saved; only derived booleans leave the temp dir.
                report["execution"]["freshRunSucceeded"] = fresh.returncode == 0
                report["checks"], report["observations"], session_id = analyze(workspace)
                resumed = subprocess.run(
                    command + ["--resume", session_id, "-p", "Continue offline audit."],
                    cwd=workspace, env=env, capture_output=True, text=True, timeout=55, check=False,
                )
                resumed_output = resumed.stdout + resumed.stderr
                report["execution"]["resumeRunSucceeded"] = resumed.returncode == 0
                report["checks"]["resumeBlocked"] = "Privacy filtering requires a new session" in resumed_output
                report["checks"]["mockModelDidNotRunOnResume"] = "OFFLINE_MY_PRIVACY_AUDIT_COMPLETE" not in resumed_output
                report["passed"] = all(report["execution"].values()) and all(report["checks"].values())
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            # Avoid leaking exception text, transcript excerpts, or paths through an error report.
            report["execution"]["failedBeforeCompleteReport"] = True
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence/latest-summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
