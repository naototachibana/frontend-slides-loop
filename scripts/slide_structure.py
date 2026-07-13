"""
slide_structure.py — Parse, validate, and transform synthetic
Frontend Slides fixture decks. Standard library only, no browser.

Scope: deterministic fixture/test utility. NOT a general-purpose
HTML presentation editor. Supports a controlled fixture grammar.
"""
import re
from functools import cmp_to_key
from typing import List, Dict, Tuple, Set


# ---------------------------------------------------------------------------
# Fixture generation
# ---------------------------------------------------------------------------

def make_slide_fragment(num: int, total: int = 0,
                        data_id: str = None,
                        payload_text: str = None) -> str:
    """Return exactly one <section>...</section> fragment."""
    if total <= 0:
        total = num
    cls = f"slide slide-{num:02d}"
    did_attr = f' data-slide-id="{data_id}"' if data_id else ""
    payload = f'      <p>{payload_text}</p>\n' if payload_text else ""
    return (
        f'    <section class="{cls}"{did_attr}>\n'
        f'      <!-- SLIDE {num:02d} -->\n'
        f'{payload}'
        f'      <div class="counter">{num:02d} / {total:02d}</div>\n'
        f'    </section>\n'
    )


def make_deck(num_slides: int, stable_ids: bool = True) -> str:
    """Create a synthetic Frontend Slides deck.

    When stable_ids=True, data-slide-id uses non-positional IDs
    (topic-001, ...) that MUST be preserved through operations.

    When stable_ids=False, data-slide-id uses positional IDs (slide-01...).
    """
    slides = []
    for i in range(1, num_slides + 1):
        did = f"topic-{i:03d}" if stable_ids else f"slide-{i:02d}"
        payload = f"payload-{i:03d}"
        slides.append(make_slide_fragment(i, num_slides, did, payload))
    return "<!DOCTYPE html>\n<html>\n<body>\n" + "".join(slides) + "</body>\n</html>\n"


def make_deck_with_content(num_slides: int, stable_ids: bool = True) -> str:
    """Create a deck where each slide has rich content: multiple <p> tags,
    an extra class, a style attribute, and an image element.

    This verifies that structural operations preserve full HTML content,
    not just the first <p> payload.
    """
    slides = []
    for i in range(1, num_slides + 1):
        did = f"topic-{i:03d}" if stable_ids else f"slide-{i:02d}"
        extra_cls = f"deck-section-{i:02d}"
        slides.append(
            f'    <section class="slide slide-{i:02d} {extra_cls}"'
            f' style="background:#fff" data-slide-id="{did}">\n'
            f'      <!-- SLIDE {i:02d} -->\n'
            f'      <p>intro-{i:03d}</p>\n'
            f'      <img src="slide-{i:02d}.png" alt="slide {i}"/>\n'
            f'      <div class="card"><p>detail-{i:03d}</p></div>\n'
            f'      <div class="counter">{i:02d} / {num_slides:02d}</div>\n'
            f'    </section>\n'
        )
    return "<!DOCTYPE html>\n<html>\n<body>\n" + "".join(slides) + "</body>\n</html>\n"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

SLIDE_PATTERN = re.compile(
    r'(<section\s+class="([^"]*)"(.*?)>)\s*'
    r'<!--\s*SLIDE\s+(\d+)\s*-->\s*'
    r'(.*?)'
    r'<div\s+class="counter">(\d+)\s*/\s*(\d+)</div>\s*'
    r'</section>',
    re.DOTALL,
)

SECTION_PATTERN = re.compile(
    r'<section[^>]*class="[^"]*slide-\d+[^"]*"[^>]*>',
)

COUNTER_PATTERN = re.compile(
    r'<div\s+class="counter">(\d+)\s*/\s*(\d+)</div>',
)


def parse_slides(deck_html: str) -> List[Dict]:
    """Extract ordered slide data from a fixture deck.

    Returns a dict per slide with keys:
      full_html, class_str, attrs, comment_num,
      counter_current, counter_total, data_id, payload
    """
    slides = []
    for m in SLIDE_PATTERN.finditer(deck_html):
        attrs = m.group(3)
        did = None
        did_m = re.search(r'data-slide-id="([^"]*)"', attrs)
        if did_m:
            did = did_m.group(1)
        inner = m.group(5) or ""
        # Extract ALL <p> text for payload verification
        payloads = re.findall(r'<p>(.*?)</p>', inner)
        slides.append({
            'full_html': m.group(0),
            'class_str': m.group(2),
            'attrs': attrs,
            'comment_num': int(m.group(4)),
            'counter_current': int(m.group(6)),
            'counter_total': int(m.group(7)),
            'data_id': did,
            'payloads': payloads,
            'inner_html': inner,
        })
    return slides


def extract_slide_numbers(deck_html: str) -> List[int]:
    return [int(s) for s in re.findall(
        r'<section[^>]*class="[^"]*slide-(\d+)[^"]*"[^>]*>',
        deck_html,
    )]


def extract_data_ids(deck_html: str) -> List[str]:
    return re.findall(r'data-slide-id="([^"]*)"', deck_html)


def extract_payloads(deck_html: str) -> List[str]:
    """Extract ALL <p> text from slides, not just the first."""
    result = []
    for s in parse_slides(deck_html):
        result.extend(s['payloads'])
    return result


def count_slides(deck_html: str) -> int:
    return len(SECTION_PATTERN.findall(deck_html))


def count_doctypes(deck_html: str) -> int:
    return len(re.findall(r'<!DOCTYPE\s+html>', deck_html, re.IGNORECASE))


# ---------------------------------------------------------------------------
# FSL-149: Targeted replacement within slide HTML (preserves all content)
# ---------------------------------------------------------------------------

def _replace_slide_in_deck(deck_html: str, old_slide_html: str,
                           new_slide_html: str) -> str:
    """Replace one slide's section HTML in the deck document."""
    return deck_html.replace(old_slide_html, new_slide_html, 1)


def _update_slide_numbering(slide_html: str,
                            old_num: int, new_num: int,
                            total: int,
                            data_id: str = None) -> str:
    """Update positional metadata within an existing slide's HTML.

    Performs targeted replacements only on:
      - class: slide-NN → slide-MM
      - comment: SLIDE NN → SLIDE MM
      - <div class="counter">: NN / TT → MM / TT
      - positional data-slide-id="slide-NN" → "slide-MM"

    Preserves ALL other content: extra classes, attributes, styles,
    images, multiple <p> tags, card elements, SVG, scripts, etc.
    """
    old_str = f"{old_num:02d}"
    new_str = f"{new_num:02d}"
    total_str = f"{total:02d}"

    result = slide_html

    # 1. Class attribute (first occurrence of slide-NN pattern)
    result = result.replace(
        f'slide-{old_str}',
        f'slide-{new_str}',
        1,
    )

    # 2. HTML comment
    result = result.replace(
        f'SLIDE {old_str}',
        f'SLIDE {new_str}',
        1,
    )

    # 3. Positional data-slide-id (slide-NN format only)
    result = result.replace(
        f'data-slide-id="slide-{old_str}"',
        f'data-slide-id="slide-{new_str}"',
        1,
    )

    # 4. <div class="counter"> content
    # Match the exact counter text to avoid damaging payload
    result = result.replace(
        f'>{old_str} / {old_total_str}',
        f'>{new_str} / {total_str}',
        1,
    ) if False else result  # placeholder

    # Actually do the replacement properly:
    counter_old = f'>{old_str} / '
    result = result.replace(counter_old, f'>{new_str} / ', 1)

    # If data_id is provided and differs from positional, keep it
    if data_id and not data_id.startswith(f'slide-{new_str}'):
        pass  # non-positional IDs are preserved as-is

    return result


# Extract old total from the slide HTML for counter replacement
def _slide_counter_total(slide_html: str) -> int:
    m = COUNTER_PATTERN.search(slide_html)
    if m:
        return int(m.group(2))
    return 0


# ---------------------------------------------------------------------------
# Fragment validation
# ---------------------------------------------------------------------------

class FragmentError(ValueError):
    """Raised when a slide fragment is invalid for insertion."""


DOCUMENT_TAGS = [
    '<!DOCTYPE', '<html', '</html>', '<head', '</head>',
    '<body', '</body>',
]


def validate_fragment(fragment: str) -> None:
    """Validate a slide fragment for use with insert_slide()."""
    if not fragment or not fragment.strip():
        raise FragmentError("Fragment is empty")

    fragment_lower = fragment.lower()
    for tag in DOCUMENT_TAGS:
        if tag.lower() in fragment_lower:
            raise FragmentError(
                f"Fragment contains document-level tag {tag}"
            )

    # FSL-151: Count <section> with or without whitespace after tag name
    all_sections = len(re.findall(r'<section(?:\s|>)', fragment, re.IGNORECASE))
    parseable = parse_slides(fragment)

    if all_sections == 0:
        raise FragmentError("Fragment contains no <section> elements")

    if all_sections != len(parseable):
        raise FragmentError(
            f"Fragment has {all_sections} <section> elements but "
            f"only {len(parseable)} are parseable"
        )

    if len(parseable) == 0:
        raise FragmentError("Fragment contains no parseable slide sections")

    if len(parseable) > 1:
        raise FragmentError(
            f"Fragment contains {len(parseable)} slide sections; "
            f"insert_slide accepts exactly one"
        )


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------

def strict_validate(deck_html: str) -> List[str]:
    """Comprehensive structural validation. Returns list of failures."""
    failures = []

    sl = parse_slides(deck_html)
    sc = count_slides(deck_html)

    # FSL-150: zero-slide deck is not valid
    if sc == 0:
        failures.append("STRUCT-NO-SLIDES: deck has 0 slide sections")
        return failures  # no further checks possible

    if sc != len(sl):
        failures.append(f"STRUCT-001: count_slides({sc}) != parse_slides({len(sl)})")

    all_sections = len(re.findall(r'<section(?:\s|>)', deck_html, re.IGNORECASE))
    if sc != all_sections:
        failures.append(
            f"STRUCT-002: {all_sections} <section> elements but "
            f"only {sc} match the fixture parser"
        )

    nums = extract_slide_numbers(deck_html)
    if nums != list(range(1, sc + 1)):
        failures.append(
            f"STRUCT-003: positional numbers in document order {nums} "
            f"!= [1..{sc}]"
        )

    if set(nums) != set(range(1, sc + 1)):
        failures.append(
            f"STRUCT-004: positional number set {sorted(set(nums))} "
            f"!= {{1..{sc}}}"
        )

    for i, s in enumerate(sl):
        expected_class_num = s['comment_num']
        class_match = re.search(r'slide-(\d+)', s['class_str'])
        if class_match:
            class_num = int(class_match.group(1))
            if class_num != expected_class_num:
                failures.append(
                    f"STRUCT-005: slide {i+1} class number {class_num} "
                    f"!= comment number {expected_class_num}"
                )
        if s['counter_current'] != s['comment_num']:
            failures.append(
                f"STRUCT-006: slide {i+1} counter current {s['counter_current']} "
                f"!= slide number {s['comment_num']}"
            )
        if s['counter_total'] != sc:
            failures.append(
                f"STRUCT-007: slide {i+1} counter total {s['counter_total']} "
                f"!= slide count {sc}"
            )

    counter_nodes = COUNTER_PATTERN.findall(deck_html)
    if len(counter_nodes) != len(sl):
        failures.append(
            f"STRUCT-008: {len(counter_nodes)} <div class=\"counter\"> nodes "
            f"but {len(sl)} parsed slides"
        )

    ids = extract_data_ids(deck_html)
    nums_list = extract_slide_numbers(deck_html)
    positional_ids = [f"slide-{n:02d}" for n in nums_list]
    stable_ids = [i for i in ids if i not in positional_ids]
    if len(stable_ids) != len(set(stable_ids)):
        from collections import Counter
        dupes = [k for k, v in Counter(stable_ids).items() if v > 1]
        failures.append(f"STRUCT-009: duplicate stable data-slide-id: {dupes}")

    for marker in ['__OLD_', 'TMP_', 'MAP_', '__BM_']:
        if marker in deck_html:
            failures.append(f"STRUCT-010: temporary marker '{marker}' remains")
            break

    return failures


def require_valid_source(deck_html: str) -> None:
    """Strict source validation. Raises ValueError on any failure."""
    failures = strict_validate(deck_html)
    if failures:
        raise ValueError(
            f"Source deck validation failed ({len(failures)} issue(s)):\n"
            + "\n".join(f"  - {f}" for f in failures)
        )


def verify_operation(deck_html: str, expected_count: int,
                     check_data_id: bool = False) -> List[str]:
    """Post-operation validation. Return list of failures (empty = PASS)."""
    failures = strict_validate(deck_html)

    c = count_slides(deck_html)
    if c != expected_count:
        failures.append(f"Expected {expected_count} slides, got {c}")

    if check_data_id:
        ids = extract_data_ids(deck_html)
        if len(ids) != len(set(ids)):
            from collections import Counter
            dupes = [k for k, v in Counter(ids).items() if v > 1]
            failures.append(f"Duplicate data-slide-id: {dupes}")

    return failures


# ---------------------------------------------------------------------------
# Resequencing (FSL-149: targeted replacement, no content loss)
# ---------------------------------------------------------------------------

def resequence(deck_html: str) -> str:
    """Renumber positional metadata sequentially from 1.

    Updates: slide class numbers, HTML comments, counter values,
    and positional data-slide-id values (slide-NN format).

    Preserves: ALL HTML content (extra classes, attributes, styles,
    images, multiple paragraphs, cards, SVG, scripts, etc.).
    Uses targeted replacement within existing slide HTML.
    """
    slides = parse_slides(deck_html)
    total = len(slides)

    if total == 0:
        return deck_html

    result = deck_html
    for idx in range(total - 1, -1, -1):
        s = slides[idx]
        new_num = idx + 1
        old_total = s['counter_total']
        new_html = s['full_html']

        # Targeted replacements (FSL-149)
        old_str = f"{s['comment_num']:02d}"
        new_str = f"{new_num:02d}"
        total_str = f"{total:02d}"

        # Class
        new_html = new_html.replace(f'slide-{old_str}', f'slide-{new_str}', 1)

        # Comment
        new_html = new_html.replace(f'SLIDE {old_str}', f'SLIDE {new_str}', 1)

        # Positional data-slide-id only
        new_html = new_html.replace(
            f'data-slide-id="slide-{old_str}"',
            f'data-slide-id="slide-{new_str}"',
        )

        # Counter — match the exact padded format
        new_html = new_html.replace(
            f'>{old_str} / ',
            f'>{new_str} / ',
        )
        if old_total != total:
            new_html = new_html.replace(
                f' {old_total:02d}<',
                f' {total_str}<',
            )

        result = _replace_slide_in_deck(result, s['full_html'], new_html)

    return result


# ---------------------------------------------------------------------------
# Structural operations
# ---------------------------------------------------------------------------

def insert_slide(deck_html: str, position: int, new_slide_html: str) -> str:
    """Insert a new slide at 1-based position, then resequence."""
    require_valid_source(deck_html)
    validate_fragment(new_slide_html)

    slides = parse_slides(deck_html)
    total = len(slides)

    if position < 1 or position > total + 1:
        raise ValueError(f"Position {position} out of range [1, {total + 1}]")

    if position == total + 1:
        idx = deck_html.rfind('</section>')
        if idx < 0:
            raise ValueError("No </section> found")
        deck_html = (
            deck_html[:idx + len('</section>')] + '\n' +
            new_slide_html.rstrip('\n') +
            deck_html[idx + len('</section>'):]
        )
    else:
        target = slides[position - 1]['full_html']
        idx = deck_html.find(target)
        if idx < 0:
            raise ValueError(f"Could not find slide at position {position}")
        deck_html = deck_html[:idx] + new_slide_html.rstrip('\n') + '\n' + deck_html[idx:]

    result = resequence(deck_html)

    if count_doctypes(result) != 1:
        raise RuntimeError(f"Result has {count_doctypes(result)} DOCTYPE declarations")

    post_failures = verify_operation(result, total + 1, check_data_id=True)
    if post_failures:
        raise RuntimeError(
            f"Post-condition validation failed:\n"
            + "\n".join(f"  - {f}" for f in post_failures)
        )

    return result


def delete_slide(deck_html: str, position: int) -> str:
    """Delete the slide at 1-based position, then resequence."""
    require_valid_source(deck_html)

    slides = parse_slides(deck_html)
    total = len(slides)

    if position < 1 or position > total:
        raise ValueError(f"Position {position} out of range [1, {total}]")

    target = slides[position - 1]['full_html']
    idx = deck_html.find(target)
    if idx < 0:
        raise ValueError(f"Could not find slide at position {position}")

    deck_html = deck_html[:idx] + deck_html[idx + len(target):]
    result = resequence(deck_html)

    post_failures = verify_operation(result, total - 1, check_data_id=True)
    if post_failures:
        raise RuntimeError(
            f"Post-condition validation failed:\n"
            + "\n".join(f"  - {f}" for f in post_failures)
        )

    return result


def reorder_slides(deck_html: str, from_pos: int, to_pos: int) -> str:
    """Move a slide from 1-based from_pos to 1-based to_pos."""
    require_valid_source(deck_html)

    slides = parse_slides(deck_html)
    total = len(slides)

    if from_pos < 1 or from_pos > total:
        raise ValueError(f"from_pos {from_pos} out of range [1, {total}]")
    if to_pos < 1 or to_pos > total:
        raise ValueError(f"to_pos {to_pos} out of range [1, {total}]")

    moving = slides[from_pos - 1]['full_html']
    idx = deck_html.find(moving)
    if idx < 0:
        raise ValueError(f"Could not find slide at position {from_pos}")

    deck_html = deck_html[:idx] + deck_html[idx + len(moving):]

    new_slides = parse_slides(deck_html)
    if to_pos == 1:
        body_end = deck_html.find('<body>') + len('<body>\n')
        deck_html = deck_html[:body_end] + moving.rstrip('\n') + '\n' + deck_html[body_end:]
    elif to_pos > len(new_slides):
        idx = deck_html.rfind('</section>')
        deck_html = (
            deck_html[:idx + len('</section>')] + '\n' +
            moving.rstrip('\n') +
            deck_html[idx + len('</section>'):]
        )
    else:
        target = new_slides[to_pos - 1]['full_html']
        idx = deck_html.find(target)
        deck_html = deck_html[:idx] + moving.rstrip('\n') + '\n' + deck_html[idx:]

    result = resequence(deck_html)

    post_failures = verify_operation(result, total, check_data_id=True)
    if post_failures:
        raise RuntimeError(
            f"Post-condition validation failed:\n"
            + "\n".join(f"  - {f}" for f in post_failures)
        )

    return result


# ---------------------------------------------------------------------------
# Batch renumbering (FSL-148: reorders sections to match mapping)
# ---------------------------------------------------------------------------

class MappingError(ValueError):
    """Raised when a batch_renumber mapping is invalid."""


def batch_renumber(deck_html: str, mapping: Dict[int, int]) -> str:
    """Collision-safe batch renumbering with exact complete mapping.

    CONTRACT:
      - mapping must be a complete bijection from every existing positional
        slide number to every desired final positional number.
      - Keys must exactly equal the current set of positional slide numbers.
      - Values must be unique.
      - Values must be exactly {1..N} where N = number of slides.
      - Partial mappings, missing keys, unknown keys, duplicate targets,
        gaps, out-of-range values all fail with MappingError.

    BEHAVIOR (FSL-148):
      - The function PHYSICALLY REORDERS sections to match the mapping.
        If mapping says 3→4 and 4→3, the sections at positions 3 and 4
        are swapped, and all positional numbering is restored to 1..N.
      - This ensures post-condition (STRUCT-003: ordered numbers) always
        passes for any valid complete bijection mapping.
      - Use this for reordering via mapping. For single-item moves,
        reorder_slides() is also available.

    Example valid mapping (swap slides 3 and 4 in a 5-slide deck):
      {1: 1, 2: 2, 3: 4, 4: 3, 5: 5}
    """
    require_valid_source(deck_html)

    all_slides = parse_slides(deck_html)
    total = len(all_slides)
    current_nums = set(s['comment_num'] for s in all_slides)
    map_keys = set(mapping.keys())
    map_vals = set(mapping.values())

    # Validate mapping completeness
    if map_keys != current_nums:
        missing = current_nums - map_keys
        extra = map_keys - current_nums
        parts = []
        if missing:
            parts.append(f"missing keys: {sorted(missing)}")
        if extra:
            parts.append(f"unknown keys: {sorted(extra)}")
        raise MappingError(
            f"Mapping keys must exactly match current slide numbers "
            f"{sorted(current_nums)}. {'; '.join(parts)}"
        )

    if len(map_vals) != len(mapping):
        from collections import Counter
        dupes = [k for k, v in Counter(mapping.values()).items() if v > 1]
        raise MappingError(
            f"Mapping values must be unique; duplicate targets: {sorted(dupes)}"
        )

    expected_values = set(range(1, total + 1))
    if map_vals != expected_values:
        extra_vals = map_vals - expected_values
        missing_vals = expected_values - map_vals
        parts = []
        if extra_vals:
            parts.append(f"out-of-range values: {sorted(extra_vals)}")
        if missing_vals:
            parts.append(f"missing values: {sorted(missing_vals)}")
        raise MappingError(
            f"Mapping values must be exactly {{1..{total}}}. "
            f"{' '.join(parts)}"
        )

    # Build the inverse mapping: {new_position: old_slide}
    inverse = {v: k for k, v in mapping.items()}
    # order_inverse: for each target position 1..N, which old number's content goes there
    ordered_content: List[str] = []
    for target_pos in range(1, total + 1):
        old_num = inverse[target_pos]
        # Find the slide with this old number
        slide = next(s for s in all_slides if s['comment_num'] == old_num)
        ordered_content.append(slide['full_html'])

    # Rebuild the deck by replacing sections in REVERSE order
    # (last to first) to avoid content duplication issues when
    # the same source content appears at multiple target positions.
    result = deck_html
    for idx in range(total - 1, -1, -1):
        s = all_slides[idx]
        new_content = ordered_content[idx]
        result = _replace_slide_in_deck(result, s['full_html'], new_content)

    # Now renumber everything sequentially
    result = resequence(result)

    # Verify no marker tokens remain
    for marker in ['__BM_', '__OLD_', 'TMP_', 'MAP_']:
        if marker in result:
            raise RuntimeError(f"Marker '{marker}' remains after batch_renumber")

    # Post-condition validation
    post_failures = verify_operation(result, total, check_data_id=True)
    if post_failures:
        raise RuntimeError(
            f"Post-condition validation failed:\n"
            + "\n".join(f"  - {f}" for f in post_failures)
        )

    return result
