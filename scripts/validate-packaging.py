#!/usr/bin/env python3
"""
validate-packaging.py — verify that the frontend-slides skill packaging
is self-consistent.

Checks:
1. Every Markdown file referenced by each installed SKILL.md exists.
2. Root and packaged skill files are synchronized (same content).
3. Required iterative-editing and visual-verification references are
   included in the installed plugin.
4. The obsolete root 'iterative-slide-workflow.md' is no longer referenced.
5. README installation examples point to the intended repository fork.
6. No instructional example contains 'git push origin main'.
7. No broad staging example uses 'git add .' / 'git add -A' / uninspected
   asset directory.
8. No workflow claims universal compatibility with arbitrary 1920×1080
   HTML decks (claims specific to Frontend Slides are accepted).
9. Numbered-slide examples and regexes work for 8, 12, and 20 slides.
|10. Reference links remain relative and use shallow, directly discoverable
|    paths.
|11. Marketplace command syntax (no leading |).
|12. No 'pkill -f' in references (PID-scoped cleanup).
|13. Split rules use heuristics, not automatic thresholds.
|14. grep flavor correctness (no bare \\d without -P or -E in bash).
|15. Fixture tests exist for numbered-slide operations.
|
|Exit 0 on success, non-zero on failure.
"""

import os
import re
import sys
import filecmp
import subprocess

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILL_MD = os.path.join(REPO_ROOT, "SKILL.md")
PLUGIN_SKILL_MD = os.path.join(
    REPO_ROOT,
    "plugins/frontend-slides/skills/frontend-slides/SKILL.md",
)
REF_DIR = os.path.join(REPO_ROOT, "references")
PLUGIN_REF_DIR = os.path.join(
    REPO_ROOT,
    "plugins/frontend-slides/skills/frontend-slides/references",
)
README_MD = os.path.join(REPO_ROOT, "README.md")

errors = []


def err(msg):
    errors.append(f"FAIL: {msg}")


# ---------------------------------------------------------------------------
# 1. Every Markdown file referenced by SKILL.md exists
# ---------------------------------------------------------------------------
def extract_referenced_paths(skill_path):
    """Return relative paths referenced in the SKILL.md table and inline links."""
    paths = set()
    with open(skill_path) as f:
        text = f.read()

    # Table rows: [...](path)
    for m in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', text):
        path = m.group(2)
        if path.endswith(".md") or path.endswith(".css") or path.endswith(".json"):
            paths.add(path)

    # Inline references like: `references/iterative-editing.md`
    for m in re.finditer(r'`([^`]+\.md)`', text):
        path = m.group(1)
        if "/" in path:
            paths.add(path)

    return paths


print("--- Check 1: SKILL.md references exist ---")
refs = extract_referenced_paths(SKILL_MD)
for ref in sorted(refs):
    target = os.path.join(REPO_ROOT, ref)
    if not os.path.exists(target):
        err(f"SKILL.md references {ref} but file not found at {target}")
    else:
        print(f"  OK: {ref}")

# Also check plugin SKILL.md
print("--- Check 1b: Plugin SKILL.md references exist ---")
plugin_refs = extract_referenced_paths(PLUGIN_SKILL_MD)
for ref in sorted(plugin_refs):
    # Plugin paths are relative to the plugin skill directory
    plugin_skill_dir = os.path.dirname(PLUGIN_SKILL_MD)
    target = os.path.join(plugin_skill_dir, ref)
    if not os.path.exists(target):
        err(f"Plugin SKILL.md references {ref} but file not found at {target}")
    else:
        print(f"  OK: {ref} (plugin)")

# ---------------------------------------------------------------------------
# 2. Root and packaged skill files are synchronized
# ---------------------------------------------------------------------------
print("\n--- Check 2: Root ↔ Plugin sync ---")
if os.path.exists(SKILL_MD) and os.path.exists(PLUGIN_SKILL_MD):
    if filecmp.cmp(SKILL_MD, PLUGIN_SKILL_MD, shallow=False):
        print("  OK: SKILL.md identical")
    else:
        err("SKILL.md differs between root and plugin")
else:
    err("SKILL.md missing from root or plugin")

# Reference files sync
if os.path.isdir(REF_DIR) and os.path.isdir(PLUGIN_REF_DIR):
    root_files = set(os.listdir(REF_DIR))
    plugin_files = set(os.listdir(PLUGIN_REF_DIR))
    if root_files != plugin_files:
        err(f"Reference file sets differ: root={root_files}, plugin={plugin_files}")
    else:
        for fname in root_files:
            root_f = os.path.join(REF_DIR, fname)
            plugin_f = os.path.join(PLUGIN_REF_DIR, fname)
            if filecmp.cmp(root_f, plugin_f, shallow=False):
                print(f"  OK: references/{fname} identical")
            else:
                err(f"references/{fname} differs between root and plugin")
else:
    err("Reference directory missing from root or plugin")

# ---------------------------------------------------------------------------
# 3. Required iterative-editing and visual-verification refs included
# ---------------------------------------------------------------------------
print("\n--- Check 3: Required reference files ---")
for fname in ["iterative-editing.md", "visual-verification.md"]:
    root_path = os.path.join(REF_DIR, fname)
    plugin_path = os.path.join(PLUGIN_REF_DIR, fname)
    if os.path.exists(root_path):
        print(f"  OK: references/{fname} (root)")
    else:
        err(f"references/{fname} missing from root")
    if os.path.exists(plugin_path):
        print(f"  OK: references/{fname} (plugin)")
    else:
        err(f"references/{fname} missing from plugin")

# ---------------------------------------------------------------------------
# 4. No reference to obsolete iterative-slide-workflow.md
# ---------------------------------------------------------------------------
print("\n--- Check 4: No obsolete file references ---")
files_to_scan = [SKILL_MD, README_MD, os.path.join(REPO_ROOT, "SKILL.md")]
for fpath in files_to_scan:
    if not os.path.exists(fpath):
        continue
    with open(fpath) as f:
        content = f.read()
    if "iterative-slide-workflow.md" in content:
        # The git rm record in the diff or commit message is fine
        # Check that it's not in current active instructions
        # (commit messages and diff comments are excluded)
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if "iterative-slide-workflow.md" in line and not line.strip().startswith("#") and "removed" not in line.lower():
                err(f"{os.path.basename(fpath)}:{i} still references iterative-slide-workflow.md: {line.strip()}")
                break
        else:
            print(f"  OK: {os.path.basename(fpath)} (only commit/removal references)")
    else:
        print(f"  OK: {os.path.basename(fpath)} — no obsolete reference")

# Also check root directory
if os.path.exists(os.path.join(REPO_ROOT, "iterative-slide-workflow.md")):
    err("iterative-slide-workflow.md still exists at root level")

# ---------------------------------------------------------------------------
# 5. README installation consistency
# ---------------------------------------------------------------------------
print("\\n--- Check 5: README installation URLs point to fork ---")
if os.path.exists(README_MD):
    with open(README_MD) as f:
        readme = f.read()

    # Collect all GitHub URLs from the README
    github_urls = re.findall(
        r'https://github\.com/[\w.-]+/[\w.-]+',
        readme
    )

    install_urls = []
    attribution_urls = []

    for url in sorted(set(github_urls)):
        # URLs inside attribution / upstream / credits context
        # Check only the line the URL appears on plus previous line
        # to avoid false attribution from nearby sections.
        url_line = None
        for i, line in enumerate(readme.split("\n")):
            if url in line:
                url_line = i
                break
        if url_line is not None:
            lines = readme.split("\n")
            check_text = " ".join(lines[max(0, url_line-1):url_line+1]).lower()
            if any(ctx in check_text for ctx in ["upstream", "attribution", "credit", "originate"]):
                attribution_urls.append(url)
            else:
                install_urls.append(url)
        else:
            install_urls.append(url)

    # Check that INSTALL urls point to the fork
    fork_url = "naototachibana/frontend-slides-loop"
    upstream_url = "zarazhangrui/frontend-slides"

    install_fail = False
    for url in install_urls:
        if fork_url in url:
            print(f"  OK: {url}")
        elif upstream_url in url:
            err(f"Install URL still points to upstream: {url}")
            install_fail = True
        else:
            pass  # non-GitHub URLs, fine

    # Also check the marketplace install command
    if "/plugin marketplace add" in readme and fork_url not in readme[readme.index("/plugin marketplace add"):readme.index("/plugin marketplace add")+200]:
        err("Marketplace install command does not point to fork")

    if not install_fail:
        print("  OK: All install URLs point to the fork")

# ---------------------------------------------------------------------------
# 6. No 'git push origin main'
# ---------------------------------------------------------------------------
print("\n--- Check 6: No unsafe git push ---")
for fpath in [SKILL_MD, README_MD]:
    if not os.path.exists(fpath):
        continue
    with open(fpath) as f:
        content = f.read()
    if 'git push origin main' in content:
        err(f"{os.path.basename(fpath)} contains 'git push origin main'")
    else:
        print(f"  OK: {os.path.basename(fpath)} — no 'git push origin main'")

# ---------------------------------------------------------------------------
# 7. No broad staging
# ---------------------------------------------------------------------------
print("\n--- Check 7: No unsafe broad staging ---")
for fpath in [SKILL_MD, README_MD]:
    if not os.path.exists(fpath):
        continue
    with open(fpath) as f:
        content = f.read()
    found_broad = False
    for pattern in ["git add .", "git add -A", "git add --all"]:
        if pattern in content:
            err(f"{os.path.basename(fpath)} contains '{pattern}'")
            found_broad = True
    if not found_broad:
        print(f"  OK: {os.path.basename(fpath)} — no broad staging examples")

# ---------------------------------------------------------------------------
# 8. No universal-claim statements
# ---------------------------------------------------------------------------
print("\n--- Check 8: Scope claims ---")
for fpath in [SKILL_MD, os.path.join(REF_DIR, "iterative-editing.md"),
              os.path.join(REF_DIR, "visual-verification.md")]:
    if not os.path.exists(fpath):
        continue
    with open(fpath) as f:
        content = f.read()
    universal_phrases = [
        "any 1920×1080",
        "any fixed-stage",
        "any HTML deck",
        "applies to all",
        "works with any",
    ]
    found_universal = False
    for phrase in universal_phrases:
        if phrase.lower() in content.lower():
            # Check context — phrases like "Frontend Slides-compatible" are OK
            line_with_phrase = [l for l in content.split("\n") if phrase.lower() in l.lower()]
            for line in line_with_phrase:
                if "Frontend Slides" not in line and "detect" not in line.lower():
                    err(f"{os.path.basename(fpath)}: universal claim '{phrase}' in: {line.strip()[:80]}")
                    found_universal = True
    if not found_universal:
        print(f"  OK: {os.path.basename(fpath)} — scope appropriately bounded")

# ---------------------------------------------------------------------------
# 9. Numbered-slide examples and regexes work for 8, 12, 20 slides
# ---------------------------------------------------------------------------
print("\\n--- Check 9: Numbered-slide handling (documentation patterns) ---")
ref_path = os.path.join(REF_DIR, "iterative-editing.md")
if os.path.exists(ref_path):
    with open(ref_path) as f:
        content = f.read()
    # Check that the three-pass algorithm is documented
    if "__OLD_" in content:
        print("  OK: collision-safe three-pass algorithm documented")
    else:
        err("iterative-editing.md missing three-pass collision-safe algorithm")

    # Check that zero-padded numbers are mentioned
    if "zero-pad" in content.lower() or "02d" in content:
        print("  OK: zero-padded numbering mentioned")
    else:
        err("iterative-editing.md missing zero-padded numbering guidance")

    # Check the verification commands support 2-digit slide numbers
    if r"\d{2}" in content and r"\d+" in content:
        print("  OK: verification patterns use \\d+ and \\d{2} (supports 20+ slides)")
    else:
        err("iterative-editing.md verification commands may not work for 20+ slides")

    # Check that no single-digit-only grep patterns exist
    single_digit_patterns = re.findall(r'slide-0\[1-9\]|0\[0-9\]|\\\\d\(?!\+\)', content)
    single_digit_lines = [l.strip() for l in content.split("\\n")
                          if "slide-0[1-9]" in l or "SLIDE 0" in l]
    if single_digit_lines:
        # Only flag if used as an active example (not in warnings)
        for line in single_digit_lines:
            if "warn" not in line.lower() and "avoid" not in line.lower() and "do not" not in line.lower():
                err(f"iterative-editing.md uses single-digit-only pattern: {line[:60]}")
                break
        else:
            print("  OK: single-digit patterns only in warning/avoidance context")
    else:
        print("  OK: no single-digit-only grep patterns")

    # Note: Executable fixture tests verify these operations end-to-end.
    # See scripts/test-renumbering.py.

# ---------------------------------------------------------------------------
# 10. Relative link paths
# ---------------------------------------------------------------------------
print("\n--- Check 10: Relative link paths ---")
for fpath in [SKILL_MD, README_MD,
              os.path.join(REF_DIR, "iterative-editing.md"),
              os.path.join(REF_DIR, "visual-verification.md")]:
    if not os.path.exists(fpath):
        continue
    with open(fpath) as f:
        content = f.read()
    for m in re.finditer(r'\(([^)]+\.md)\)', content):
        link = m.group(1)
        if link.startswith("http://") or link.startswith("https://"):
            continue
        if link.startswith("#"):
            continue
        # Resolve relative to the file's directory
        base_dir = os.path.dirname(fpath)
        target = os.path.normpath(os.path.join(base_dir, link))
        if not os.path.exists(target):
            err(f"{os.path.basename(fpath)}: broken relative link '{link}' → {target}")
        else:
            pass  # OK, silent for clean output

# ---------------------------------------------------------------------------
# 11. Valid marketplace command (no leading |)
# ---------------------------------------------------------------------------
print("\n--- Check 11: Marketplace command syntax ---")
if os.path.exists(README_MD):
    with open(README_MD) as f:
        readme = f.read()
    pipe_commands = re.findall(r'^\s*\|/plugin marketplace add', readme, re.MULTILINE)
    if pipe_commands:
        err(f"README has {len(pipe_commands)} marketplace command(s) with leading pipe: {pipe_commands}")
    else:
        print("  OK: No leading-pipe marketplace commands")

    # Also verify the exact expected command exists
    valid_cmd = "/plugin marketplace add https://github.com/naototachibana/frontend-slides-loop"
    if valid_cmd in readme:
        print(f"  OK: Valid marketplace command found")
    else:
        err("README missing valid marketplace install command")

# ---------------------------------------------------------------------------
# 12. No pkill -f in references
# ---------------------------------------------------------------------------
print("\n--- Check 12: Safe preview cleanup (no pkill -f) ---")
ref_dir = REF_DIR
for fname in os.listdir(ref_dir):
    fpath = os.path.join(ref_dir, fname)
    if not fname.endswith(".md"):
        continue
    with open(fpath) as f:
        content = f.read()
    if "pkill -f" in content:
        err(f"{fname} uses 'pkill -f' instead of PID-scoped cleanup")
        break
else:
    print("  OK: No 'pkill -f' in reference files")

# ---------------------------------------------------------------------------
# 13. No automatic 12-CJK or 30%-image split rules
# ---------------------------------------------------------------------------
print("\n--- Check 13: Split rules use heuristics not thresholds ---")
ie_path = os.path.join(REF_DIR, "iterative-editing.md")
if os.path.exists(ie_path):
    with open(ie_path) as f:
        content = f.read()
    # Section 8 should not list 12-CJK or 30%-image as automatic conditions
    section_8_start = content.find("## 8. Splitting and merging")
    if section_8_start >= 0:
        s8 = content[section_8_start:]
        has_automatic_12 = "12 CJK" in s8 and "heuristic" not in s8[:s8.find("12 CJK")+50].lower()
        has_automatic_30 = "30" in s8 and "%" in s8 and "heuristic" not in s8[:s8.find("30")+50].lower()
        if has_automatic_12:
            err("Section 8 lists 12-CJK as automatic split condition (should be heuristic)")
        elif has_automatic_30:
            err("Section 8 lists 30%-image as automatic split condition (should be heuristic)")
        else:
            print("  OK: Split rules use heuristics, not automatic thresholds")
    else:
        print("  WARN: Could not find Section 8 to check split rules")

# ---------------------------------------------------------------------------
# 14. grep flavor correctness
# ---------------------------------------------------------------------------
print("\n--- Check 14: grep flavor (no bare \\d without -P in bash) ---")
for fname in os.listdir(ref_dir):
    fpath = os.path.join(ref_dir, fname)
    if not fname.endswith(".md"):
        continue
    with open(fpath) as f:
        content = f.read()
    # Find bash code blocks
    in_bash = False
    for i, line in enumerate(content.split("\n"), 1):
        if line.strip().startswith("```bash"):
            in_bash = True
            continue
        elif line.strip().startswith("```") and in_bash:
            in_bash = False
            continue
        if in_bash:
            # Check for grep with \d without -P or -E
            m = re.search(r'grep\s+(?!-P)(?!-E)(-[a-zA-Z]*[^PE])?\s+[\"\']?[^\"\']*\\\\d', line)
            if m:
                err(f"{fname}:{i} uses grep without -P/-E with \\d: {line.strip()[:80]}")
                break
    else:
        print(f"  OK: {fname} — grep commands use correct flavor")

# ---------------------------------------------------------------------------
# 15. Execute fixture test suite
# ---------------------------------------------------------------------------
print("\\n--- Check 15: Execute fixture test suite ---")
test_path = os.path.join(REPO_ROOT, "scripts", "test-renumbering.py")
if os.path.exists(test_path):
    result = subprocess.run(
        [sys.executable, test_path],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    # Print stdout (test output)
    for line in result.stdout.split("\\n"):
        if line.strip():
            print(f"  {line}")
    if result.stderr:
        for line in result.stderr.split("\\n"):
            if line.strip():
                print(f"  STDERR: {line}")

    if result.returncode == 0:
        # Extract test count from output
        import re as re2
        m = re2.search(r"Ran (\d+) tests in", result.stdout)
        count = m.group(1) if m else "?"
        print(f"  OK: {count} fixture tests PASSED")
    else:
        err(f"Fixture test suite exited {result.returncode}")
        print(f"  FAIL: See test output above")
else:
    err("Missing scripts/test-renumbering.py")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*50}")
if errors:
    for e in errors:
        print(e)
    print(f"\n{len(errors)} check(s) FAILED")
    sys.exit(1)
else:
    print("All checks PASSED")
    sys.exit(0)
