# Visual Verification

A companion reference for **Mode C** of `frontend-slides/SKILL.md`.

Run this procedure after any change that can alter the rendered
appearance of a Frontend Slides-compatible HTML deck.

---

## 1. Deterministic readiness

Before inspecting, confirm the page is in a stable state:

- `document.fonts.ready` has resolved
- All relevant `<img>` elements have `naturalWidth > 0` or have
  fired an `onerror` (not still pending)
- Animations and transitions are settled — either wait a reasonable
  timeout (at least 300 ms after the slide change) or disable
  animations via `prefers-reduced-motion` for verification
- The intended slide is the active slide
- The fixed stage has the expected dimensions (1920×1080 at the
  authored coordinate system)

---

## 2. DOM-level checks

Run automated checks before screenshot inspection:

```javascript
const slide = document.querySelector('.slide.active') ||
              document.querySelector('.slide.visible');

// Overflow
if (slide.scrollWidth > slide.clientWidth)
  report('horizontal overflow');
if (slide.scrollHeight > slide.clientHeight)
  report('vertical overflow');

// Images
slide.querySelectorAll('img').forEach(img => {
  if (img.naturalWidth === 0)
    report('broken image: ' + img.src);
});

// Duplicate slide IDs
const ids = [...document.querySelectorAll('[data-slide-id]')]
  .map(el => el.getAttribute('data-slide-id'));
if (new Set(ids).size !== ids.length)
  report('duplicate slide IDs');
```

---

## 3. Screenshot capture

Use the agent's screenshot tool at full presentation resolution
(1920×1080 authored stage). Do not rely on a scaled-down preview
for final verification.

Show the complete slide, including footer and page counter if
the deck uses them.

---

## 4. Screenshot inspection checklist

Check every item that applies to the change:

| # | Check | Pass condition |
|---|-------|----------------|
| 1 | **No clipping** | No text, image, or panel edge is cut off by the slide boundary |
| 2 | **No overlap** | No panel, card, or text block sits unintentionally on top of another |
| 3 | **Text columns** | Japanese or CJK text wraps by meaningful phrase — not one or two characters per line |
| 4 | **Images intact** | Every expected image renders; none is replaced by a broken-icon or alt text alone |
| 5 | **Aspect ratio** | Images are not stretched, squashed, or cropped unexpectedly |
| 6 | **One-line titles** | Where specified, the title fits on one line |
| 7 | **Footer visibility** | Footer, source line, and page counter are visible if they exist |
| 8 | **Design consistency** | Colors, fonts, borders, and spacing match the deck's established design system |
| 9 | **No accidental transforms** | Text like `[nm]` is not rendered as `[NM]` due to CSS inheritance |
| 10 | **Counter correctness** | Page numbers are consecutive and the total matches the slide count |

---

## 5. Bounded correction loop

```
round = 0
MAX_ITERATIONS = 3

while defects_found and round < MAX_ITERATIONS:
    round += 1
    record current defects and screenshot
    apply the most targeted fix
    return to step 1 (reload and wait for readiness)
    re-run DOM checks
    capture new screenshot
    inspect against checklist

after loop:
    if no defects remain:
        report PASS with the final screenshot
    else:
        report REMAINING DEFECTS with the latest screenshot
        list each unresolved defect and what was tried
        do not call a result accepted merely because the latest change
        differed visually from the previous iteration
```

---

## 6. Acceptance determination

| Category | Decided by |
|----------|-----------|
| Measurable invariants (overflow, broken images, duplicate IDs) | Objective DOM checks |
| Visual invariants (clipping, overlap, aspect ratio, counter correctness) | Screenshot inspection |
| Aesthetic choices (color shade, font size preference, spacing feel) | User approval |

Do not skip user approval for aesthetic decisions. Do not escalate
measurable or visual failures to the user as if they are preferences.

---

## 7. Evidence

Preserve from each iteration:

- the screenshot
- a list of defects found (or "none")
- what fix was applied
- the iteration round number

Include the final pass/fail evidence in the completion report.
