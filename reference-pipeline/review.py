#!/usr/bin/env python3
"""AI-assisted security code review.

Scanner findings are the primary input. Bandit and detect-secrets run
over the target, their output is normalized, and each finding is triaged
by a local model into an explained, prioritized review comment that cites
a real file and line.

Freeform review of raw code is the secondary path, behind --no-scanner.

Exit code is always 0 in this phase. Blocking behavior is a later module.
"""

import argparse
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tokenize
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

import requests

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
CONFIG_PATH = HERE / "config.toml"
PROMPT_PATH = REPO_ROOT / "prompts" / "review_system.md"

SEVERITIES = ["critical", "high", "medium", "low", "info"]
CONFIDENCES = ["high", "medium", "low"]

FINDING_PROPERTIES = {
    "severity": {"type": "string", "enum": SEVERITIES},
    "title": {"type": "string"},
    "line_start": {"type": "integer"},
    "line_end": {"type": "integer"},
    "evidence": {"type": "string"},
    "explanation": {"type": "string"},
    "confidence": {"type": "string", "enum": CONFIDENCES},
}

TRIAGE_SCHEMA = {
    "type": "object",
    "properties": FINDING_PROPERTIES,
    "required": list(FINDING_PROPERTIES),
}

SWEEP_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": FINDING_PROPERTIES,
                "required": list(FINDING_PROPERTIES),
            },
        },
        "no_findings_reason": {"type": ["string", "null"]},
    },
    "required": ["findings", "no_findings_reason"],
}

# Module 8 repo-read tool. The model may ask to read named functions or
# classes elsewhere in the repository before it reviews a file. Limits are
# enforced here, not requested in the prompt.
READ_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "requests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "symbol": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["file", "symbol", "reason"],
            },
        },
    },
    "required": ["requests"],
}
READ_MAX_REQUESTS = 4
READ_MAX_LINES = 80


def warn(message):
    """Warnings go to stderr so stdout stays parseable JSON."""
    print("warning: %s" % message, file=sys.stderr)


def fail(message) -> NoReturn:
    """Every failure message names the fix."""
    print("error: %s" % message, file=sys.stderr)
    raise SystemExit(1)


# ---------------------------------------------------------------- config

THINK_LEVELS = ("low", "medium", "high")


def parse_think(value):
    """Normalize the think setting from config.toml or REVIEW_THINK.

    false turns reasoning off and is safe on every model, including models
    that have no reasoning mode. A level (low, medium, high) is for models
    that cannot turn reasoning off, such as gpt-oss. None sends nothing.
    """
    if value is None or isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("false", "off", "no", "0"):
        return False
    if text in ("true", "on", "yes", "1"):
        return True
    if text in THINK_LEVELS:
        return text
    fail(
        "think must be false, true, low, medium, or high, not '%s'. "
        "Fix model.think in config.toml or REVIEW_THINK." % value
    )


def load_config(path=CONFIG_PATH):
    """Read config.toml and apply environment overrides."""
    if not path.is_file():
        fail("config not found at %s. Run setup.sh or setup.ps1 first." % path)
    with path.open("rb") as handle:
        config = tomllib.load(handle)

    model = config.setdefault("model", {})
    review = config.setdefault("review", {})

    model["name"] = os.environ.get("REVIEW_MODEL") or model.get("name")
    model["host"] = (os.environ.get("OLLAMA_HOST") or model.get("host") or "").rstrip("/")

    if not model["name"]:
        fail("no model configured. Set model.name in config.toml or REVIEW_MODEL.")
    if not model["host"]:
        fail("no host configured. Set model.host in config.toml or OLLAMA_HOST.")

    model["think"] = parse_think(os.environ.get("REVIEW_THINK", model.get("think")))

    review.setdefault("max_findings", 25)
    review.setdefault("ignored_rules", [])
    review.setdefault("excluded_paths", [])
    sanitize = os.environ.get("REVIEW_SANITIZE", review.get("sanitize_source", False))
    review["sanitize_source"] = str(sanitize).strip().lower() in ("1", "true", "on", "yes")
    review["audit_log"] = os.environ.get("REVIEW_AUDIT_LOG", review.get("audit_log", ""))
    repo_read = os.environ.get("REVIEW_REPO_READ", review.get("repo_read", False))
    review["repo_read"] = str(repo_read).strip().lower() in ("1", "true", "on", "yes")
    return config


def load_prompts(path=PROMPT_PATH):
    """Split the prompt file on its level-two headings."""
    if not path.is_file():
        fail("prompt file not found at %s." % path)
    text = path.read_text(encoding="utf-8")
    sections = {}
    current = None
    buffer = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                sections[current] = "\n".join(buffer).strip()
            current = line[3:].strip()
            buffer = []
        elif current:
            buffer.append(line)
    if current:
        sections[current] = "\n".join(buffer).strip()

    for required in ("triage", "sweep"):
        if not sections.get(required):
            fail("prompt file %s is missing a '## %s' section." % (path, required))
    return sections


# --------------------------------------------------------------- scanners


def _relative(path):
    """Repo-relative POSIX path. Scanners and SARIF both want this form."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def parse_sarif(document):
    """Normalize a SARIF 2.1.0 document into scanner findings."""
    findings = []
    for run in document.get("runs", []):
        driver = run.get("tool", {}).get("driver", {})
        tool_name = driver.get("name", "sarif")
        rules = {rule.get("id"): rule for rule in driver.get("rules", [])}
        for result in run.get("results", []):
            locations = result.get("locations") or []
            if not locations:
                continue
            physical = locations[0].get("physicalLocation", {})
            uri = physical.get("artifactLocation", {}).get("uri")
            line = physical.get("region", {}).get("startLine")
            if not uri or not line:
                continue
            rule_id = result.get("ruleId", "")
            findings.append(
                {
                    "tool": tool_name,
                    "rule_id": rule_id,
                    "rule_name": rules.get(rule_id, {}).get("name", ""),
                    "file": uri,
                    "line": int(line),
                    "message": result.get("message", {}).get("text", ""),
                }
            )
    return findings


def run_bandit(targets, excluded):
    """Run Bandit and return normalized findings."""
    command = [sys.executable, "-m", "bandit", "-q", "-r", "-f", "sarif"]
    if excluded:
        command += ["-x", ",".join(excluded)]
    # Paths must be repo-relative because the scanner runs from REPO_ROOT,
    # and SARIF then reports repo-relative URIs that match.
    command += [_relative(t) for t in targets]
    completed = subprocess.run(
        command, cwd=REPO_ROOT, capture_output=True, text=True
    )
    if not completed.stdout.strip():
        warn("bandit produced no output. stderr: %s" % completed.stderr.strip()[:300])
        return []
    try:
        return parse_sarif(json.loads(completed.stdout))
    except json.JSONDecodeError:
        warn("bandit output was not valid SARIF, skipping its findings.")
        return []


def run_detect_secrets(targets):
    """Run detect-secrets and return normalized findings.

    Two silent failure modes are handled here. Without --all-files it only
    scans git-tracked files and reports nothing on new work. It also only
    reports paths under the working directory, so everything is made
    repo-relative and the command runs from the repo root.
    """
    command = [sys.executable, "-m", "detect_secrets", "scan", "--all-files"]
    command += [_relative(t) for t in targets]
    completed = subprocess.run(
        command, cwd=REPO_ROOT, capture_output=True, text=True
    )
    if not completed.stdout.strip():
        warn("detect-secrets produced no output. stderr: %s" % completed.stderr.strip()[:300])
        return []
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError:
        warn("detect-secrets output was not valid JSON, skipping its findings.")
        return []

    findings = []
    for filename, items in document.get("results", {}).items():
        for item in items:
            findings.append(
                {
                    "tool": "detect-secrets",
                    "rule_id": item.get("type", "secret"),
                    "rule_name": item.get("type", ""),
                    "file": Path(filename).as_posix(),
                    "line": int(item.get("line_number", 0)),
                    "message": "Possible %s detected." % item.get("type", "secret"),
                }
            )
    return [f for f in findings if f["line"] > 0]


def collect_scanner_findings(targets, config):
    """Run both scanners, drop ignored rules, and merge by file and line."""
    excluded = config["review"]["excluded_paths"]
    ignored = set(config["review"]["ignored_rules"])

    raw = run_bandit(targets, excluded) + run_detect_secrets(targets)
    raw = [f for f in raw if f["rule_id"] not in ignored]
    raw = [
        f
        for f in raw
        if not any(part in f["file"].split("/") for part in excluded)
    ]

    merged = {}
    for finding in raw:
        key = (finding["file"], finding["line"])
        if key in merged:
            existing = merged[key]
            if finding["rule_id"] not in existing["refs"]:
                existing["refs"].append(finding["rule_id"])
            continue
        finding["refs"] = [finding["rule_id"]]
        merged[key] = finding
    return sorted(merged.values(), key=lambda f: (f["file"], f["line"]))


# ------------------------------------------------------------ diff parsing


HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_unified_diff(text):
    """Map each file in a unified diff to the line numbers it adds.

    Only added and context lines advance the new-file counter, which is
    what finding line numbers are measured against.
    """
    changed = {}
    current_file = None
    new_line = 0

    for line in text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path == "/dev/null":
                current_file = None
                continue
            if path.startswith("b/"):
                path = path[2:]
            current_file = path
            changed.setdefault(current_file, set())
            continue

        if line.startswith("@@"):
            match = HUNK_RE.match(line)
            if match:
                new_line = int(match.group(1))
            continue

        if current_file is None:
            continue

        if line.startswith("+"):
            changed[current_file].add(new_line)
            new_line += 1
        elif line.startswith("-"):
            continue
        elif line.startswith(" "):
            new_line += 1

    return changed


def read_staged_diff():
    completed = subprocess.run(
        ["git", "diff", "--cached"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        fail("git diff --cached failed. Are you inside a git repository? %s" % completed.stderr.strip())
    return completed.stdout


# ----------------------------------------------------------------- model


TEST_PATH_MARKERS = ("test", "tests", "conftest", "fixtures", "spec")


def looks_like_test_code(file_path):
    """True when a path is test or fixture code.

    Credentials in test fixtures are a different thing from credentials in
    application code. The model is told this rather than having its answer
    overridden, because a real secret can still be committed to a test file.
    """
    parts = [part.lower() for part in Path(file_path).parts]
    stem = Path(file_path).stem.lower()
    if any(marker in parts for marker in TEST_PATH_MARKERS):
        return True
    return stem.startswith("test_") or stem.endswith("_test") or stem == "conftest"


def build_triage_user(scanner, source):
    """The user message for one scanner finding. Shared so evaluation
    harnesses measure exactly what production sends."""
    context = ""
    if looks_like_test_code(scanner["file"]):
        context = (
            "\nContext: this file is test or fixture code, not application code.\n"
        )
    return (
        "Scanner: %s reported %s at line %d of %s\n"
        "Scanner message: %s\n%s\n"
        "Numbered source:\n%s"
        % (
            scanner["tool"],
            ", ".join(scanner["refs"]),
            scanner["line"],
            scanner["file"],
            scanner["message"],
            context,
            source,
        )
    )


COMMENT_PLACEHOLDER = "# [comment removed by the review bot]"
DOCSTRING_PLACEHOLDER = '"""[docstring removed by the review bot]"""'


def sanitize_python(text):
    """Remove comments and docstrings, keeping every line where it was.

    Module 6 input sanitization. Comments, docstrings, and bare string
    statements are written by the author of the code under review, and the
    model treats them as evidence: a docstring that calls a file test
    fixtures talked the model out of two real secrets in Module 5. Code
    lines are untouched and the line count never changes, so citations
    still point at the real file. If the file does not parse, it is
    returned unchanged with a warning.
    """
    lines = text.split("\n")
    try:
        tree = ast.parse(text)
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (SyntaxError, tokenize.TokenError, ValueError):
        warn("could not parse the file for sanitizing, sending it unchanged.")
        return text

    # Bare string statements: docstrings, and dead strings anywhere.
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            first, last = node.lineno - 1, (node.end_lineno or node.lineno) - 1
            indent = lines[first][: len(lines[first]) - len(lines[first].lstrip())]
            lines[first] = indent + DOCSTRING_PLACEHOLDER
            for index in range(first + 1, last + 1):
                lines[index] = ""

    # Comments, including the ones after code on the same line.
    for token in reversed(tokens):
        if token.type == tokenize.COMMENT:
            row, col = token.start
            line = lines[row - 1]
            if line[col:].startswith("#"):
                lines[row - 1] = line[:col] + COMMENT_PLACEHOLDER

    return "\n".join(lines)


def numbered_source(path, sanitize=False):
    """Read a file with 1-based line numbers prefixed."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        warn("could not read %s: %s" % (path, exc))
        return None
    if sanitize and str(path).endswith(".py"):
        text = sanitize_python(text)
    return "\n".join("%d: %s" % (i, line) for i, line in enumerate(text.splitlines(), 1))


# -------------------------------------------------------------- repo-read


def repo_scope(file_path):
    """The folder the repo-read tool may read: the reviewed file's top folder."""
    parts = Path(file_path).parts
    return (REPO_ROOT / parts[0]).resolve() if len(parts) > 1 else REPO_ROOT.resolve()


def repo_index(scope, config):
    """A menu of readable Python files and the functions and classes in each."""
    excluded = set(config["review"]["excluded_paths"]) | {"tests"}
    lines = []
    for path in sorted(scope.rglob("*.py")):
        if excluded.intersection(path.relative_to(scope).parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        names = [
            n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        lines.append("%s: %s" % (_relative(path), ", ".join(names) or "(no functions)"))
    return "\n".join(lines)


def read_symbol(request, scope, config):
    """Return (label, numbered source) for one read request, or (label, refusal).

    Read-only, confined to the scope folder, Python files only, never test
    files, capped at READ_MAX_LINES lines. Sanitizing applies here too.
    """
    file_name = str(request.get("file", "")).strip()
    symbol = str(request.get("symbol", "")).strip()
    label = "%s: %s" % (file_name, symbol)
    path = (REPO_ROOT / file_name).resolve()
    if scope not in path.parents or path.suffix != ".py" or not path.is_file():
        return label, "refused: only Python files inside %s can be read." % _relative(scope)
    blocked = {"tests"} | set(config["review"]["excluded_paths"])
    if blocked & set(path.relative_to(scope).parts):
        return label, "refused: test and excluded files cannot be read."

    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return label, "refused: the file does not parse."
    node = next(
        (
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == symbol
        ),
        None,
    )
    if node is None:
        return label, "not found: no function or class named %s in %s." % (symbol, file_name)

    if config["review"]["sanitize_source"]:
        text = sanitize_python(text)
    source_lines = text.splitlines()
    first = min([node.lineno] + [d.lineno for d in node.decorator_list])
    last = min(node.end_lineno or node.lineno, first + READ_MAX_LINES - 1)
    body = "\n".join("%d: %s" % (i, source_lines[i - 1]) for i in range(first, last + 1))
    return label, body


def gather_context(config, prompts, file_path, source):
    """Let the model ask for other code before it reviews file_path."""
    scope = repo_scope(file_path)
    user = (
        "You are about to review %s. Readable code in this repository:\n%s\n\n"
        "Numbered source of %s:\n%s" % (file_path, repo_index(scope, config), file_path, source)
    )
    result = call_model(config, prompts["repo_read"], user, READ_REQUEST_SCHEMA) or {}
    requests_made = (result.get("requests") or [])[:READ_MAX_REQUESTS]
    blocks = []
    for request in requests_made:
        label, body = read_symbol(request, scope, config)
        audit(config, "repo-read", label, body[:200])
        blocks.append("Read %s\n%s" % (label, body))
    return "\n\n".join(blocks)


def call_model(config, system, user, schema):
    """One chat call with schema-constrained decoding."""
    model = config["model"]
    url = "%s/api/chat" % model["host"]
    payload = {
        "model": model["name"],
        "format": schema,
        "stream": False,
        "options": {
            "temperature": model.get("temperature", 0),
            "num_ctx": model.get("context_tokens", 8192),
        },
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if model.get("think") is not None:
        payload["think"] = model["think"]
    try:
        response = requests.post(url, json=payload, timeout=model.get("timeout_seconds", 300))
    except requests.exceptions.ConnectionError:
        fail(
            "cannot reach Ollama at %s. Start the Ollama app or run 'ollama serve', "
            "or set OLLAMA_HOST to the machine running Ollama." % model["host"]
        )
    except requests.exceptions.Timeout:
        fail(
            "Ollama did not answer within %s seconds. Raise model.timeout_seconds "
            "in config.toml, or check that model.think is false (or low for gpt-oss)."
            % model.get("timeout_seconds", 300)
        )

    if response.status_code == 404:
        fail(
            "model '%s' is not present. Pull it with 'ollama pull %s'."
            % (model["name"], model["name"])
        )
    if response.status_code == 400 and "does not support thinking" in response.text:
        fail(
            "model '%s' has no reasoning mode, so think cannot be a level. "
            "Set model.think = false in config.toml, or unset REVIEW_THINK."
            % model["name"]
        )
    if response.status_code != 200:
        fail("Ollama returned HTTP %s: %s" % (response.status_code, response.text[:300]))

    try:
        content = response.json()["message"]["content"]
        result = json.loads(content)
    except (KeyError, ValueError):
        warn("model returned output that was not valid JSON, dropping it.")
        content, result = None, None
    audit(config, system, user, content)
    return result


def audit(config, system, user, content):
    """Append one record per model call to the audit log, if one is set.

    Module 6 audit logging. Each record holds the model, its reasoning
    setting, a sha256 of the exact prompt, the user prompt, and the raw
    answer, so any verdict can be traced to what produced it. The log
    contains source code from the review, so treat it like the code.
    """
    path = config["review"].get("audit_log")
    if not path:
        return
    prompt = system + "\n\n" + user
    record = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": config["model"]["name"],
        "think": config["model"].get("think"),
        "sanitized": config["review"].get("sanitize_source", False),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "user_prompt": user,
        "answer": content,
    }
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError as exc:
        warn("could not write the audit log at %s: %s" % (path, exc))


# ------------------------------------------------------------- validation


def _squash(text):
    return " ".join(str(text).split())


def evidence_matches(evidence, file_path, start, end):
    """True when the quoted evidence really appears at the cited lines.

    Compares the start of the evidence's first line, ignoring whitespace,
    with the real file's lines from one before start to one after end. A
    model that cites line 55 of app.py while quoting auth.py fails this.
    """
    path = REPO_ROOT / file_path
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    window = _squash(" ".join(lines[max(start - 2, 0):end + 1]))
    first = next((line for line in str(evidence).splitlines() if line.strip()), "")
    probe = _squash(first)[:40]
    return bool(probe) and probe in window


def validate_finding(candidate, file_path, scanner_refs=None, line_budget=None):
    """Enforce citation-required. Returns a finding, or None.

    A finding without a file and a usable line range is not a finding. It
    gets dropped and the reason is logged, which is the pattern taught in
    Module 3.5 and enforced here rather than merely requested in the prompt.
    """
    if not isinstance(candidate, dict):
        warn("dropped a finding that was not an object.")
        return None

    title = str(candidate.get("title", "")).strip()
    if not title:
        warn("dropped a finding with no title.")
        return None

    if not file_path:
        warn("dropped '%s': no file to cite." % title)
        return None

    start = candidate.get("line_start")
    end = candidate.get("line_end")
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < 1:
        warn("dropped '%s': no usable line citation." % title)
        return None
    if end < start:
        start, end = end, start

    if line_budget is not None and start > line_budget:
        warn(
            "dropped '%s': cites line %d, but %s has %d lines."
            % (title, start, file_path, line_budget)
        )
        return None

    evidence = str(candidate.get("evidence", "")).strip()
    if not evidence:
        warn("dropped '%s': no evidence quoted." % title)
        return None
    if (REPO_ROOT / file_path).is_file() and not evidence_matches(evidence, file_path, start, end):
        warn(
            "dropped '%s': the quoted evidence is not on lines %d-%d of %s."
            % (title, start, end, file_path)
        )
        return None

    severity = str(candidate.get("severity", "")).lower()
    if severity not in SEVERITIES:
        warn("'%s' had severity '%s', recording as info." % (title, severity))
        severity = "info"

    confidence = str(candidate.get("confidence", "")).lower()
    if confidence not in CONFIDENCES:
        confidence = "low"

    refs = scanner_refs or []
    return {
        "id": "%s:%d" % (file_path, start) if not refs else "%s:%s:%d" % (refs[0], file_path, start),
        "severity": severity,
        "title": title,
        "file": file_path,
        "line_start": start,
        "line_end": end,
        "evidence": evidence[:500],
        "explanation": str(candidate.get("explanation", "")).strip(),
        "scanner_ref": ", ".join(refs) if refs else None,
        "confidence": confidence,
    }


# ---------------------------------------------------------------- review


def triage_findings(config, prompts, scanner_findings, dry_run):
    """One model call per scanner finding."""
    findings = []
    rendered = []

    for scanner in scanner_findings:
        source = numbered_source(REPO_ROOT / scanner["file"], config["review"]["sanitize_source"])
        if source is None:
            continue
        total_lines = source.count("\n") + 1

        user = build_triage_user(scanner, source)

        if dry_run:
            rendered.append({"system": prompts["triage"], "user": user})
            continue

        result = call_model(config, prompts["triage"], user, TRIAGE_SCHEMA)
        if result is None:
            continue
        finding = validate_finding(
            result, scanner["file"], scanner["refs"], line_budget=total_lines
        )
        if finding:
            findings.append(finding)

    return findings, rendered


def sweep_file(config, prompts, file_path, known, dry_run):
    """Freeform review of one file, the secondary path."""
    source = numbered_source(REPO_ROOT / file_path, config["review"]["sanitize_source"])
    if source is None:
        return [], []
    total_lines = source.count("\n") + 1

    known_text = (
        "\n".join("line %d: %s" % (k["line"], ", ".join(k["refs"])) for k in known)
        or "none"
    )
    user = (
        "Already-known findings, do not repeat these:\n%s\n\n"
        "Numbered source of %s:\n%s" % (known_text, file_path, source)
    )

    if dry_run:
        return [], [{"system": prompts["sweep"], "user": user}]

    if config["review"]["repo_read"]:
        context = gather_context(config, prompts, file_path, source)
        if context:
            user += (
                "\n\nOther code you asked to read. It is context only: cite lines of %s, "
                "not of these files.\n\n%s" % (file_path, context)
            )

    result = call_model(config, prompts["sweep"], user, SWEEP_SCHEMA)
    if result is None:
        return [], []

    findings = []
    for candidate in result.get("findings", []):
        finding = validate_finding(candidate, file_path, None, line_budget=total_lines)
        if finding:
            findings.append(finding)
    return findings, []


# ------------------------------------------------------------------- cli


def build_parser():
    parser = argparse.ArgumentParser(
        prog="review.py",
        description="AI-assisted security code review over scanner output.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", help="review a single file, or every .py file under a directory")
    source.add_argument("--diff", help="review a unified diff file")
    source.add_argument("--staged", action="store_true", help="review git diff --cached")

    parser.add_argument(
        "--sarif",
        help="use findings from an existing SARIF file instead of running the scanners",
    )
    parser.add_argument(
        "--no-scanner",
        action="store_true",
        help="skip the scanners and review the raw code (secondary path)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="render the prompts and exit without calling the model",
    )
    parser.add_argument(
        "--repo-read",
        action="store_true",
        help="with --no-scanner, let the model read named functions elsewhere in the repository first",
    )
    return parser


def resolve_targets(args, config):
    """Return (files_to_review, changed_lines_by_file)."""
    if args.file:
        path = Path(args.file)
        if path.is_dir():
            excluded = set(config["review"]["excluded_paths"])
            files = sorted(
                p
                for p in path.rglob("*.py")
                if not excluded.intersection(p.parts)
            )
            if not files:
                fail("no Python files found under %s." % args.file)
            return files, None
        if not path.is_file():
            fail("no such file or directory: %s" % args.file)
        return [path], None

    diff_text = read_staged_diff() if args.staged else Path(args.diff).read_text(encoding="utf-8")
    changed = parse_unified_diff(diff_text)
    files = []
    for name in changed:
        candidate = REPO_ROOT / name
        if candidate.is_file():
            files.append(candidate)
        else:
            warn("diff references %s, which is not on disk. Skipping." % name)
    return files, changed


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config()
    prompts = load_prompts()
    if args.repo_read:
        config["review"]["repo_read"] = True
    if config["review"]["repo_read"] and "repo_read" not in prompts:
        fail("repo-read is on, but %s has no '## repo_read' section." % PROMPT_PATH)

    files, changed_lines = resolve_targets(args, config)
    target_label = args.file or (args.diff if args.diff else "staged changes")

    if not files:
        print(json.dumps(
            {
                "model": config["model"]["name"],
                "target": target_label,
                "findings": [],
                "no_findings_reason": "The diff contained no reviewable files on disk.",
            },
            indent=2,
        ))
        return 0

    scanner_findings = []
    if not args.no_scanner:
        if args.sarif:
            sarif_path = Path(args.sarif)
            if not sarif_path.is_file():
                fail("no such SARIF file: %s" % args.sarif)
            try:
                scanner_findings = parse_sarif(json.loads(sarif_path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                fail("%s is not valid JSON. Expected a SARIF 2.1.0 document." % args.sarif)
            for finding in scanner_findings:
                finding["refs"] = [finding["rule_id"]]
        else:
            scanner_findings = collect_scanner_findings(files, config)

        if changed_lines is not None:
            scanner_findings = [
                f for f in scanner_findings if f["line"] in changed_lines.get(f["file"], set())
            ]

    findings = []
    rendered = []

    if args.no_scanner:
        for path in files:
            found, render = sweep_file(config, prompts, _relative(path), [], args.dry_run)
            findings += found
            rendered += render
    else:
        findings, rendered = triage_findings(config, prompts, scanner_findings, args.dry_run)

    if args.dry_run:
        print(json.dumps(
            {
                "model": config["model"]["name"],
                "target": target_label,
                "dry_run": True,
                "scanner_findings": len(scanner_findings),
                "prompts": rendered,
            },
            indent=2,
        ))
        return 0

    max_findings = config["review"]["max_findings"]
    if len(findings) > max_findings:
        warn("emitting %d of %d findings, capped by review.max_findings." % (max_findings, len(findings)))
        findings = findings[:max_findings]

    severity_order = {name: index for index, name in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: (severity_order.get(f["severity"], 99), f["file"], f["line_start"]))

    no_findings_reason = None
    if not findings:
        if args.no_scanner:
            no_findings_reason = "The model reviewed the code and reported nothing it could cite."
        elif not scanner_findings:
            no_findings_reason = "The scanners reported nothing on the reviewed code."
        else:
            no_findings_reason = (
                "The scanners reported %d item(s), but none survived citation checking."
                % len(scanner_findings)
            )

    print(json.dumps(
        {
            "model": config["model"]["name"],
            "target": target_label,
            "findings": findings,
            "no_findings_reason": no_findings_reason,
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
