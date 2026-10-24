#!/usr/bin/env python3
"""Post the review as a comment on the pull request or merge request.

Reads the JSON that review.py prints and writes one comment. On every
later push it edits that same comment instead of adding a new one, found
by a hidden marker.

  python review.py --diff pr.diff > findings.json
  python post_comment.py findings.json

GitHub Actions: uses GITHUB_TOKEN, which the workflow grants with
`permissions: pull-requests: write`. Nothing to create.

GitLab CI: the built-in CI_JOB_TOKEN cannot comment on merge requests.
Store a token as a masked CI/CD variable named REVIEW_BOT_TOKEN: a
fine-grained personal access token with read_work_item (find the earlier
comment), create_work_item (post it) and update_work_item (edit it), and
no repository permissions. Project access tokens need Premium or Ultimate
on GitLab.com.

The bot never fails the pipeline. If posting goes wrong it prints a
warning and exits 0, unless you pass --strict.

Model output is untrusted. Findings quote code from the change under
review, and that code was written by whoever opened the pull request, so
everything is escaped before it is rendered as Markdown.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests

MARKER = "<!-- security-review-bot -->"
MAX_COMMENT = 60000
MAX_FIELD = 600
SEVERITY_ICON = {
    "critical": "🔴 critical",
    "high": "🟠 high",
    "medium": "🟡 medium",
    "low": "🔵 low",
    "info": "⚪ info",
}


def warn(message):
    print("warning: %s" % message, file=sys.stderr)


# --------------------------------------------------------------- render


def escape(text, limit=MAX_FIELD):
    """Make untrusted text safe inside a Markdown table cell.

    Strips HTML, pipes, and newlines so a quoted line of code cannot close
    the table, inject markup, or hide text from the reviewer.
    """
    text = str(text or "")
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    text = text.replace("`", "'")
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text


def render(document):
    """Turn review.py output into one Markdown comment."""
    findings = document.get("findings") or []
    model = escape(document.get("model", "unknown model"), 80)
    lines = [MARKER, "### Security review bot", ""]

    if not findings:
        reason = escape(document.get("no_findings_reason") or "No findings.")
        lines += ["No findings on this change. %s" % reason, ""]
    else:
        real = [f for f in findings if f.get("severity") != "info"]
        lines += [
            "%d finding(s), %d marked informational." % (len(real), len(findings) - len(real)),
            "",
            "| Severity | Location | Finding | Why it matters |",
            "|---|---|---|---|",
        ]
        for f in findings:
            location = "`%s:%s`" % (escape(f.get("file"), 200), f.get("line_start", "?"))
            if f.get("line_end") and f.get("line_end") != f.get("line_start"):
                location = "`%s:%s-%s`" % (escape(f.get("file"), 200), f["line_start"], f["line_end"])
            lines.append(
                "| %s | %s | %s | %s |"
                % (
                    SEVERITY_ICON.get(f.get("severity"), escape(f.get("severity"), 20)),
                    location,
                    escape(f.get("title"), 200),
                    escape(f.get("explanation")),
                )
            )
        lines.append("")

    lines.append(
        "<sub>Model: %s. Advisory only: this check never blocks the merge. "
        "A human reviews before anything ships.</sub>" % model
    )
    body = "\n".join(lines)
    if len(body) > MAX_COMMENT:
        body = body[: MAX_COMMENT - 80] + "\n\n_Comment truncated._"
    return body


# ------------------------------------------------------------- platforms


def detect_platform():
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return "github"
    if os.environ.get("GITLAB_CI") == "true":
        return "gitlab"
    return None


def github_target():
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    if not (token and repo and event_path):
        return None, "GITHUB_TOKEN, GITHUB_REPOSITORY, or GITHUB_EVENT_PATH is not set."
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    number = (event.get("pull_request") or {}).get("number")
    if not number:
        return None, "this run is not for a pull request, so there is nowhere to comment."
    return {
        "list": "%s/repos/%s/issues/%s/comments?per_page=100" % (api, repo, number),
        "create": "%s/repos/%s/issues/%s/comments" % (api, repo, number),
        "update": "%s/repos/%s/issues/comments/{id}" % (api, repo),
        "update_method": "PATCH",
        "headers": {
            "Authorization": "Bearer %s" % token,
            "Accept": "application/vnd.github+json",
        },
    }, None


def gitlab_target():
    token = os.environ.get("REVIEW_BOT_TOKEN")
    api = os.environ.get("CI_API_V4_URL")
    project = os.environ.get("CI_PROJECT_ID")
    iid = os.environ.get("CI_MERGE_REQUEST_IID")
    if not token:
        return None, (
            "REVIEW_BOT_TOKEN is not set. Create a fine-grained personal access "
            "token with read_work_item, create_work_item and update_work_item, "
            "and add it as a masked CI/CD variable. See ci-templates/README.md."
        )
    if not (api and project and iid):
        return None, "this pipeline is not for a merge request, so there is nowhere to comment."
    base = "%s/projects/%s/merge_requests/%s/notes" % (api, project, iid)
    return {
        "list": base + "?per_page=100",
        "create": base,
        "update": base + "/{id}",
        "update_method": "PUT",
        "headers": {"PRIVATE-TOKEN": token},
    }, None


def post(target, body):
    """Edit the bot's earlier comment if there is one, otherwise create it."""
    headers = target["headers"]
    response = requests.get(target["list"], headers=headers, timeout=30)
    response.raise_for_status()
    existing = next((c for c in response.json() if MARKER in (c.get("body") or "")), None)
    if existing:
        url = target["update"].format(id=existing["id"])
        response = requests.request(target["update_method"], url, headers=headers, json={"body": body}, timeout=30)
        action = "updated"
    else:
        response = requests.post(target["create"], headers=headers, json={"body": body}, timeout=30)
        action = "created"
    response.raise_for_status()
    return action


# ------------------------------------------------------------------- cli



def read_input_text(path):
    """Read a file another tool wrote, whatever its encoding.

    Windows PowerShell 5.1 writes `>` redirects as UTF-16 with a byte order
    mark, and some editors add a UTF-8 one. Both are decoded here, so a
    findings file or diff made on any platform reads the same way.
    """
    data = Path(path).read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    return data.decode("utf-8-sig")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Post review.py findings as a PR or MR comment.")
    parser.add_argument("findings", help="JSON file written by review.py")
    parser.add_argument("--platform", choices=["github", "gitlab"], help="default: detected from the CI environment")
    parser.add_argument("--print", action="store_true", help="print the comment instead of posting it")
    parser.add_argument("--strict", action="store_true", help="exit 1 if posting fails")
    args = parser.parse_args(argv)

    try:
        document = json.loads(read_input_text(args.findings))
    except (OSError, ValueError) as error:
        warn("could not read %s: %s. Did review.py run?" % (args.findings, error))
        return 1 if args.strict else 0

    body = render(document)
    if args.print:
        print(body)
        return 0

    platform = args.platform or detect_platform()
    if platform is None:
        warn("not running in GitHub Actions or GitLab CI. Pass --print to see the comment.")
        return 1 if args.strict else 0

    target, problem = github_target() if platform == "github" else gitlab_target()
    if problem:
        warn(problem)
        return 1 if args.strict else 0

    try:
        action = post(target, body)
    except requests.RequestException as error:
        warn("posting the comment failed: %s. Check the token's permissions." % error)
        return 1 if args.strict else 0

    print("Comment %s." % action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
