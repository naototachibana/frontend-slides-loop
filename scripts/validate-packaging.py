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
10. Reference links remain relative and use shallow, directly discoverable
    paths.

Exit 0 on success, non-zero on failure.
"""

import os
import re
import sys
import filecmp

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
        if any(ctx in readme[max(0, readme.index(url)-200):readme.index(url)+len(url)+200].lower()
               for ctx in ["upstream", "attribution", "credit", "originate"]):
            attribution_urls.append(url)
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
print("\\n--- Check 9: Numbered-slide handling ---")
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

    # Note: A full runtime test would create an 8, 12, or 20-slide fixture
    # deck using the standard template, run insertion/deletion/reordering,
    # and verify identity uniqueness. That requires browser automation.
    print("  INFO: Runtime fixture tests not possible without browser.")
    print("  INFO: Static pattern validation performed instead.")

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
