#!/usr/bin/env python3
"""
Negative tests for the validate-packaging.py validator logic.

Each test invokes the validator as a subprocess against a temporary
repository structure and asserts a nonzero exit (failure).
"""
import os
import sys
import subprocess
import tempfile
import shutil
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VALIDATOR = os.path.join(REPO_ROOT, "scripts", "validate-packaging.py")


def run_validator(repo_dir):
    """Run validate-packaging.py in repo_dir and return (exit_code, stdout)."""
    # Copy the validator into the temp repo so its __file__-based
    # REPO_ROOT resolves inside the temp structure.
    validator_copy = os.path.join(repo_dir, "scripts", "validate-packaging.py")
    shutil.copy(VALIDATOR, validator_copy)

    result = subprocess.run(
        [sys.executable, validator_copy],
        cwd=repo_dir,
        text=True,
        capture_output=True,
        timeout=30,
    )
    return result.returncode, result.stdout + result.stderr


def create_minimal_repo(tmpdir):
    """Create a minimal valid repo structure so the validator can run."""
    # SKILL.md
    skill = """---
name: frontend-slides
description: Create HTML presentations.
---

# Frontend Slides

## Mode C: Enhancement

Before modifying an existing deck, read `references/iterative-editing.md`.

Read `references/visual-verification.md` and complete its validation loop
before declaring the change finished.

## Supporting Files

| File | Purpose | When to Read |
|------|---------|-------------|
| [references/iterative-editing.md](references/iterative-editing.md) | Editing guide | Mode C |
| [references/visual-verification.md](references/visual-verification.md) | Verification loop | Mode C |
| [STYLE_PRESETS.md](STYLE_PRESETS.md) | Presets | Phase 2 |
"""
    with open(os.path.join(tmpdir, "SKILL.md"), "w") as f:
        f.write(skill)

    # README.md
    readme = """# Frontend Slides

## Installation

### Via Claude Code

```text
/plugin marketplace add https://github.com/naototachibana/frontend-slides-loop
```

### Manual

```bash
git clone https://github.com/naototachibana/frontend-slides-loop.git ~/.claude/skills/frontend-slides
```

## Credits

Created by [@zarazhangrui](https://github.com/zarazhangrui).
"""
    with open(os.path.join(tmpdir, "README.md"), "w") as f:
        f.write(readme)

    # references/
    ref_dir = os.path.join(tmpdir, "references")
    os.makedirs(ref_dir, exist_ok=True)

    ie = """# Iterative Slide Editing

## 8. Splitting and merging

**Split** when content exceeds the authored stage content area.
This is an objective defect — content must never overflow.

The following are **diagnostic heuristics**:

- If a text column has fewer than roughly 12 CJK characters.

## 9. Legacy numbered decks

### Collision-safe renumbering

Use a **three-pass** replacement:

```
pass A: prefix every old numbered pattern with a unique marker,
         e.g. `.slide-05` → `.slide-__OLD_05__`
pass B: replace the marker + old number with the new number
pass C: clean up any unreplaced markers as errors
```

### Verification after renumbering

```bash
grep -oP 'data-slide-id="[^"]*"' deck.html | sort | uniq -d
grep -oP '<section[^>]*class="[^"]*slide-\\d+"[^>]*>' deck.html
grep -Pc 'slide-\\d'
# Also supports \d{2} for 2-digit slide numbers
```

### Zero-padded numbers

Support at least 8, 12, and 20 slides. Use 02d format.

## 10. Rollback checkpoints

Before any structural operation, save a backup.
"""
    with open(os.path.join(ref_dir, "iterative-editing.md"), "w") as f:
        f.write(ie)

    vv = """# Visual Verification

## 0. Local preview setup

```bash
DECK_DIR="/path/to/deck/directory"
PORT=8000
cd "$DECK_DIR"
python3 -m http.server "$PORT" --bind 127.0.0.1 >preview-server.log 2>&1 &
PREVIEW_PID=$!
if curl --fail --silent --show-error "http://127.0.0.1:$PORT/index.html" >/dev/null; then
  echo "Server is ready"
fi
kill "$PREVIEW_PID" 2>/dev/null || true
```
"""
    with open(os.path.join(ref_dir, "visual-verification.md"), "w") as f:
        f.write(vv)

    # scripts/ — minimal stub for test to pass
    scripts_dir = os.path.join(tmpdir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    test_stub = """#!/usr/bin/env python3
import unittest
class TestStub(unittest.TestCase):
    def test_pass(self):
        self.assertTrue(True)
if __name__ == "__main__":
    unittest.main()
"""
    with open(os.path.join(scripts_dir, "test-renumbering.py"), "w") as f:
        f.write(test_stub)

    # Stub files that the validator expects to exist
    for fname in ["STYLE_PRESETS.md", "animation-patterns.md", "html-template.md",
                  "viewport-base.css"]:
        with open(os.path.join(tmpdir, fname), "w") as f:
            f.write(f"# {fname}\n")

    # bold-template-pack stub
    btp = os.path.join(tmpdir, "bold-template-pack")
    os.makedirs(btp, exist_ok=True)
    with open(os.path.join(btp, "selection-index.json"), "w") as f:
        f.write('{"templates": []}\n')

    # Plugin mirror
    plugin_skill_dir = os.path.join(
        tmpdir, "plugins", "frontend-slides", "skills", "frontend-slides"
    )
    os.makedirs(plugin_skill_dir, exist_ok=True)
    # scripts/ in plugin
    os.makedirs(os.path.join(plugin_skill_dir, "scripts"), exist_ok=True)

    shutil.copy(
        os.path.join(tmpdir, "SKILL.md"),
        os.path.join(plugin_skill_dir, "SKILL.md"),
    )
    plugin_ref_dir = os.path.join(plugin_skill_dir, "references")
    os.makedirs(plugin_ref_dir, exist_ok=True)
    shutil.copy(
        os.path.join(ref_dir, "iterative-editing.md"),
        os.path.join(plugin_ref_dir, "iterative-editing.md"),
    )
    shutil.copy(
        os.path.join(ref_dir, "visual-verification.md"),
        os.path.join(plugin_ref_dir, "visual-verification.md"),
    )

    # Copy stub files to plugin
    for fname in ["STYLE_PRESETS.md", "animation-patterns.md", "html-template.md",
                  "viewport-base.css"]:
        shutil.copy(
            os.path.join(tmpdir, fname),
            os.path.join(plugin_skill_dir, fname),
        )
    # Copy scripts/* that exist
    for fname in os.listdir(os.path.join(tmpdir, "scripts")):
        shutil.copy(
            os.path.join(tmpdir, "scripts", fname),
            os.path.join(plugin_skill_dir, "scripts", fname),
        )

    # Final sync pass — ensure plugin and root reference files match exactly
    for fname in os.listdir(ref_dir):
        shutil.copy(
            os.path.join(ref_dir, fname),
            os.path.join(plugin_ref_dir, fname),
        )
    # Also re-sync SKILL.md and bold-template-pack
    shutil.copy(
        os.path.join(tmpdir, "SKILL.md"),
        os.path.join(plugin_skill_dir, "SKILL.md"),
    )
    plugin_btp = os.path.join(plugin_skill_dir, "bold-template-pack")
    os.makedirs(plugin_btp, exist_ok=True)
    shutil.copy(
        os.path.join(btp, "selection-index.json"),
        os.path.join(plugin_btp, "selection-index.json"),
    )


class TestValidatorNegative(unittest.TestCase):
    """Each test corrupts the minimal repo and asserts validator failure."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        create_minimal_repo(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _add_malformed_marketplace(self):
        """Replace valid marketplace command with leading-pipe version."""
        readme = os.path.join(self.tmpdir, "README.md")
        with open(readme) as f:
            content = f.read()
        content = content.replace(
            "/plugin marketplace add https://github.com/naototachibana/frontend-slides-loop",
            "|/plugin marketplace add https://github.com/naototachibana/frontend-slides-loop",
        )
        with open(readme, "w") as f:
            f.write(content)

    def _add_upstream_install_url(self):
        readme = os.path.join(self.tmpdir, "README.md")
        with open(readme) as f:
            content = f.read()
        # Replace the fork clone URL with upstream in an install context
        content = content.replace(
            "git clone https://github.com/naototachibana/frontend-slides-loop.git",
            "git clone https://github.com/zarazhangrui/frontend-slides.git",
        )
        with open(readme, "w") as f:
            f.write(content)

    def _add_pkill(self):
        vv = os.path.join(self.tmpdir, "references", "visual-verification.md")
        with open(vv) as f:
            content = f.read()
        content = content.replace(
            'kill "$PREVIEW_PID"',
            "pkill -f http.server",
        )
        with open(vv, "w") as f:
            f.write(content)

    def _add_basic_grep(self):
        ie = os.path.join(self.tmpdir, "references", "iterative-editing.md")
        with open(ie) as f:
            content = f.read()
        content = content.replace("grep -Pc", "grep -c")
        with open(ie, "w") as f:
            f.write(content)

    def _add_automatic_split_threshold(self):
        ie = os.path.join(self.tmpdir, "references", "iterative-editing.md")
        with open(ie) as f:
            content = f.read()
        content = content.replace(
            "**diagnostic heuristics**",
            "automatic split conditions",
        )
        with open(ie, "w") as f:
            f.write(content)

    def _break_root_plugin_sync(self):
        """Make root and plugin references differ."""
        ie = os.path.join(self.tmpdir, "references", "iterative-editing.md")
        with open(ie, "a") as f:
            f.write("\n\nRoot-only content.\n")

    def _add_stale_workflow_ref(self):
        readme = os.path.join(self.tmpdir, "README.md")
        with open(readme) as f:
            content = f.read()
        content += "\nSee iterative-slide-workflow.md for details.\n"
        with open(readme, "w") as f:
            f.write(content)

    def _remove_test_file(self):
        os.remove(
            os.path.join(self.tmpdir, "scripts", "test-renumbering.py")
        )

    # --- Tests ---

    def test_validator_rejects_malformed_marketplace(self):
        self._add_malformed_marketplace()
        rc, _ = run_validator(self.tmpdir)
        self.assertNotEqual(rc, 0, "Validator should reject leading-pipe command")

    def test_validator_rejects_upstream_install_url(self):
        self._add_upstream_install_url()
        rc, _ = run_validator(self.tmpdir)
        self.assertNotEqual(rc, 0, "Validator should reject upstream install URL")

    def test_validator_rejects_pkill(self):
        self._add_pkill()
        rc, _ = run_validator(self.tmpdir)
        self.assertNotEqual(rc, 0, "Validator should reject pkill -f")

    def test_validator_rejects_basic_grep(self):
        self._add_basic_grep()
        rc, _ = run_validator(self.tmpdir)
        self.assertNotEqual(rc, 0, "Validator should reject bare \\d grep")

    def test_validator_rejects_automatic_split(self):
        self._add_automatic_split_threshold()
        rc, _ = run_validator(self.tmpdir)
        self.assertNotEqual(rc, 0, "Validator should reject automatic split rules")

    def test_validator_rejects_root_plugin_divergence(self):
        self._break_root_plugin_sync()
        rc, _ = run_validator(self.tmpdir)
        self.assertNotEqual(rc, 0, "Validator should reject root/plugin divergence")

    def test_validator_rejects_stale_workflow_ref(self):
        self._add_stale_workflow_ref()
        rc, _ = run_validator(self.tmpdir)
        self.assertNotEqual(rc, 0, "Validator should reject stale iterative-slide-workflow.md ref")

    def test_validator_rejects_missing_tests(self):
        self._remove_test_file()
        rc, _ = run_validator(self.tmpdir)
        self.assertNotEqual(rc, 0, "Validator should reject missing test file")

    def test_validator_accepts_clean_repo(self):
        """Sanity check: the minimal repo should pass all checks."""
        rc, output = run_validator(self.tmpdir)
        self.assertEqual(rc, 0, f"Clean repo should pass. Output: {output[:500]}")


if __name__ == "__main__":
    unittest.main()
