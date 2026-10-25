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


def location(f):
    where = "`%s:%s`" % (escape(f.get("file"), 200), f.get("line_start", "?"))
    if f.get("line_end") and f.get("line_end") != f.get("line_start"):
        where = "`%s:%s-%s`" % (escape(f.get("file"), 200), f["line_start"], f["line_end"])
    return where


def render(document):
    """Turn review.py output into one Markdown comment."""
    everything = document.get("findings") or []
    findings = [f for f in everything if not f.get("suppressed")]
    suppressed = [f for f in everything if f.get("suppressed")]
    model = escape(document.get("model", "unknown model"), 80)
    lines = [MARKER, "### Security review bot", ""]

    if not findings:
        reason = escape(document.get("no_findings_reason") or "No findings.")
        if suppressed:
            reason = "Every finding is covered by an approved suppression."
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
            lines.append(
                "| %s | %s | %s | %s |"
                % (
                    SEVERITY_ICON.get(f.get("severity"), escape(f.get("severity"), 20)),
                    location(f),
                    escape(f.get("title"), 200),
                    escape(f.get("explanation")),
                )
            )
        lines.append("")

    if suppressed:
        lines += [
            "**Suppressed by `security-suppressions.toml`** (approved bypasses, shown so nothing disappears silently):",
            "",
            "| Severity | Location | Finding | Reason | Approved by |",
            "|---|---|---|---|---|",
        ]
        for f in suppressed:
            lines.append(
                "| %s | %s | %s | %s | %s |"
                % (
                    SEVERITY_ICON.get(f.get("severity"), escape(f.get("severity"), 20)),
                    location(f),
                    escape(f.get("title"), 200),
                    escape(f["suppressed"].get("reason"), 300),
                    escape(f["suppressed"].get("approved_by"), 80),
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


# ---------------------------------------------------------- suggestions

FIX_MARKER = "<!-- security-review-bot:fix %s:%s -->"
MAX_SUGGESTIONS = 5


def suggestion_candidates(findings, changed):
    """Findings worth a one-click fix: real, not suppressed, wholly on changed lines."""
    picked = []
    for f in findings:
        if f.get("severity") == "info" or f.get("suppressed"):
            continue
        lines = set(range(f["line_start"], f["line_end"] + 1))
        if not lines <= set(changed.get(f["file"], ())):
            continue
        picked.append(f)
    return picked[:MAX_SUGGESTIONS]


def suggestion_body(finding, fix, platform):
    """One line comment: what, the model-written patch, and a warning to read it."""
    if not fix.get("lines"):
        return "\n".join([
            FIX_MARKER % (finding["file"], finding["line_start"]),
            "**Recommended fix: %s**" % escape(finding.get("title"), 200),
            "",
            escape(fix.get("rationale"), 800),
            "",
            "<sub>No one-click patch: the model was not confident it could fix this safely in place. "
            "Written by the model, which read the code under review.</sub>",
        ])
    span = finding["line_end"] - finding["line_start"]
    fence = "```suggestion" if platform == "github" else "```suggestion:-0+%d" % span
    parts = [
        FIX_MARKER % (finding["file"], finding["line_start"]),
        "**Suggested fix: %s**" % escape(finding.get("title"), 200),
        "",
        fence,
        "\n".join(fix["lines"]),
        "```",
        "",
    ]
    if fix.get("rationale"):
        parts += [escape(fix["rationale"], 500), ""]
    parts.append(
        "<sub>Written by the model, which read the code under review. "
        "Read it before you apply it: nothing is committed until a person clicks.</sub>"
    )
    return "\n".join(parts)


def github_line_api(target):
    """Review-comment endpoints and the head commit, from the Actions event."""
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    pr = event["pull_request"]
    base = target["create"].replace("/issues/", "/pulls/")
    return {"list": base + "?per_page=100", "create": base, "head": pr["head"]["sha"]}


def github_line_payload(finding, body, head):
    payload = {"body": body, "commit_id": head, "path": finding["file"],
               "line": finding["line_end"], "side": "RIGHT"}
    if finding["line_end"] != finding["line_start"]:
        payload.update(start_line=finding["line_start"], start_side="RIGHT")
    return payload


def gitlab_line_api(target):
    """Discussion endpoint and the diff version a line position must name."""
    base = target["create"].rsplit("/notes", 1)[0]
    response = requests.get(base + "/versions", headers=target["headers"], timeout=30)
    response.raise_for_status()
    version = response.json()[0]
    return {"list": base + "/discussions?per_page=100", "create": base + "/discussions",
            "shas": (version["base_commit_sha"], version["start_commit_sha"], version["head_commit_sha"])}


def gitlab_line_payload(finding, body, shas):
    base_sha, start_sha, head_sha = shas
    return {"body": body, "position": {
        "position_type": "text", "base_sha": base_sha, "start_sha": start_sha, "head_sha": head_sha,
        "new_path": finding["file"], "new_line": finding["line_start"],
    }}


def existing_bodies(platform, api, headers):
    response = requests.get(api["list"], headers=headers, timeout=30)
    response.raise_for_status()
    items = response.json()
    if platform == "gitlab":
        return [n.get("body") or "" for d in items for n in d.get("notes", [])]
    return [c.get("body") or "" for c in items]


def make_suggestions(document, diff_path):
    """Ask the model for a fix to each eligible finding. Returns [(finding, fix)]."""
    import fixes
    import review

    changed = review.parse_unified_diff(read_input_text(diff_path))
    config = review.load_config()
    prompts = review.load_prompts()
    if "fix" not in prompts:
        warn("prompts/review_system.md has no '## fix' section, so no fixes are suggested.")
        return []
    out = []
    for finding in suggestion_candidates(document.get("findings") or [], changed):
        fix = fixes.suggest_fix(config, prompts, finding)
        if fix:
            out.append((finding, fix))
        else:
            warn("no safe fix suggested for %s:%s." % (finding["file"], finding["line_start"]))
    return out


def post_suggestions(platform, target, suggestions):
    """Post each fix once, as a line comment with the platform's apply button."""
    headers = target["headers"]
    api = github_line_api(target) if platform == "github" else gitlab_line_api(target)
    seen = existing_bodies(platform, api, headers)
    posted = 0
    for finding, fix in suggestions:
        marker = FIX_MARKER % (finding["file"], finding["line_start"])
        if any(marker in body for body in seen):
            continue
        body = suggestion_body(finding, fix, platform)
        payload = (github_line_payload(finding, body, api["head"]) if platform == "github"
                   else gitlab_line_payload(finding, body, api["shas"]))
        response = requests.post(api["create"], headers=headers, json=payload, timeout=30)
        if response.status_code >= 400:
            warn("could not post the fix for %s:%s: HTTP %s %s"
                 % (finding["file"], finding["line_start"], response.status_code, response.text[:200]))
            continue
        posted += 1
    return posted


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
    # Windows writes redirected output in its legacy code page, which has no
    # emoji and no typographic dashes. UTF-8 everywhere instead.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Post review.py findings as a PR or MR comment.")
    parser.add_argument("findings", help="JSON file written by review.py")
    parser.add_argument("--platform", choices=["github", "gitlab"], help="default: detected from the CI environment")
    parser.add_argument("--print", action="store_true", help="print the comment instead of posting it")
    parser.add_argument("--strict", action="store_true", help="exit 1 if posting fails")
    parser.add_argument("--suggest", action="store_true",
                        help="also post a one-click suggested fix on each finding's changed lines (needs --diff and the model)")
    parser.add_argument("--diff", help="the diff the review ran on, so fixes go only on changed lines")
    args = parser.parse_args(argv)
    if args.suggest and not args.diff:
        warn("--suggest needs --diff, so fixes land only on lines the change touched.")
        return 1 if args.strict else 0

    try:
        document = json.loads(read_input_text(args.findings))
    except (OSError, ValueError) as error:
        warn("could not read %s: %s. Did review.py run?" % (args.findings, error))
        return 1 if args.strict else 0

    body = render(document)
    if args.print:
        print(body)
        suggestions = make_suggestions(document, args.diff) if args.suggest else []
        for finding, fix in suggestions:
            print("\n--- suggested fix on %s:%s ---" % (finding["file"], finding["line_start"]))
            print(suggestion_body(finding, fix, args.platform or "github"))
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
    # Fixes come after the summary, so a slow model can never hold the summary back.
    suggestions = make_suggestions(document, args.diff) if args.suggest else []
    if suggestions:
        try:
            print("Posted %d suggested fix(es)." % post_suggestions(platform, target, suggestions))
        except (requests.RequestException, KeyError, IndexError, ValueError) as error:
            warn("posting suggested fixes failed: %s. The summary comment is unaffected." % error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
