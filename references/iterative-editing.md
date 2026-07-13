# Iterative Slide Editing

A companion reference for **Mode C** of `frontend-slides/SKILL.md`.

Apply these procedures when modifying an existing Frontend
Slides-compatible 1920×1080 fixed-stage HTML deck, or a compatible
external deck whose structure has first been detected and validated.

---

## 1. Baseline inspection (Phase 0)

Before any edit, determine the deck's actual structure — do not
assume a specific template convention:

- **Slide selector and count**: how many `.slide` elements exist
- **Slide identity mechanism**: numbered class (`.slide-01`), `data-slide-id`,
  `id` attribute, or none
- **Stage dimensions**: the authored slide size (expected 1920×1080)
- **Navigation**: how slides are controlled (keyboard, `?slide=N`, click)
- **Counter scheme**: static (`NN / MM` in HTML), JS-generated, or absent
- **CSS selector scheme**: whether slide-specific `.slide-NN` rules exist
- **Asset base path**: where images and other resources are loaded from
- **Output mode**: single-file (all inline) or bundle (HTML + assets)

Record these findings. If the structure is not understood well enough to
edit safely, stop and report what could not be established.

---

## 2. Text editing

Use find-and-replace with enough surrounding context for uniqueness.

Prefer `patch` (fuzzy matching) over sed. When the same text appears
in multiple slide elements, scope the replacement by including enough
parent HTML to make it unique.

Verify that font sizes, line-heights, and container dimensions still
accommodate the new text after editing.

---

## 3. Image replacement

1. Obtain the source image (download from URL, local path, or data URI).
2. Determine the output mode of the deck. The default is
   **single-file mode** (matching Frontend Slides' zero-dependency
   principle). Change mode only when required and disclosed.

   - **Single-file mode (default, recommended)** — embed the image as
     a data URI. Do not silently introduce sibling-file dependencies.
   - **Bundle mode** — place the image in the deck's asset directory
     and use a relative `src` path. Verify the path at rest and
     when served over HTTP. The entire directory is the deliverable.
   - **External mode** — use a remote URL only when the user has
     explicitly accepted external hosting or hotlinking. Do not
     treat an external host as the default solution for local-preview
     path problems. Record external dependencies in the final report.

3. Update the `<img src="...">` attribute.
4. Update `alt` text if the subject changed.
5. Hand off for visual verification.

### Local-preview caveat

A single-file HTTP serve does not resolve relative image paths. If the
deck is served this way and images must be local, serve the entire
directory or switch to an external URL for images.

---

## 4. Layout editing

When restructuring a slide's layout:

1. Read the slide's full HTML block.
2. Replace the affected container (`<div class="content">` or a
   narrower scope) with the new structure.
3. Add any new CSS rules needed. Prefix them with the slide's
   identity selector (e.g. `.slide-05 .new-component`).
4. Remove CSS rules that are no longer referenced.
5. Verify visually — do not rely on DOM checks alone.

### CSS traps

- `text-transform: uppercase` on a parent also transforms descendant
  text. If you write `[nm]` inside a parent with `text-transform`,
  it renders as `[NM]`.
- `white-space: nowrap` on a narrow element causes overflow.
- Remove or override inherited rules that conflict with the new layout.

---

## 5. Slide insertion

1. Build the new slide HTML using the deck's established component
   classes and CSS variables.
2. Assign a stable identity: `data-slide-id="descriptive-name"`.
   Avoid positional classes such as `.slide-06` unless the deck
   already uses them.
3. Insert the `<section>…</section>` block at the target position.
4. If the deck uses positional numbered classes or counters, renumber
   all slides from the insertion point onward. Use a **two-pass**
   approach to avoid collision:

   ```
   pass 1: replace every old class/counter with a temporary token
   pass 2: replace every token with the final value
   ```

   Never perform ascending replacements that can rematch a value
   just written.
5. If counters are hard-coded in the HTML, update them to match the
   new total.
6. Update slide-specific CSS selectors if the deck uses positional
   numbering.
7. Add the new slide's CSS rules if it needs unique styling.
8. Regenerate screenshots.

---

## 6. Slide deletion

1. Remove the `<section>…</section>` block.
2. Remove any CSS rules referenced only by the deleted slide's
   selector.
3. If the deck uses positional numbering, renumber all subsequent
   slides (two-pass method, same as insertion).
4. Update counters and total denominator.
5. Remove or regenerate screenshots.
6. Run the structure verification from Phase 0.

---

## 7. Slide reordering

1. Move the target `<section>…</section>` block to the new position.
2. Renumber all slides from the earlier of the two positions onward.
3. Update CSS selectors, counters, and screenshot filenames.
4. Verify that every slide identity is unique after the operation.

---

## 8. Splitting and merging

**Split** when any of these is true:

- text column has fewer than 12 CJK characters per line at reading size
- an image is smaller than 30 % of its column
- a card or table row is clipped
- total content exceeds the stage content area

Move a subset of content to a new slide inserted immediately after.
Follow insertion procedure.

**Merge** when two consecutive slides have very little content each.
Delete one slide and absorb its content into the other. Follow
deletion procedure.

---

## 9. Legacy numbered decks

When a deck already uses positional classes (`.slide-01` … `.slide-12`):

### Collision-safe renumbering

Use a **three-pass** replacement:

```
pass A: prefix every old numbered pattern with a unique marker,
         e.g. `.slide-05` → `.slide-__OLD_05__`
pass B: replace the marker + old number with the new number,
         e.g. `.slide-__OLD_05__` → `.slide-04`
pass C: clean up any unreplaced markers as errors
```

This applies to:

- HTML class attributes (`class="slide slide-05"`)
- CSS selectors (`.slide-05 .title { ... }`)
- HTML comments (`<!-- SLIDE 05 -->`)
- Counter text (`05 / 12`)
- Navigation metadata
- Screenshot filenames (`slide-05.png`)

### Zero-padded numbers

Support at least 8, 12, and 20 slides. Use two-digit zero-padding
(`01` … `20`). Do not use regex patterns that match only single-digit
numbers (e.g. `slide-0[1-9]`).

### Verification after renumbering

```bash
# Identity uniqueness: check data-slide-id values if they exist
grep -oP 'data-slide-id="[^"]*"' deck.html | sort | uniq -d
# (Output empty = all unique; shows duplicates if any)

# Numbered-class identity: extract slide-NN from section elements only
grep -oP '<section[^>]*class="[^"]*slide-\d+[^"]*"[^>]*>' deck.html |
  grep -oP 'slide-\d+' | sort | uniq -c
# Expected: each number should appear exactly once

# Verify identity count matches expected total
if [ "$(grep -oP '<section[^>]*class="[^"]*slide[^"]*"[^>]*>' deck.html |
         grep -c 'slide-\d')" -eq "$NEW_COUNT" ]; then
  echo "OK: $NEW_COUNT identities found"
fi

# Counter text consistency (if deck uses static counters)
grep -oP '\b\d{2}\s*/\s*\d{2}\b' deck.html | sort -u
# Verify each counter pair matches the expected totals
```

### Split heuristics

The following observations from real-world decks are
**reference heuristics**, not general failure conditions.
Evaluate them in context:

- If a text column has fewer than roughly 12 CJK characters
  per line at reading size, the column may be too wide for
  its content; splitting could improve readability.
- If an image is visually smaller than ~30% of its column
  width, it may be undersized for its container.
- Cards, tables, or panels whose content is visibly clipped
  should be split or restructured regardless of numeric
  heuristics.
- When total content exceeds the authored stage content area
  (determined by the deck's CSS variables and container
  dimensions), splitting is required — not heuristic.

---

## 10. Rollback checkpoints

Before any structural operation (insert, delete, reorder, split, merge):

1. Save a copy of the file: `cp deck.html deck.html.bak`
2. Record the current slide identity list
3. Record the current CSS selector inventory

If the operation fails or produces unexpected results:

1. Restore: `cp deck.html.bak deck.html`
2. Discard the backup only after verification passes

---

## 11. Completion handoff

After editing, hand off to visual verification by reporting:

- which slides were changed
- what kind of change was made (text, image, layout, structural)
- expected visual effect
- any areas of concern (tight spacing, new CSS, renumbered items)
