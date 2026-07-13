# Visual Verification

A companion reference for **Mode C** of `frontend-slides/SKILL.md`.

Run this procedure after any change that can alter the rendered
appearance of a Frontend Slides-compatible HTML deck.

---

## 0. Local preview setup

Before running the verification loop, make the deck available over HTTP:

```bash
# Single-file deck: serve its parent directory
cd /path/to/deck/directory
python3 -m http.server 8000 --bind 127.0.0.1

# Verify the server responds
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/index.html
# Expected: 200
```

Open the deck in a browser or browser automation tool:

- If the deck supports `?slide=N`: `http://127.0.0.1:8000/index.html?slide=1`
- If it does not: navigate with keyboard arrow keys after opening the URL

**Cleanup after verification:**

```bash
kill %1 2>/dev/null
# or
pkill -f "python3 -m http.server 8000" 2>/dev/null
```

> **Note**: Tailscale Serve or similar tunnel services are optional adapters. Do not use them as the default preview method. If you must use Tailscale Serve, inspect current status first (`tailscale serve status`), do not use `sudo`, and provide cleanup instructions.

---

## 1. Deterministic readiness

Before inspecting, confirm the page is in a stable state. Use
the following JavaScript checks (in browser console or via
browser automation tool):

```javascript
// 1. Web font loading
await document.fonts.ready;

// 2. All images loaded or explicitly failed
const images = document.querySelectorAll('img');
const allLoaded = [...images].every(
  img => img.complete && img.naturalWidth > 0
);

// 3. Animations and transitions settled:
//    Standard Frontend Slides decks have 0.6s transition +
//    max 0.4s stagger delay. Wait at least 1200 ms after
//    slide change.
await new Promise(r => setTimeout(r, 1200));

// 4. Active slide found
const activeSlide = document.querySelector('.slide.active') ||
                    document.querySelector('.slide.visible');
if (!activeSlide) {
  throw new Error('No active or visible slide found');
}

// 5. Stage dimensions at authored coordinate system
//    (expected 1920×1080 for Frontend Slides decks)
const stage = document.querySelector('#stage') ||
              document.querySelector('.stage') ||
              document.querySelector('[class*="stage"]');
if (stage) {
  const sr = stage.getBoundingClientRect();
  // Log actual dimensions for reference
  console.log(`Stage: ${sr.width}×${sr.height}`);
}
```

---

## 2. DOM-level checks

Run automated checks before screenshot inspection:

```javascript
const slide = document.querySelector('.slide.active') ||
              document.querySelector('.slide.visible');
if (!slide) {
  report('no active slide to inspect');
} else {
  // Overflow
  if (slide.scrollWidth > slide.clientWidth)
    report('horizontal overflow: ' + (slide.scrollWidth - slide.clientWidth) + 'px');
  if (slide.scrollHeight > slide.clientHeight)
    report('vertical overflow: ' + (slide.scrollHeight - slide.clientHeight) + 'px');

  // Bounding box — child elements must stay within the slide
  slide.querySelectorAll('*').forEach(el => {
    const r = el.getBoundingClientRect();
    const sr = slide.getBoundingClientRect();
    if (r.left < sr.left - 0.5 || r.top < sr.top - 0.5 ||
        r.right > sr.right + 0.5 || r.bottom > sr.bottom + 0.5) {
      // Only report visible elements to avoid false positives
      const style = getComputedStyle(el);
      if (style.display !== 'none' && style.visibility !== 'hidden') {
        report('element outside slide boundary: ' +
          el.tagName + (el.className ? '.' + el.className : ''));
      }
    }
  });

  // Images
  slide.querySelectorAll('img').forEach(img => {
    if (img.naturalWidth === 0)
      report('broken image: ' + (img.src || 'no src'));
    // Aspect ratio check (only if natural dimensions known)
    if (img.naturalWidth > 0 && img.width > 0) {
      const expectedRatio = img.naturalWidth / img.naturalHeight;
      const actualRatio = img.width / img.height;
      if (Math.abs(expectedRatio - actualRatio) > 0.05)
        report('aspect ratio distortion: ' + img.src);
    }
  });

  // Counter validation (if counters exist)
  const counterEl = slide.querySelector('.counter, .page-number, [class*="counter"]');
  if (counterEl) {
    const text = counterEl.textContent.trim();
    const match = text.match(/(\d+)\s*\/\s*(\d+)/);
    if (match) {
      const totalSlides = document.querySelectorAll('.slide').length;
      if (parseInt(match[2]) !== totalSlides)
        report('counter total mismatch: ' + match[2] + ' vs ' + totalSlides + ' slides');
    }
  }

  // Duplicate slide IDs
  const ids = [...document.querySelectorAll('[data-slide-id]')]
    .map(el => el.getAttribute('data-slide-id'));
  if (new Set(ids).size !== ids.length) {
    const dupes = ids.filter((id, i) => ids.indexOf(id) !== i);
    report('duplicate slide IDs: ' + [...new Set(dupes)].join(', '));
  }
}
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
