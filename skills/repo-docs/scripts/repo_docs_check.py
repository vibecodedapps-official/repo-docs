#!/usr/bin/env python3
"""Check that AGENTS.md / CLAUDE.md bridges and docs in a repo are correct.

Five checks: bridge (error), rival (warning), size (info/warning),
link (error), stale (info).

Exit codes: 0 = no error findings, 1 = at least one error finding, 2 = usage
error or internal failure. Only unambiguous problems (missing/broken
bridges, dead links) are errors: a checker wired into a session hook that
fails on advisory findings gets switched off.

Standard library only. Never writes or edits a file.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

EXCLUDED_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
LINK_EXTS = (".md", ".markdown", ".txt", ".json", ".yml", ".yaml", ".toml", ".py", ".sh", ".js", ".ts")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
CODE_SPAN_RE = re.compile(r"`[^`]*`")
SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}

def safe_read_text(path):
    """UTF-8 text, bad bytes replaced, or None if the file can't be read at
    all (broken symlink, permission error). Unreadable is a normal outcome
    here, not a crash."""
    try:
        return path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None

def safe_stat_size(path):
    """Byte size of path, or None if it can't be statted (broken symlink)."""
    try:
        return path.stat().st_size
    except OSError:
        return None

def posix_rel(root, path):
    return os.path.relpath(str(path), str(root)).replace(os.sep, "/")

def posix_dir(rel_path):
    return rel_path.rsplit("/", 1)[0] if "/" in rel_path else ""

def posix_join(dir_, name):
    return name if dir_ == "" else f"{dir_}/{name}"

def finding(check, severity, path, message, fix=""):
    return {"check": check, "severity": severity, "path": path, "message": message, "fix": fix}

def exists_on_disk(path):
    """True if path is there at all, including a broken symlink: .exists()
    alone follows symlinks and says False for a broken one."""
    return path.exists() or path.is_symlink()


# ---------------------------------------------------------------------------
# Scanning

def filter_gitignored(root, rel_paths):
    """Drop paths matched by .gitignore (empty result if git is unavailable).
    Uses -z: newline-separated I/O breaks on a path with non-ASCII or
    control bytes (git C-quotes those on output) or an embedded newline."""
    if not rel_paths:
        return set()
    payload = b"\x00".join(p.encode("utf-8") for p in rel_paths) + b"\x00"
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "--stdin", "-z"],
            cwd=str(root), input=payload,
            capture_output=True,
        )
    except OSError:
        return set()
    if proc.returncode not in (0, 1):
        return set()
    return {p.decode("utf-8", errors="replace") for p in proc.stdout.split(b"\x00") if p}

def collect_paths(root):
    """Find AGENTS.md and CLAUDE.md, honoring the static and .gitignore
    exclusions. docs/**/*.md is not collected: the stale check just uses
    the "docs" git pathspec, which matches that whole subtree already."""
    agents, claude = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for name in filenames:
            rel = posix_rel(root, os.path.join(dirpath, name))
            if name == "AGENTS.md":
                agents.append(rel)
            elif name == "CLAUDE.md":
                claude.append(rel)
    ignored = filter_gitignored(root, agents + claude)
    keep = lambda paths: [p for p in paths if p not in ignored]
    return keep(agents), keep(claude)


# ---------------------------------------------------------------------------
# bridge, rival, size (these three share the AGENTS.md/CLAUDE.md pairing)

def bridge_status(root, a_dir, a_rel):
    """Return (bridge value, error finding or None) for one AGENTS.md dir.
    Resolves the CLAUDE.md sibling against the filesystem, not against the
    gitignore-filtered scan list: a gitignored CLAUDE.md still exists and
    Claude Code still loads it, so it must not be reported as missing."""
    c_rel = posix_join(a_dir, "CLAUDE.md")
    c_path, a_path = root / c_rel, root / a_rel

    if not exists_on_disk(c_path):
        fix = f"printf '@AGENTS.md\\n' > {c_rel}"
        msg = f"{a_rel} has no CLAUDE.md bridge; Claude Code will not load it"
        return "missing", finding("bridge", "error", a_rel, msg, fix)

    fix = f"printf '@AGENTS.md\\n' > {c_rel}"

    if c_path.is_symlink():
        if c_path.resolve() == a_path.resolve():
            return "symlink", None
        msg = f"{c_rel} is a symlink but does not resolve to {a_rel}; Claude Code will not load {a_rel}"
        return "invalid", finding("bridge", "error", c_rel, msg, f"ln -sf AGENTS.md {c_rel}")

    if c_path.is_file():
        text = safe_read_text(c_path)
        if text is None:
            msg = f"{c_rel} could not be read (permission error); Claude Code will not load {a_rel}"
            return "invalid", finding("bridge", "error", c_rel, msg, fix)
        first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        if first_line == "@AGENTS.md":
            return "import", None
        msg = f"{c_rel} first line is not exactly '@AGENTS.md' (mentioning it in prose does not count); Claude Code will not load {a_rel}"
        return "invalid", finding("bridge", "error", c_rel, msg, fix)

    msg = f"{c_rel} is not a regular file or symlink; Claude Code will not load {a_rel}"
    return "invalid", finding("bridge", "error", c_rel, msg, fix)

def agents_size_finding(a_rel, a_bytes):
    if a_bytes <= 2000:
        return None
    if a_bytes <= 6000:
        msg = f"{a_rel} is {a_bytes} bytes; consider moving detail to docs/ or a nested AGENTS.md"
        return finding("size", "info", a_rel, msg)
    msg = f"{a_rel} is {a_bytes} bytes, over the 6000 byte warning threshold; move detail to docs/ or a nested AGENTS.md"
    return finding("size", "warning", a_rel, msg)

def dangling_import(c_path, is_symlink):
    """For a CLAUDE.md with no sibling AGENTS.md on disk: is it shaped like
    a bridge attempt (a dangling import, the inverse of the bridge check),
    and what byte count should it report? A symlink named AGENTS.md at its
    target, or a file whose first line is exactly '@AGENTS.md', reports 0
    bytes and is dangling, not a rival. Anything else is a real rival
    candidate, measured for real (including through a symlink to an
    unrelated file), so the rival check can see it."""
    if is_symlink:
        target = c_path.resolve()
        if target.name == "AGENTS.md":
            return True, 0
        return False, safe_stat_size(target) or 0
    text = safe_read_text(c_path)
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "") if text is not None else ""
    if first_line == "@AGENTS.md":
        return True, 0
    return False, safe_stat_size(c_path) or 0

def analyze_docs(root, agents_rel, claude_rel):
    """Run bridge, rival, and size checks. Returns (findings, files)."""
    findings, files = [], []

    for a_rel in sorted(agents_rel):
        a_dir = posix_dir(a_rel)
        bridge, bridge_finding = bridge_status(root, a_dir, a_rel)
        if bridge_finding:
            findings.append(bridge_finding)
        a_bytes = safe_stat_size(root / a_rel)
        if a_bytes is None:
            # A broken symlink or a permission error: unreadable, not a crash.
            msg = f"{a_rel} could not be read (broken symlink or permission error); Claude Code cannot load it"
            findings.append(finding("bridge", "error", a_rel, msg))
            files.append({"path": a_rel, "bytes": 0, "status": "ok", "bridge": bridge})
            continue
        size_finding = agents_size_finding(a_rel, a_bytes)
        status = "ok"
        if size_finding:
            findings.append(size_finding)
            status = size_finding["severity"]
        files.append({"path": a_rel, "bytes": a_bytes, "status": status, "bridge": bridge})

    for c_rel in sorted(claude_rel):
        c_dir = posix_dir(c_rel)
        c_path = root / c_rel
        is_symlink = c_path.is_symlink()
        # Resolved against the filesystem, like bridge_status: a gitignored
        # sibling AGENTS.md still exists and still bridges normally.
        has_sibling = exists_on_disk(root / posix_join(c_dir, "AGENTS.md"))
        status = "ok"

        if has_sibling:
            c_bytes = 0 if is_symlink else (safe_stat_size(c_path) or 0)
            if not is_symlink and c_bytes > 300:
                msg = f"{c_rel} bridge file is {c_bytes} bytes; keep CLAUDE.md additions minimal and put substance in AGENTS.md"
                findings.append(finding("size", "info", c_rel, msg))
                status = "info"
        else:
            is_dangling, c_bytes = dangling_import(c_path, is_symlink)
            if is_dangling:
                expected = posix_join(c_dir, "AGENTS.md")
                msg = f"{c_rel} imports AGENTS.md, but {expected} does not exist; Claude Code will load a broken import"
                fix = f"create {expected}, or remove the @AGENTS.md import from {c_rel}"
                findings.append(finding("bridge", "error", c_rel, msg, fix))
            elif c_bytes > 300:
                msg = f"{c_rel} has no sibling AGENTS.md and is {c_bytes} bytes; it is acting as an independent instruction file, outside the AGENTS.md/CLAUDE.md model"
                findings.append(finding("rival", "warning", c_rel, msg))
                status = "warning"

        files.append({"path": c_rel, "bytes": c_bytes, "status": status, "bridge": None})

    return findings, files


# ---------------------------------------------------------------------------
# link

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")

def strip_fenced_code_blocks(text):
    """Blank fenced code blocks (``` or ~~~, 3+ chars) so link syntax shown
    as a documentation example is never read as a real link. A closing
    fence must match the opening character and be at least as long."""
    out_lines = []
    fence = None
    for line in text.splitlines():
        match = FENCE_RE.match(line)
        if fence is None and match:
            fence = match.group(1)
            out_lines.append("")
            continue
        if fence is not None:
            out_lines.append("")
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
                fence = None
            continue
        out_lines.append(line)
    return "\n".join(out_lines)

def link_targets(line):
    for match in LINK_RE.finditer(CODE_SPAN_RE.sub("", line)):
        target = match.group(1).strip()
        if " " in target:
            target = target.split(" ", 1)[0]
        if target:
            yield target

def check_links(root, rel_paths):
    findings = []
    seen_real_paths = set()
    for rel in sorted(rel_paths):
        real = (root / rel).resolve()
        if real in seen_real_paths:
            continue  # a symlink bridge and its AGENTS.md are the same content
        seen_real_paths.add(real)
        text = safe_read_text(root / rel)
        if text is None:
            continue  # unreadable file: the bridge/size checks already flag it
        base_dir = (root / rel).parent
        for line in strip_fenced_code_blocks(text).splitlines():
            for target in link_targets(line):
                if "://" in target or target.startswith("mailto:"):
                    continue
                if target.startswith("#") or target.startswith("<"):
                    continue
                remainder = target.split("#", 1)[0]
                if not remainder or not remainder.lower().endswith(LINK_EXTS):
                    continue
                resolved = root / remainder.lstrip("/") if remainder.startswith("/") else base_dir / remainder
                if not resolved.exists():
                    msg = f"{rel} links to '{remainder}', which does not exist"
                    findings.append(finding("link", "error", rel, msg))
    return findings


# ---------------------------------------------------------------------------
# stale

def run_git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)

def commits_touching_other_files(log_output, doc_set, docs_prefix):
    """Count commits, from one `git log --format=%x00%H --name-only` stream
    (doc_set and docs_prefix already repo-root-relative, to match it), that
    touched a file outside both. One subprocess for the whole range, not
    one per commit, so a long run since the docs last changed can't make a
    session-start hook block."""
    count = 0
    for chunk in log_output.split("\x00"):
        lines = chunk.splitlines()
        if not lines:
            continue
        changed = [ln for ln in lines[1:] if ln]
        if any(f not in doc_set and not f.startswith(docs_prefix) for f in changed):
            count += 1
    return count

def repo_relative_prefix(root):
    """ROOT's path relative to the repo's top-level directory, as a posix
    prefix ("" if ROOT is the repo root; None if undeterminable). `git log
    --name-only` reports paths relative to the repo root, never to ROOT, so
    anything compared against that output needs this to line the two up."""
    top = run_git(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return None
    try:
        rel = os.path.relpath(str(root), top.stdout.strip()).replace(os.sep, "/")
    except ValueError:
        return None
    return "" if rel == "." else rel

def check_stale(root, doc_rel_paths, threshold):
    """Skip silently if there's no usable git history: no git, not a repo,
    no commits, or a shallow clone, which cannot answer this question at
    all (reporting nothing is correct; reporting zero would be a lie)."""
    if shutil.which("git") is None:
        return None, []
    try:
        head = run_git(root, "rev-parse", "HEAD")
    except OSError:
        return None, []
    if head.returncode != 0:
        return None, []
    shallow = run_git(root, "rev-parse", "--is-shallow-repository")
    if shallow.returncode != 0 or shallow.stdout.strip() != "false":
        return None, []
    prefix = repo_relative_prefix(root)
    if prefix is None:
        return None, []

    pathspecs = list(doc_rel_paths) + ["docs"]
    last = run_git(root, "log", "-1", "--format=%H %ad", "--date=short", "--", *pathspecs)
    if last.returncode != 0:
        return None, []
    line = last.stdout.strip()
    if not line:
        return None, []
    docs_commit, docs_date = line.split(" ", 1)

    since = run_git(root, "log", "--format=%x00%H", "--name-only", f"{docs_commit}..HEAD")
    if since.returncode != 0:
        return None, []
    doc_set = {posix_join(prefix, p) for p in doc_rel_paths}
    docs_prefix = posix_join(prefix, "docs") + "/"
    commits_since = commits_touching_other_files(since.stdout, doc_set, docs_prefix)

    stale_info = {
        "checked": True,
        "commits_since_docs": commits_since,
        "threshold": threshold,
        "docs_last_changed": docs_date,
    }
    findings = []
    if commits_since > threshold:
        msg = f"{commits_since} commits since docs last changed on {docs_date} (threshold {threshold})"
        findings.append(finding("stale", "info", "", msg))
    return stale_info, findings


# ---------------------------------------------------------------------------
# report assembly

def run_checks(root, threshold):
    agents_rel, claude_rel = collect_paths(root)
    findings, files = analyze_docs(root, agents_rel, claude_rel)
    findings += check_links(root, agents_rel + claude_rel)
    stale_info, stale_findings = check_stale(root, agents_rel + claude_rel, threshold)
    findings += stale_findings

    counts = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        counts[f["severity"]] += 1

    return {
        "root": str(root),
        "ok": counts["error"] == 0,
        "counts": counts,
        "findings": findings,
        "files": files,
        "stale": stale_info if stale_info is not None else {"checked": False},
    }

def format_finding_line(f):
    prefix = f"{f['severity'].upper():7} [{f['check']}]"
    if f["path"]:
        return f"{prefix} {f['path']}: {f['message']}"
    return f"{prefix} {f['message']}"

def format_report(result):
    lines = [format_finding_line(f) for f in result["findings"]]
    counts = result["counts"]
    lines.append(f"{counts['error']} error, {counts['warning']} warning, {counts['info']} info.")
    lines.append("Byte budgets (2000/6000 bytes for AGENTS.md, 300 bytes for CLAUDE.md) are editorial defaults, not measured optima.")
    return "\n".join(lines)

def build_hook_payload(result):
    """None means print nothing. Otherwise the one SessionStart payload object."""
    findings = result["findings"]
    if not findings:
        return None
    counts = result["counts"]
    parts = [f"{counts[s]} {s}" for s in ("error", "warning", "info") if counts[s]]
    top = min(findings, key=lambda f: SEVERITY_RANK[f["severity"]])
    context = f"repo-docs: {', '.join(parts)}. {top['message']}. Run the repo-docs skill in audit mode for the full report."
    if len(context) >= 600:
        context = context[:596] + "..."
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}


# ---------------------------------------------------------------------------
# CLI

def parse_args(argv):
    parser = argparse.ArgumentParser(prog="repo_docs_check.py")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--hook", action="store_true")
    parser.add_argument("--stale-threshold", type=int, default=20, dest="stale_threshold")
    return parser.parse_args(argv)

def main(argv=None):
    args = parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"repo_docs_check: {root} is not a directory", file=sys.stderr)
        return 0 if args.hook else 2

    try:
        result = run_checks(root, args.stale_threshold)
    except Exception as exc:  # unreadable files are handled below; this is a last resort
        print(f"repo_docs_check: internal error: {exc}", file=sys.stderr)
        return 0 if args.hook else 2  # --hook always exits 0, even on failure; see stderr

    if args.hook:
        payload = build_hook_payload(result)
        if payload is not None:
            print(json.dumps(payload))
        return 0

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))
    return 1 if result["counts"]["error"] else 0

if __name__ == "__main__":
    sys.exit(main())
