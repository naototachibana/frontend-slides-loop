# Visual Verification

A companion reference for **Mode C** of `frontend-slides/SKILL.md`.

Run this procedure after any change that can alter the rendered
appearance of a Frontend Slides-compatible HTML deck.

---

## 0. Local preview setup

Before running the verification loop, make the deck available over HTTP.
Use a PID-scoped background server and stop only that specific process.

```bash
# Determine the deck directory to serve as document root
#   - Single-file mode:  parent directory of the HTML file
#   - Bundle mode:       the bundle directory containing index.html + assets
DECK_DIR="/path/to/deck/directory"

# Pick an available port (default 8000, change if occupied)
PORT=8000

# Start the server, capturing the exact PID
cd "$DECK_DIR"
python3 -m http.server "$PORT" --bind 127.0.0.1 >preview-server.log 2>&1 &
PREVIEW_PID=$!
echo "Preview server PID: $PREVIEW_PID"
echo "URL: http://127.0.0.1:$PORT/index.html"

# Verify it responds
sleep 1
if curl --fail --silent --show-error \
  "http://127.0.0.1:$PORT/index.html" >/dev/null; then
  echo "Server is ready"
else
  echo "Server failed to respond"
  kill "$PREVIEW_PID" 2>/dev/null
  exit 1
fi
```

Open the deck in a browser or browser automation tool:

- If the deck supports `?slide=N`:
  `http://127.0.0.1:8000/index.html?slide=1`
- If it does not: navigate with keyboard arrow keys after opening the URL

**Cleanup after verification — stop only the PID we started:**

```bash
kill "$PREVIEW_PID" 2>/dev/null || true
# Optionally remove the temporary log
rm -f preview-server.log
```

> **Port conflicts**: If port 8000 is occupied, change `PORT=8000` to another
> value and update the URLs consistently.
>
> **Tailscale Serve**: Optional adapter only. Do not use as default preview.
> If you must use it, inspect current status first (`tailscale serve status`),
> do not use `sudo`, and provide cleanup instructions.

---

## 1. Deterministic readiness

Before inspecting, confirm the page is in a stable state. Use
the following JavaScript checks (in browser console or via
browser automation tool):

```javascript
// 1. Web font loading — with bounded timeout
const FONT_TIMEOUT_MS = 10000;
const fontReady = Promise.race([
  document.fonts.ready,
  new Promise((_, reject) =>
    setTimeout(() => reject(new Error(
      `Font loading timed out after ${FONT_TIMEOUT_MS} ms`
    )), FONT_TIMEOUT_MS)
  ),
]);
await fontReady;

// 2. Every image resolves as loaded or fails — with bounded timeout
const withTimeout = (promise, ms, label) =>
  Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error(`${label} timed out after ${ms} ms`)), ms)
    ),
  ]);

const imageChecks = [...document.images].map((img, index) => {
  const label =
    `Image ${index + 1}: ${img.currentSrc || img.src || "(missing src)"}`;
  return withTimeout(
    new Promise((resolve, reject) => {
      if (img.complete) {
        if (img.naturalWidth > 0) {
          resolve();
        } else {
          reject(new Error(`Broken image: ${img.currentSrc || img.src}`));
        }
        return;
      }
      img.addEventListener("load", resolve, { once: true });
      img.addEventListener(
        "error",
        () => reject(new Error(`Broken image: ${img.currentSrc || img.src}`)),
        { once: true }
      );
    }),
    10000,
    label,
  );
});

await Promise.all(imageChecks);

// 3. Animations and transitions settled — mutually exclusive paths
//    Path A (preferred): inject CSS to disable all motion.
function disableMotionWithCSS() {
  const style = document.createElement('style');
  style.textContent = '*, *::before, *::after { ' +
    'transition: none !important; ' +
    'animation: none !important; ' +
    'transition-delay: 0s !important; ' +
    'animation-delay: 0s !important; }';
  document.head.appendChild(style);
  // Wait two animation frames as a small bounded stabilization barrier
  return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
}

//    Path B (fallback, only if Path A unavailable): compute max
//    transition/animation duration from computed styles, apply
//    a bounded timeout, and report the calculated wait.
async function waitForMotionFallback() {
  const all = document.querySelectorAll('*');
  let maxMs = 0;
  all.forEach(el => {
    const cs = getComputedStyle(el);
    for (const prop of ['transitionDuration', 'animationDuration']) {
      const vals = (cs[prop] || '0s').split(',');
      const delays = ((prop === 'transitionDuration'
        ? cs.transitionDelay : cs.animationDelay) || '0s').split(',');
      vals.forEach((dur, i) => {
        const del = delays[i] || delays[0] || '0s';
        const parseMs = (s) => {
          s = s.trim();
          if (s.endsWith('ms')) return parseFloat(s);
          if (s.endsWith('s')) return parseFloat(s) * 1000;
          return 0;
        };
        const t = parseMs(dur) + parseMs(del);
        if (t > maxMs) maxMs = t;
      });
    }
  });
  // FSL-137: bounded timeout — fail if computed duration exceeds cap
  const MAX_MOTION_WAIT = 5000;
  if (maxMs > MAX_MOTION_WAIT) {
    throw new Error(
      `Motion settle maxMs (${maxMs}) exceeds ` +
      `MAX_MOTION_WAIT (${MAX_MOTION_WAIT}). ` +
      `Cannot proceed: deck has animations longer than the permitted cap.`
    );
  }
  const waitMs = Math.max(maxMs, 200);
  console.log(`Motion settle delay (fallback): ${waitMs} ms`);
  await new Promise(r => setTimeout(r, waitMs));
}

// Choose one path — do not execute both:
// Set this to true if CSS injection is not possible.
const MOTION_CSS_INJECTION_UNAVAILABLE = false;
if (MOTION_CSS_INJECTION_UNAVAILABLE) {
  await waitForMotionFallback();
} else {
  await disableMotionWithCSS();
}

// 4. Active slide found — fail if unresolved
// Use the selector discovered during Phase 0 (FSL-138).
// Do not hardcode — set during Phase 0 and fail closed if missing.
const PHASE_0_ACTIVE_SLIDE_SELECTOR = '.slide.active'; // ← set during Phase 0
const activeSlide = document.querySelector(PHASE_0_ACTIVE_SLIDE_SELECTOR);
if (!activeSlide) {
  throw new Error(
    `No active slide found using Phase 0 selector: ${PHASE_0_ACTIVE_SLIDE_SELECTOR}. ` +
    'Cannot proceed with visual verification.'
  );
}

// 5. Stage dimensions — use ONLY the selector discovered during Phase 0.
//    Do NOT fall back to generic selectors — fail closed if it's missing.
const PHASE_0_STAGE_SELECTOR = '#stage'; // ← set during Phase 0
const stage = document.querySelector(PHASE_0_STAGE_SELECTOR);
if (!stage) {
  throw new Error(
    `Authored stage not found using Phase 0 selector: ${PHASE_0_STAGE_SELECTOR}`
  );
}

// Measure authored dimensions using offsetWidth/offsetHeight (pre-transform)
// rather than getBoundingClientRect() which reports scaled viewport size.
// Frontend Slides scales a 1920×1080 stage to fit the viewport, so the
// bounding rectangle may not equal 1920×1080 even for a correct deck.
const authoredW = stage.offsetWidth;
const authoredH = stage.offsetHeight;
const authoredRect = stage.getBoundingClientRect();

const expectedW = 1920, expectedH = 1080;
if (Math.abs(authoredW - expectedW) > 1 || Math.abs(authoredH - expectedH) > 1) {
  console.warn(
    `Authored stage dimensions: ${authoredW}×${authoredH} ` +
    `(expected ${expectedW}×${expectedH}). ` +
    `Using authored dimensions (${authoredW}×${authoredH}) ` +
    `for bounds checks. ` +
    `Rendered viewport rect: ${Math.round(authoredRect.width)}×${Math.round(authoredRect.height)}`
  );
} else {
  console.log(
    `Stage OK: authored ${authoredW}×${authoredH}, ` +
    `rendered ${Math.round(authoredRect.width)}×${Math.round(authoredRect.height)}`
  );
}
```

---

## 2. DOM-level checks

Run automated checks before screenshot inspection:

```javascript
const slide = document.querySelector(PHASE_0_ACTIVE_SLIDE_SELECTOR);
if (!slide) {
  report('no active slide to inspect');
} else {
  // Overflow
  if (slide.scrollWidth > slide.clientWidth)
    report('horizontal overflow: ' + (slide.scrollWidth - slide.clientWidth) + 'px');
  if (slide.scrollHeight > slide.clientHeight)
    report('vertical overflow: ' + (slide.scrollHeight - slide.clientHeight) + 'px');

  // Bounding box — child elements must stay within the slide
  // To avoid false positives, skip:
  //   - hidden elements (display:none, visibility:hidden)
  //   - zero-size elements (width/height = 0)
  //   - intentionally off-stage inactive slides (opacity: 0)
  //   - SVG filter or shadow bounds extending past the element
  //
  // Use data-allow-overflow attribute for intentional overflow elements.
  // Document every such element in the verification evidence.
  // Do not use hard-coded broad class selectors like '.shadow'.
  slide.querySelectorAll('*').forEach(el => {
    // Check allowlist — elements with data-allow-overflow attribute are exempt
    if (el.hasAttribute && el.hasAttribute('data-allow-overflow')) return;

    const r = el.getBoundingClientRect();
    const sr = slide.getBoundingClientRect();
    // Skip zero-size elements
    if (r.width === 0 || r.height === 0) return;

    if (r.left < sr.left - 0.5 || r.top < sr.top - 0.5 ||
        r.right > sr.right + 0.5 || r.bottom > sr.bottom + 0.5) {
      const style = getComputedStyle(el);
      if (style.display !== 'none' && style.visibility !== 'hidden' &&
          parseFloat(style.opacity) > 0) {
        report('element outside slide boundary: ' +
          el.tagName + (el.className ? '.' + el.className.split(' ').join('.') : ''));
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
