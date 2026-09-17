"""Tests for repo_docs_check.py.

Every check gets a positive fixture (it fires) and a negative fixture
(valid documentation, zero findings). The negative fixtures matter most:
a checker that cries wolf on good docs gets switched off.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, SCRIPT, can_symlink, run_checker, run_checker_json


# SCRIPT's directory is hyphenated (skills/repo-docs/...), so it cannot be
# imported as a normal package; load it directly from its file path instead.
_spec = importlib.util.spec_from_file_location("repo_docs_check", SCRIPT)
CHECK = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CHECK)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True
    )


def git_commit(root, message):
    git(root, "add", "-A")
    result = git(
        root,
        "-c", "user.email=test@example.com",
        "-c", "user.name=Test",
        "commit", "-m", message,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def init_git_repo(root):
    result = git(root, "init", "-q")
    assert result.returncode == 0, result.stdout + result.stderr


def findings_of(result, check):
    return [f for f in result["findings"] if f["check"] == check]


class CheckerTestCase(unittest.TestCase):
    """Base class giving each test its own scratch directory."""

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp_path, ignore_errors=True)

    def write_bridge(self, target=None, agents="Rules.\n", claude="@AGENTS.md\n"):
        """Write a valid AGENTS.md + CLAUDE.md import bridge under target
        (default: tmp_path itself)."""
        target = self.tmp_path if target is None else target
        write(target / "AGENTS.md", agents)
        write(target / "CLAUDE.md", claude)

    def mkdir(self, name="pkg"):
        """Create and return a fresh subdirectory of tmp_path."""
        d = self.tmp_path / name
        d.mkdir()
        return d


@unittest.skipIf(os.name == "nt", "Exercises the POSIX hook command")
class TestPluginHook(CheckerTestCase):
    def run_hook(self, project_dir=None):
        manifest = json.loads(
            (REPO_ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8")
        )
        self.assertTrue((REPO_ROOT / manifest["skills"] / "repo-docs/SKILL.md").is_file())
        config = json.loads((REPO_ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
        command = config["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(REPO_ROOT))
        env.pop("CLAUDE_PROJECT_DIR", None)
        if project_dir is not None:
            env["CLAUDE_PROJECT_DIR"] = str(project_dir)
        return subprocess.run(
            ["/bin/sh", "-c", command], cwd=self.tmp_path, env=env,
            capture_output=True, text=True,
        )

    def test_codex_hook_reports_findings_from_session_directory(self):
        write(self.tmp_path / "AGENTS.md", "Rules.\n")
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(payload["hookEventName"], "SessionStart")
        self.assertIn("1 error", payload["additionalContext"])

    def test_codex_hook_is_silent_when_clean(self):
        self.write_bridge()
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, "")

    def test_claude_hook_preserves_explicit_project_directory(self):
        project = self.mkdir("project with spaces")
        write(project / "AGENTS.md", "Rules.\n")
        self.write_bridge()
        result = self.run_hook(project)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("1 error", context)


# ---------------------------------------------------------------------------
# bridge

class TestBridge(CheckerTestCase):
    def test_bridge_missing_is_error(self):
        write(self.tmp_path / "pkg" / "AGENTS.md", "Rules for pkg.\n")
        result, _ = run_checker_json(self.tmp_path)
        bridge_findings = findings_of(result, "bridge")
        self.assertEqual(len(bridge_findings), 1)
        self.assertEqual(bridge_findings[0]["severity"], "error")
        self.assertIn("pkg/AGENTS.md", bridge_findings[0]["path"])
        self.assertEqual(result["counts"]["error"], 1)

    def test_missing_bridge_fix_creates_the_file(self):
        """Nothing is there yet, so the redirect that creates it is safe."""
        write(self.tmp_path / "pkg" / "AGENTS.md", "Rules for pkg.\n")
        result, _ = run_checker_json(self.tmp_path)
        self.assertIn("printf", findings_of(result, "bridge")[0]["fix"])

    def test_existing_bridge_fix_does_not_truncate_the_file(self):
        """A CLAUDE.md that exists may hold rules AGENTS.md does not. The
        suggested fix must not be a shell redirect, which would delete them."""
        pkg = self.mkdir("pkg")
        write(pkg / "AGENTS.md", "Rules for pkg.\n")
        write(pkg / "CLAUDE.md", "Never deploy without approval.\n")
        result, _ = run_checker_json(self.tmp_path)
        fix = findings_of(result, "bridge")[0]["fix"]
        self.assertNotIn(">", fix)
        self.assertIn("keeping the rest of the file", fix)

    def test_bridge_import_is_valid(self):
        self.write_bridge(self.tmp_path / "pkg", agents="Rules for pkg.\n")
        result, _ = run_checker_json(self.tmp_path)
        self.assertEqual(findings_of(result, "bridge"), [])
        self.assertEqual(result["counts"]["error"], 0)
        agents_entry = next(f for f in result["files"] if f["path"] == "pkg/AGENTS.md")
        self.assertEqual(agents_entry["bridge"], "import")

    def test_bridge_prose_mention_is_error(self):
        """A CLAUDE.md that only mentions AGENTS.md in prose is an error, not a pass."""
        write(self.tmp_path / "pkg" / "AGENTS.md", "Rules for pkg.\n")
        write(self.tmp_path / "pkg" / "CLAUDE.md", "See AGENTS.md for the rules that apply here.\n")
        result, _ = run_checker_json(self.tmp_path)
        bridge_findings = findings_of(result, "bridge")
        self.assertEqual(len(bridge_findings), 1)
        self.assertEqual(bridge_findings[0]["severity"], "error")
        self.assertEqual(result["counts"]["error"], 1)

    def test_bridge_symlink_is_valid(self):
        if not can_symlink(self.tmp_path):
            self.skipTest("platform cannot create symlinks")
        pkg = self.mkdir()
        write(pkg / "AGENTS.md", "Rules for pkg.\n")
        (pkg / "CLAUDE.md").symlink_to("AGENTS.md")
        result, _ = run_checker_json(self.tmp_path)
        self.assertEqual(findings_of(result, "bridge"), [])
        self.assertEqual(findings_of(result, "size"), [])
        agents_entry = next(f for f in result["files"] if f["path"] == "pkg/AGENTS.md")
        self.assertEqual(agents_entry["bridge"], "symlink")
        claude_entry = next(f for f in result["files"] if f["path"] == "pkg/CLAUDE.md")
        self.assertEqual(claude_entry["bytes"], 0)
        self.assertEqual(claude_entry["status"], "ok")

    def test_broken_claude_symlink_is_a_finding_not_a_crash(self):
        if not can_symlink(self.tmp_path):
            self.skipTest("platform cannot create symlinks")
        pkg = self.mkdir()
        write(pkg / "AGENTS.md", "Rules for pkg.\n")
        (pkg / "CLAUDE.md").symlink_to("does-not-exist.md")
        result, raw = run_checker_json(self.tmp_path)
        self.assertEqual(raw.returncode, 1)
        bridge_findings = findings_of(result, "bridge")
        self.assertEqual(len(bridge_findings), 1)
        self.assertEqual(bridge_findings[0]["severity"], "error")

    def test_broken_agents_symlink_is_a_finding_not_a_crash(self):
        if not can_symlink(self.tmp_path):
            self.skipTest("platform cannot create symlinks")
        pkg = self.mkdir()
        (pkg / "AGENTS.md").symlink_to("does-not-exist.md")
        write(pkg / "CLAUDE.md", "@AGENTS.md\n")
        result, raw = run_checker_json(self.tmp_path)
        self.assertEqual(raw.returncode, 1)
        self.assertTrue(any("could not be read" in f["message"] for f in result["findings"]))

    def test_hook_exits_zero_even_with_broken_symlink(self):
        if not can_symlink(self.tmp_path):
            self.skipTest("platform cannot create symlinks")
        pkg = self.mkdir()
        (pkg / "AGENTS.md").symlink_to("does-not-exist.md")
        write(pkg / "CLAUDE.md", "@AGENTS.md\n")
        result = run_checker(self.tmp_path, "--hook")
        self.assertEqual(result.returncode, 0)

    def test_hook_exits_zero_on_usage_error(self):
        """--hook always exits 0, even when the run itself fails (here, a bad ROOT)."""
        result = run_checker(self.tmp_path / "does-not-exist", "--hook")
        self.assertEqual(result.returncode, 0)

    def test_hook_exits_zero_on_bad_argument(self):
        """A malformed flag fails in argparse, before the guarded run; --hook
        must still exit 0 so a typo in hooks.json cannot break a session."""
        result = run_checker(self.tmp_path, "--hook", "--stale-threshold", "oops")
        self.assertEqual(result.returncode, 0)
        self.assertIn("invalid int value", result.stderr)

    def test_bad_argument_without_hook_still_exits_two(self):
        """The --hook exception must not swallow every parse error."""
        result = run_checker(self.tmp_path, "--stale-threshold", "oops")
        self.assertEqual(result.returncode, 2)
        result = run_checker("--", "--hook", "extra")
        self.assertEqual(result.returncode, 2)

    @unittest.skipIf(not hasattr(os, "mkfifo"), "platform has no named pipes")
    def test_named_pipe_agents_md_is_a_finding_not_a_hang(self):
        """A FIFO named AGENTS.md stats fine but blocks forever on read. The
        checker must report it instead of hanging the session hook."""
        os.mkfifo(self.tmp_path / "AGENTS.md")
        write(self.tmp_path / "CLAUDE.md", "@AGENTS.md\n")
        try:
            result, raw = run_checker_json(self.tmp_path)
        except subprocess.TimeoutExpired:
            self.fail("checker hung on a named pipe")
        self.assertEqual(raw.returncode, 1)
        self.assertTrue(any("could not be read" in f["message"] for f in result["findings"]))

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "needs POSIX permissions as non-root")
    def test_unreadable_agents_md_is_a_finding_not_clean(self):
        """chmod 000 on AGENTS.md still stats, but Claude Code cannot load it.
        The checker must not certify it clean."""
        self.write_bridge()
        (self.tmp_path / "AGENTS.md").chmod(0)
        self.addCleanup((self.tmp_path / "AGENTS.md").chmod, 0o644)
        result, raw = run_checker_json(self.tmp_path)
        self.assertEqual(raw.returncode, 1)
        self.assertTrue(any("could not be read" in f["message"] for f in result["findings"]))

    @unittest.skipIf(os.name == "nt", "fix commands are POSIX shell")
    def test_fix_commands_quote_paths(self):
        """The suggested repair is meant to be pasted into a shell. A path
        with a space or shell metacharacter must be quoted, or the command
        writes to the wrong file. Both the create and the symlink repair
        are run for real to prove they touch only the intended file."""
        if not can_symlink(self.tmp_path):
            self.skipTest("platform cannot create symlinks")
        name = "my pkg; echo INJECTED #"
        create = self.tmp_path / name
        write(create / "AGENTS.md", "Rules.\n")
        relink = self.tmp_path / "re link"
        write(relink / "AGENTS.md", "Rules.\n")
        (relink / "CLAUDE.md").symlink_to("wrong.md")
        result, _ = run_checker_json(self.tmp_path)
        fixes = {f["path"]: f["fix"] for f in findings_of(result, "bridge")}
        self.assertEqual(len(fixes), 2)
        for fix in fixes.values():
            proc = subprocess.run(["/bin/sh", "-c", fix], cwd=self.tmp_path, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("INJECTED", proc.stdout)
        self.assertEqual((create / "CLAUDE.md").read_text(encoding="utf-8"), "@AGENTS.md\n")
        self.assertEqual(os.readlink(relink / "CLAUDE.md"), "AGENTS.md")
        self.assertFalse((self.tmp_path / "my").exists())
        result, raw = run_checker_json(self.tmp_path)
        self.assertEqual(findings_of(result, "bridge"), [])
        self.assertEqual(raw.returncode, 0)

    def test_gitignored_claude_md_is_still_a_valid_bridge(self):
        """A gitignored CLAUDE.md still exists on disk and Claude Code still
        loads it normally. It must not be reported as a missing bridge just
        because it was filtered out of the gitignore-aware scan list."""
        init_git_repo(self.tmp_path)
        write(self.tmp_path / ".gitignore", "CLAUDE.md\n")
        self.write_bridge()
        result, raw = run_checker_json(self.tmp_path)
        self.assertEqual(findings_of(result, "bridge"), [])
        self.assertEqual(result["counts"]["error"], 0)
        self.assertEqual(raw.returncode, 0)

    def test_dangling_bridge_import_is_an_error(self):
        """A CLAUDE.md that imports @AGENTS.md with no sibling AGENTS.md (left
        behind after deleting or renaming a nested AGENTS.md) is a broken
        import Claude Code will still try to load. This is the inverse of the
        bridge check, and must not be mistaken for a rival."""
        write(self.tmp_path / "pkg" / "CLAUDE.md", "@AGENTS.md\n")
        result, raw = run_checker_json(self.tmp_path)
        bridge_findings = findings_of(result, "bridge")
        self.assertEqual(len(bridge_findings), 1)
        self.assertEqual(bridge_findings[0]["severity"], "error")
        self.assertEqual(findings_of(result, "rival"), [])
        self.assertEqual(result["counts"]["error"], 1)
        self.assertEqual(raw.returncode, 1)

    def test_dangling_bridge_symlink_import_is_an_error(self):
        """Same as above, but the dangling import is a symlink named AGENTS.md
        rather than a regular file containing @AGENTS.md."""
        if not can_symlink(self.tmp_path):
            self.skipTest("platform cannot create symlinks")
        pkg = self.mkdir()
        (pkg / "CLAUDE.md").symlink_to("AGENTS.md")
        result, raw = run_checker_json(self.tmp_path)
        bridge_findings = findings_of(result, "bridge")
        self.assertEqual(len(bridge_findings), 1)
        self.assertEqual(bridge_findings[0]["severity"], "error")
        self.assertEqual(findings_of(result, "rival"), [])
        self.assertEqual(raw.returncode, 1)

    def test_import_of_agents_md_directory_is_an_error(self):
        """A directory named AGENTS.md exists on disk but cannot be imported.
        The bridge must not be certified clean because the name is taken."""
        (self.tmp_path / "AGENTS.md").mkdir()
        write(self.tmp_path / "CLAUDE.md", "@AGENTS.md\n")
        result, raw = run_checker_json(self.tmp_path)
        bridge_findings = findings_of(result, "bridge")
        self.assertEqual(len(bridge_findings), 1)
        self.assertEqual(bridge_findings[0]["severity"], "error")
        self.assertEqual(raw.returncode, 1)

    def test_gitignored_broken_agents_symlink_import_is_an_error(self):
        """A gitignored AGENTS.md is skipped by the scan, but if it is a broken
        symlink the sibling CLAUDE.md still imports nothing. Existence on
        disk is not enough; the import target must be readable."""
        if not can_symlink(self.tmp_path):
            self.skipTest("platform cannot create symlinks")
        init_git_repo(self.tmp_path)
        write(self.tmp_path / ".gitignore", "AGENTS.md\n")
        (self.tmp_path / "AGENTS.md").symlink_to("missing.md")
        write(self.tmp_path / "CLAUDE.md", "@AGENTS.md\n")
        result, raw = run_checker_json(self.tmp_path)
        bridge_findings = findings_of(result, "bridge")
        self.assertEqual(len(bridge_findings), 1)
        self.assertEqual(bridge_findings[0]["severity"], "error")
        self.assertEqual(raw.returncode, 1)

    def test_symlink_to_existing_non_sibling_agents_md_is_a_rival_not_broken(self):
        """A CLAUDE.md symlinked to an AGENTS.md in another directory loads
        fine, so it is not a broken import. With no sibling AGENTS.md it is
        an independent instruction file, measured by its target's size."""
        if not can_symlink(self.tmp_path):
            self.skipTest("platform cannot create symlinks")
        shared = self.mkdir("shared")
        self.write_bridge(shared, agents="x" * 5000)
        (self.tmp_path / "CLAUDE.md").symlink_to(Path("shared") / "AGENTS.md")
        result, raw = run_checker_json(self.tmp_path)
        self.assertEqual(findings_of(result, "bridge"), [])
        rival_findings = findings_of(result, "rival")
        self.assertEqual(len(rival_findings), 1)
        self.assertEqual(rival_findings[0]["path"], "CLAUDE.md")
        self.assertEqual(raw.returncode, 0)


# ---------------------------------------------------------------------------
# rival

class TestRival(CheckerTestCase):
    def test_rival_fires_over_300_bytes(self):
        write(self.tmp_path / "CLAUDE.md", "x" * 301)
        result, _ = run_checker_json(self.tmp_path)
        rival_findings = findings_of(result, "rival")
        self.assertEqual(len(rival_findings), 1)
        self.assertEqual(rival_findings[0]["severity"], "warning")
        self.assertEqual(result["counts"]["error"], 0)

    def test_rival_silent_under_300_bytes(self):
        write(self.tmp_path / "CLAUDE.md", "short notes\n")
        result, _ = run_checker_json(self.tmp_path)
        self.assertEqual(findings_of(result, "rival"), [])

    def test_rival_symlink_measures_resolved_target_size(self):
        """A CLAUDE.md symlinked to an unrelated file outside its own directory,
        with no sibling AGENTS.md, is exactly the independent instruction file
        the rival check exists to find. It must be measured by its resolved
        target's size, not reported as a free 0-byte bridge symlink."""
        if not can_symlink(self.tmp_path):
            self.skipTest("platform cannot create symlinks")
        write(self.tmp_path / "elsewhere.md", "x" * 5000)
        b = self.tmp_path / "b"
        b.mkdir()
        (b / "CLAUDE.md").symlink_to(self.tmp_path / "elsewhere.md")
        result, _ = run_checker_json(self.tmp_path)
        rival_findings = findings_of(result, "rival")
        self.assertEqual(len(rival_findings), 1)
        self.assertEqual(rival_findings[0]["severity"], "warning")
        claude_entry = next(f for f in result["files"] if f["path"] == "b/CLAUDE.md")
        self.assertEqual(claude_entry["bytes"], 5000)


# ---------------------------------------------------------------------------
# size

class TestSize(CheckerTestCase):
    def test_size_agents_warning_over_6000(self):
        self.write_bridge(agents="x" * 6001)
        result, _ = run_checker_json(self.tmp_path)
        size_findings = findings_of(result, "size")
        self.assertEqual(len(size_findings), 1)
        self.assertEqual(size_findings[0]["severity"], "warning")
        self.assertEqual(result["counts"]["error"], 0)

    def test_size_agents_ok_under_2000(self):
        self.write_bridge(agents="small and tidy\n")
        result, _ = run_checker_json(self.tmp_path)
        self.assertEqual(findings_of(result, "size"), [])
        agents_entry = next(f for f in result["files"] if f["path"] == "AGENTS.md")
        self.assertEqual(agents_entry["status"], "ok")

    def test_size_claude_bridge_info_over_300(self):
        self.write_bridge(claude="@AGENTS.md\n" + ("y" * 301))
        result, _ = run_checker_json(self.tmp_path)
        size_findings = findings_of(result, "size")
        self.assertEqual(len(size_findings), 1)
        self.assertEqual(size_findings[0]["severity"], "info")
        self.assertEqual(size_findings[0]["path"], "CLAUDE.md")
        self.assertEqual(result["counts"]["error"], 0)


# ---------------------------------------------------------------------------
# link

class TestLink(CheckerTestCase):
    def test_link_error_missing_target(self):
        self.write_bridge(agents="See [guide](docs/missing.md) for details.\n")
        result, _ = run_checker_json(self.tmp_path)
        link_findings = findings_of(result, "link")
        self.assertEqual(len(link_findings), 1)
        self.assertEqual(link_findings[0]["severity"], "error")
        self.assertEqual(result["counts"]["error"], 1)

    def test_link_negative_cases_produce_no_findings(self):
        write(self.tmp_path / "docs" / "real.md", "content\n")
        content = (
            "External: [site](https://example.com/page.md)\n"
            "Anchor only: [section](#usage)\n"
            "Mail: [me](mailto:a@b.com)\n"
            "No extension: [x](some/path)\n"
            "Backticked code that looks like a path: `docs/fake.md`\n"
            "Existing target: [real](docs/real.md)\n"
        )
        self.write_bridge(agents=content)
        result, _ = run_checker_json(self.tmp_path)
        self.assertEqual(findings_of(result, "link"), [])
        self.assertEqual(result["counts"]["error"], 0)

    def test_link_inside_fenced_code_blocks_is_ignored(self):
        """Link syntax shown as a documentation example, inside a fenced block,
        must never be treated as a real link, in either fence style."""
        content = (
            "Backtick fence example:\n"
            "```markdown\n"
            "[guide](docs/missing.md)\n"
            "```\n"
            "\n"
            "Tilde fence example:\n"
            "~~~markdown\n"
            "[other](also/missing.md)\n"
            "~~~\n"
        )
        self.write_bridge(agents=content)
        result, _ = run_checker_json(self.tmp_path)
        self.assertEqual(findings_of(result, "link"), [])
        self.assertEqual(result["counts"]["error"], 0)

    def test_percent_encoded_link_to_existing_file_is_not_an_error(self):
        """A markdown destination may be percent-encoded, so `docs/a%20b.md`
        points at the file `docs/a b.md`. The file is there, so nothing is
        broken and the documented CI check must not fail."""
        docs = self.mkdir("docs")
        write(docs / "setup guide.md", "How to set up.\n")
        self.write_bridge(agents="See [guide](docs/setup%20guide.md).\n")
        result, proc = run_checker_json(self.tmp_path)
        self.assertEqual(findings_of(result, "link"), [])
        self.assertEqual(result["counts"]["error"], 0)
        self.assertEqual(proc.returncode, 0)

    def test_percent_encoded_link_to_missing_file_is_still_an_error(self):
        """Decoding the destination must not blind the check to a real miss."""
        self.write_bridge(agents="See [guide](docs/setup%20guide.md).\n")
        result, _ = run_checker_json(self.tmp_path)
        self.assertEqual(len(findings_of(result, "link")), 1)
        self.assertEqual(result["counts"]["error"], 1)

    def test_symlink_bridge_does_not_double_report_broken_links(self):
        """A CLAUDE.md symlinked to its sibling AGENTS.md has identical content
        to that AGENTS.md. A broken link in it must be reported once, not once
        per path that resolves to the same real file."""
        if not can_symlink(self.tmp_path):
            self.skipTest("platform cannot create symlinks")
        a = self.tmp_path / "a"
        a.mkdir()
        write(a / "AGENTS.md", "See [guide](docs/missing.md) for details.\n")
        (a / "CLAUDE.md").symlink_to("AGENTS.md")
        result, _ = run_checker_json(self.tmp_path)
        link_findings = findings_of(result, "link")
        self.assertEqual(len(link_findings), 1)
        self.assertEqual(link_findings[0]["path"], "a/AGENTS.md")
        self.assertEqual(result["counts"]["error"], 1)


# ---------------------------------------------------------------------------
# gitignore

class TestGitignore(CheckerTestCase):
    def test_gitignore_filters_non_ascii_path(self):
        init_git_repo(self.tmp_path)
        write(self.tmp_path / ".gitignore", "scratch/\n")
        write(self.tmp_path / "scratch" / "café" / "AGENTS.md", "ignored rules\n")
        self.write_bridge()
        result, _ = run_checker_json(self.tmp_path)
        agents_paths = [f["path"] for f in result["files"] if f["bridge"] is not None]
        self.assertEqual(agents_paths, ["AGENTS.md"])
        self.assertEqual(result["counts"]["error"], 0)

    def test_gitignore_filters_newline_path(self):
        init_git_repo(self.tmp_path)
        write(self.tmp_path / ".gitignore", "scratch/\n")
        write(self.tmp_path / "scratch" / "wei\nrd" / "AGENTS.md", "ignored rules\n")
        self.write_bridge()
        result, _ = run_checker_json(self.tmp_path)
        agents_paths = [f["path"] for f in result["files"] if f["bridge"] is not None]
        self.assertEqual(agents_paths, ["AGENTS.md"])
        self.assertEqual(result["counts"]["error"], 0)


# ---------------------------------------------------------------------------
# stale

class TestStale(CheckerTestCase):
    def test_stale_fires_over_threshold(self):
        init_git_repo(self.tmp_path)
        self.write_bridge()
        git_commit(self.tmp_path, "add docs")
        for name in ("a", "b", "c"):
            write(self.tmp_path / "src" / f"{name}.txt", name)
            git_commit(self.tmp_path, f"add {name}")
        result, _ = run_checker_json(self.tmp_path, "--stale-threshold", "2")
        stale_findings = findings_of(result, "stale")
        self.assertEqual(len(stale_findings), 1)
        self.assertEqual(stale_findings[0]["severity"], "info")
        self.assertIs(result["stale"]["checked"], True)
        self.assertEqual(result["stale"]["commits_since_docs"], 3)
        self.assertEqual(result["stale"]["threshold"], 2)
        self.assertEqual(result["counts"]["error"], 0)

    def test_stale_silent_under_threshold(self):
        init_git_repo(self.tmp_path)
        self.write_bridge()
        git_commit(self.tmp_path, "add docs")
        write(self.tmp_path / "src" / "a.txt", "a")
        git_commit(self.tmp_path, "add a")
        result, _ = run_checker_json(self.tmp_path, "--stale-threshold", "5")
        self.assertEqual(findings_of(result, "stale"), [])
        self.assertIs(result["stale"]["checked"], True)
        self.assertEqual(result["stale"]["commits_since_docs"], 1)

    def test_commits_touching_other_files_matches_naive_count(self):
        """The single git-log-pass counter must count exactly what the original
        one-subprocess-per-commit approach would: a commit counts when it touched
        at least one tracked file that is not in doc_set and not under docs/.
        """
        doc_set = {"AGENTS.md", "CLAUDE.md"}
        commits = [
            ("h1", ["AGENTS.md"]),                  # doc-only: must not count
            ("h2", ["src/a.py"]),                   # code-only: must count
            ("h3", ["docs/notes.md", "src/b.py"]),  # mixed: must count
            ("h4", ["docs/notes.md"]),              # doc-only, under docs/: must not count
            ("h5", []),                             # empty commit: must not count
            ("h6", ["src/c.py", "CLAUDE.md"]),      # mixed: must count
        ]
        log_output = "".join(
            "\x00" + h + "\n" + "\n".join(files) + ("\n" if files else "")
            for h, files in commits
        )
        naive_count = sum(
            1
            for _, files in commits
            if any(f not in doc_set and not f.startswith("docs/") for f in files)
        )
        self.assertEqual(naive_count, 3)  # h2, h3, h6
        self.assertEqual(
            CHECK.commits_touching_other_files(log_output, doc_set, "docs/"), naive_count
        )

    def test_stale_skipped_when_not_a_git_repo(self):
        self.write_bridge()
        result, raw = run_checker_json(self.tmp_path)
        self.assertEqual(raw.returncode, 0)
        self.assertEqual(result["stale"], {"checked": False})
        self.assertEqual(findings_of(result, "stale"), [])

    def test_stale_skipped_when_no_commits(self):
        init_git_repo(self.tmp_path)
        self.write_bridge()
        result, raw = run_checker_json(self.tmp_path)
        self.assertEqual(raw.returncode, 0)
        self.assertEqual(result["stale"], {"checked": False})

    def test_stale_scopes_to_root_when_root_is_a_subdirectory(self):
        """git reports changed files relative to the repo root, not to ROOT.
        Commits that only touch a top-level docs/ outside ROOT's own subtree
        are not ROOT's own docs, and must still count toward ROOT's staleness,
        not be silently swallowed by a bare "docs/" prefix check."""
        init_git_repo(self.tmp_path)
        self.write_bridge(self.tmp_path / "sub")
        git_commit(self.tmp_path, "add sub docs")
        for name in ("a", "b", "c"):
            write(self.tmp_path / "docs" / f"{name}.md", name)
            git_commit(self.tmp_path, f"top-level docs {name}")
        result, _ = run_checker_json(self.tmp_path / "sub", "--stale-threshold", "0")
        self.assertIs(result["stale"]["checked"], True)
        self.assertEqual(result["stale"]["commits_since_docs"], 3)
        stale_findings = findings_of(result, "stale")
        self.assertEqual(len(stale_findings), 1)
        self.assertEqual(stale_findings[0]["severity"], "info")

    def test_stale_skipped_in_shallow_clone(self):
        """A shallow clone (fetch-depth: 1, as actions/checkout@v4 defaults to)
        cannot answer "commits since docs last changed" at all: reporting
        nothing is correct, reporting a confident zero is a lie."""
        source = self.mkdir("source")
        init_git_repo(source)
        self.write_bridge(source)
        git_commit(source, "add docs")
        write(source / "src" / "a.txt", "a")
        git_commit(source, "add a")

        shallow = self.tmp_path / "shallow"
        # --depth is silently ignored for a plain local-path clone; file:// forces
        # git to treat it as a real transport, so the clone is actually shallow.
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "file://" + str(source), str(shallow)],
            capture_output=True, text=True,
        )
        self.assertEqual(clone.returncode, 0, clone.stdout + clone.stderr)

        result, raw = run_checker_json(shallow)
        self.assertEqual(raw.returncode, 0)
        self.assertEqual(result["stale"], {"checked": False})
        self.assertEqual(findings_of(result, "stale"), [])


# ---------------------------------------------------------------------------
# exit codes

class TestExitCodes(CheckerTestCase):
    def test_exit_code_0_when_clean(self):
        self.write_bridge()
        result = run_checker(self.tmp_path)
        self.assertEqual(result.returncode, 0)

    def test_exit_code_1_when_error_finding(self):
        write(self.tmp_path / "pkg" / "AGENTS.md", "Rules.\n")
        result = run_checker(self.tmp_path)
        self.assertEqual(result.returncode, 1)

    def test_exit_code_2_on_usage_error(self):
        result = run_checker(self.tmp_path / "does-not-exist")
        self.assertEqual(result.returncode, 2)


# ---------------------------------------------------------------------------
# --hook

class TestHook(CheckerTestCase):
    def test_hook_silent_when_clean(self):
        self.write_bridge()
        result = run_checker(self.tmp_path, "--hook")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_hook_payload_when_not_clean(self):
        write(self.tmp_path / "pkg" / "AGENTS.md", "Rules.\n")
        result = run_checker(self.tmp_path, "--hook")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        self.assertTrue(len(output["additionalContext"]) < 600)
        self.assertIn("repo-docs", output["additionalContext"])


# ---------------------------------------------------------------------------
# --json shape

class TestJsonShape(CheckerTestCase):
    def test_json_output_has_documented_keys(self):
        self.write_bridge()
        result, _ = run_checker_json(self.tmp_path)
        self.assertEqual(
            set(result.keys()), {"root", "ok", "counts", "findings", "files", "stale"}
        )
        self.assertEqual(set(result["counts"].keys()), {"error", "warning", "info"})
        for entry in result["files"]:
            self.assertEqual(set(entry.keys()), {"path", "bytes", "status", "bridge"})
            self.assertIn(entry["status"], ("ok", "info", "warning"))


# ---------------------------------------------------------------------------
# real repo

class TestRealRepo(unittest.TestCase):
    def test_real_repo_root_is_clean(self):
        if not (REPO_ROOT / "AGENTS.md").exists():
            self.skipTest("this repo's own AGENTS.md has not been written yet")
        result = run_checker(REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
