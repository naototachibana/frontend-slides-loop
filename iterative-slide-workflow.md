---
name: iterative-slide-workflow
description: |
  Slide-deck modification workflow for agents: structural operations
  (insert, delete, reorder), content editing, screenshot-based visual
  verification, and iteration. Complements the one-shot generation
  in SKILL.md with a refinement loop for existing presentations.
---

# Iterative Slide-Deck Workflow

This document fills the refinement gap in Frontend Slides: what to do
*after* the first draft exists — editing, restructuring, verifying, and
iterating on an already-generated presentation.

It is written generically so it applies to any 1920×1080 fixed-stage
HTML slide deck, regardless of topic, template, or visual style.

---

## Phase 0: Understand the Deck

Before making any change, establish baseline facts:

```
grep -n 'SLIDE 0' deck.html        # slide list with line numbers
grep -n 'slide-0[1-9]' deck.html   # all slide-class references
grep -c '<section .*class="slide' deck.html  # total slide count
```

Record:
- Total slide count
- Each slide's topic, line range, css class (`.slide-NN`)
- Counter pattern (`NN / MM` — one per slide in topbar and footline)
- Any slide-specific CSS class references in `<style>` blocks
- External image URLs referenced in `<img src="...">`

---

## Phase 1: Structure Operations

### 1a — Delete a slide

1. Remove the HTML block:
   `<!-- SLIDE NN --> … </section>`
2. Remove any slide-specific CSS rules for that class:
   `grep -n "slide-NN\." deck.html` in the `<style>` block
3. Renumber every *later* slide's:
   - Comment (`SLIDE NN` → `SLIDE NN-1`)
   - HTML class (`slide-NN` → `slide-NN-1`)
   - Topbar counter / footline counter (`NN / MM` → `NN-1 / MM-1`)
4. Renumber every later slide-specific CSS selector:
   `.slide-NN` → `.slide-NN-1`
5. Update the total-denominator for all slides (`/MM` → `/MM-1`)

### 1b — Insert a slide

1. Build the new slide's HTML block, assign it the next free class
   (e.g. `slide-06` if `slide-05` precedes it)
2. Insert the HTML between the adjacent slide boundaries
3. Renumber every *later* slide (comment, class, counter) → increment by 1
4. Renumber every later slide-specific CSS selector
5. Add CSS rules for the new slide's class if it uses unique layouts
6. Update total-denominator for all slides (`/MM` → `/MM+1`)

### 1c — Reorder slides

1. Move the entire `<section>…</section>` block to the target position
2. Renumber all slides from the destination index onward
3. Renumber CSS selectors and counters accordingly

### Counter update trick

Use `patch` with `replace_all=true` when only the denominator changes:

```
patch path=deck.html old_string="03 / 09" new_string="03 / 08" replace_all=true
```

When both number and denominator change, do each old value individually.

### Verify structure

```
grep -n 'slide-0' deck.html | grep -v wl-
grep -n '/ 0[0-9]' deck.html          # every counter occurrence
```

All counters must be consecutive and match the final slide count.

---

## Phase 2: Content Editing

### 2a — Edit text (targeted)

Use `patch` with enough surrounding context for uniqueness:

```
patch path=deck.html \
  old_string="元の文章" \
  new_string="新しい文章"
```

For repeated text (e.g. a label appearing in all cards), scope by
including the parent container in both old and new strings.

### 2b — Replace an image

1. Download the source image (curl, browser, Imgur, etc.)
2. Decide where to host it:
   - **Same repo**: copy into an `images/` or `assets/` directory.
     Use relative path in `<img src="...">`.
   - **External URL**: direct link (Imgur, CDN, etc.)
     Only use if the host reliably serves the file.
   - **Tailscale Serve constraint**: a single-file Serve does *not*
     resolve relative image paths.  If you need local images under
     Tailscale Serve, either serve the whole directory or use an
     external URL as the image source.
3. Change the `<img src="...">` attribute:
   ```
   <img src="old/path.jpg" ...>  →  <img src="new/path.png" ...>
   ```
4. Update the `alt` text if the subject changed.
5. Verify the image renders (Phase 4).

### 2c — Edit layout

For layout changes that go beyond find-and-replace, replace the whole
slide's HTML or the affected container:

1. Read the current HTML block for the slide
2. Rewrite the container (`<div class="content">…</div>` or a narrower
   scope) with the new structure
3. Add any new CSS class rules needed for the new layout
4. Remove CSS rules that are no longer referenced
5. Verify visually (Phase 4)

### 2d — Text-formatting traps

- `text-transform: uppercase` on a parent element affects every
  descendant text node.  If you write `[nm]` inside a parent with
  `text-transform: uppercase`, it renders as `[NM]`.
- `white-space: nowrap` on a narrow element causes overflow.
- Japanese text needs adequate column width for line-breaking.
  A good heuristic: minimum 12 CJK characters per line at
  body-text size (38–40 px).

---

## Phase 3: Asset Management

### 3a — Screenshot regeneration

After any structural or visual change, regenerate slide images:

```
for n in $(seq 1 $SLIDE_COUNT); do
  browser_navigate(url="https://…?slide=$n")
  browser_vision(question="full slide $n")
  cp <screenshot_path> <project>/images/slide-$(printf "%02d" $n).png
done
```

### 3b — Image directory maintenance

When slides are added or removed:

- **Added**: create new `slide-NN.png` and add to git
- **Removed**: `git rm` the orphaned `slide-NN.png`
- **Renumbered**: truncate old sequence; regenerate all

### 3c — External images

If an image source URL may become unavailable, store a local copy:

```
curl -sL -o images/local-name.png "https://example.com/path/image.png"
```

- Prefer placing images in a `assets/` or `images/` subdirectory
  next to the HTML file.
- For Tailscale single-file Serve, fall back to a stable external URL.

---

## Phase 4: Visual Verification

### 4a — Render the deck

Open the deck in a browser at a slide that exercises the changed
content:

```
browser_navigate(url="https://…?slide=N")
```

### 4b — Screenshot inspection checklist

Use `browser_vision` (or take a screenshot and inspect it) with a
prompt that checks every item below:

```
1. Title on one line? (if so specified)
2. No overflow or clipping: text, images, borders within canvas
3. No panel overlap or z-order issues
4. Japanese/Asian text wraps by phrase, not 1–2 characters per line
5. Images render, are not distorted, preserve aspect ratio
6. Table rows/cards fully visible, no truncated content
7. Footer / source / page counter visible at bottom
8. Colors and fonts match the slide's design system
9. All `src=` images are present (no placeholder/alt-text only)
```

### 4c — Layout measurement

When a precise measurement is needed:

- Content area: 1680 × 815 px  (1920 − 2×120, 1080 − 150 − 115)
- Title at 104 px fills ≈ 1040 px of width (CJK-heavy titles may wrap)
- Safe line-length heuristic:
  `(column_width − padding) / font_size ≥ 12` for Japanese body text

### 4d — Multi-device check

For production decks, verify at two sizes:

1. Full 1920×1080 (desktop projector)
2. A narrower viewport or reduced scale (preview panes, scaled browser)

The fixed 16:9 stage handles this automatically; check only that no
overflow appears at the scaled sizes.

---

## Phase 5: Iterative Refinement

### The core loop

```
while not accepted:
  1. identify the problem
  2. propose a fix
  3. apply the fix (patch, replace, restructure)
  4. re-render the deck
  5. take a screenshot of the affected slide(s)
  6. verify against the acceptance criteria
  7. if the fix introduces a new problem:
       revert or apply a corrective patch
       go to step 4
  8. if all criteria pass:
       mark accepted, continue to the next issue
```

This loop is the central mechanism that `SKILL.md`'s one-shot
generation does not define.  It is what makes agent-driven slide
refinement reliable.

### When to split a slide

Split when **any** of these is true:

- Title wraps to 2 lines at body-text size
- Text column has fewer than 12 CJK characters per line
- Image is smaller than 30 % of its column
- A list/card/table row is clipped or truncated
- Total content height exceeds 815 px (the `.content` area)

Move a subset of content to a new slide inserted immediately after.

### When to merge slides

Merge when two consecutive slides have very little content each
(e.g. one short bullet + one image).  Use the procedure in 1b
(reverse: delete one, absorb its content into the other).

---

## Phase 6: Local Preview & Distribution

### 6a — Tailscale Serve (tailnet-local)

```bash
# Serve a single file
sudo tailscale serve --bg --https=443 --set-path=/SLUG /absolute/path/to/deck.html

# Remove that mount
sudo tailscale serve --bg --https=443 --set-path=/SLUG off

# Access:  https://<hostname>.ts.net/SLUG?slide=N
```

Use a distinct slug per version (`/deck-v1`, `/deck-v2`, …) so the
user can A/B compare.

Caveats (see also 2b):
- A single-file Serve does **not** serve sibling assets.
  Images referenced by relative paths will not load.
- Use absolute external URLs for images, or serve the whole directory.

### 6b — Git versioning

```bash
cp deck-v1.html deck-v2.html    # branch for iterative changes
git add deck-v2.html images/
git commit -m "description of changes"
git push origin main
```

Keep past versions (`-v1`, `-v2`)  for reference; squash only when
the user explicitly asks for cleanup.

---

## Phase 7: Recovery & Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Image not rendering on Tailscale | Relative path not served | Replace `src=` with external URL |
| Counter shows `08 / 09` but only 8 slides | Denominator not updated | `patch replace_all=true` on mis-matched counter |
| CSS rules for deleted slide still in `<style>` | Orphan CSS | `grep slide-NN` in style block, remove dead rules |
| Title wraps to 2 lines | Font too large for column | Reduce font-size by 20–40 % or widen column |
| `[nm]` renders as `[NM]` | Parent has `text-transform: uppercase` | Remove `text-transform` from the parent, or scope a child rule |
| Two elements overlap at bottom | Absolute positioning conflict | Switch to flex/grid; avoid mixing absolute with flow layout |
| New slide's class matches old CSS | Stale selector from prior renumbering | Update the CSS selector to match the new class |
