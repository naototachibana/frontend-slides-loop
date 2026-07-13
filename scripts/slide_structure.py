"""
slide_structure.py — Parse, validate, and transform synthetic
Frontend Slides fixture decks. Standard library only, no browser.

Scope: deterministic fixture/test utility. NOT a general-purpose
HTML presentation editor. Supports a controlled fixture grammar.
"""
import re
from typing import List, Dict, Tuple, Set


# ---------------------------------------------------------------------------
# Fixture generation
# ---------------------------------------------------------------------------

def make_slide_fragment(num: int, total: int = 0,
                        data_id: str = None,
                        payload_text: str = None) -> str:
    """Return exactly one <section>...</section> fragment.

    Args:
        num: Slide number for class and counter.
        total: Total slides for counter denominator (default: num).
        data_id: Stable non-positional ID (default: None).
        payload_text: Unique content inside the slide (default: None).
    """
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


def make_deck(num_slides: int, stable_ids: bool = True,
              payload_content: str = None) -> str:
    """Create a synthetic Frontend Slides deck.

    When stable_ids=True, data-slide-id uses non-positional IDs
    (topic-001, ...) that MUST be preserved through operations.

    When stable_ids=False, data-slide-id uses positional IDs (slide-01...).

    payload_content: optional extra text to embed in each slide's
    <p> element for payload-preservation testing.
    """
    slides = []
    for i in range(1, num_slides + 1):
        did = f"topic-{i:03d}" if stable_ids else f"slide-{i:02d}"
        payload = payload_content or f"payload-{i:03d}"
        slides.append(make_slide_fragment(i, num_slides, did, payload))
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
        payload = ""
        pm = re.search(r'<p>(.*?)</p>', inner)
        if pm:
            payload = pm.group(1)
        slides.append({
            'full_html': m.group(0),
            'class_str': m.group(2),
            'attrs': attrs,
            'comment_num': int(m.group(4)),
            'counter_current': int(m.group(6)),
            'counter_total': int(m.group(7)),
            'data_id': did,
            'payload': payload,
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
    for s in parse_slides(deck_html):
        if s['payload']:
            yield s['payload']


def count_slides(deck_html: str) -> int:
    return len(SECTION_PATTERN.findall(deck_html))


def count_doctypes(deck_html: str) -> int:
    return len(re.findall(r'<!DOCTYPE\s+html>', deck_html, re.IGNORECASE))


# ---------------------------------------------------------------------------
# Per-slide replacement helper (FSL-126: never rewrite payload text)
# ---------------------------------------------------------------------------

def _replace_slide_in_deck(deck_html: str, old_slide_html: str,
                           new_slide_html: str) -> str:
    """Replace one slide's HTML in the deck document.

    Uses str.replace(..., 1) on the known old_slide_html substring.
    This is safe because old_slide_html comes from parse_slides() which
    extracts the exact substring via SLIDE_PATTERN.finditer.
    """
    return deck_html.replace(old_slide_html, new_slide_html, 1)


def _build_updated_slide(
    slide: Dict,
    new_num: int,
    total: int,
    new_data_id: str = None,
) -> str:
    """Build a replacement <section> for a parsed slide with updated
    positional metadata. Preserves non-positional data-slide-id and
    payload text exactly.

    Positional updates:
      - class: slide-NN
      - HTML comment: SLIDE NN
      - counter: NN / TT
      - positional data-slide-id (slide-NN format)

    Non-positional data-slide-id (topic-NNN, etc.) is preserved
    via the new_data_id parameter. If new_data_id is None, the
    original data_id is kept (for stable IDs).
    """
    if new_data_id is None:
        new_data_id = slide['data_id']
    payload_text = slide['payload'] if slide['payload'] else None
    return make_slide_fragment(
        new_num, total, new_data_id, payload_text
    )


# ---------------------------------------------------------------------------
# Fragment validation
# ---------------------------------------------------------------------------

class FragmentError(ValueError):
    """Raised when a slide fragment is invalid for insertion."""


# Document-level tags to detect (case-insensitive)
DOCUMENT_TAGS = [
    '<!DOCTYPE', '<html', '</html>', '<head', '</head>',
    '<body', '</body>',
]


def validate_fragment(fragment: str) -> None:
    """Validate a slide fragment for use with insert_slide().

    Raises FragmentError if:
    - fragment is empty
    - fragment contains document-level tags (case-insensitive, attribute-aware)
    - fragment has zero or more than one parseable slide sections
    - fragment has any <section> that is not parseable by the fixture parser
    """
    if not fragment or not fragment.strip():
        raise FragmentError("Fragment is empty")

    # Case-insensitive document tag detection (FSL-128)
    fragment_lower = fragment.lower()
    for tag in DOCUMENT_TAGS:
        if tag.lower() in fragment_lower:
            raise FragmentError(
                f"Fragment contains document-level tag {tag}; "
                f"use make_slide_fragment() to create a valid section fragment"
            )

    # Count all <section> elements and parseable slides
    all_sections = re.findall(r'<section\s', fragment, re.IGNORECASE)
    parseable = parse_slides(fragment)

    if len(all_sections) == 0:
        raise FragmentError(
            "Fragment contains no <section> elements"
        )

    if len(all_sections) != len(parseable):
        raise FragmentError(
            f"Fragment has {len(all_sections)} <section> element(s) but "
            f"only {len(parseable)} are parseable by the fixture parser. "
            f"All sections must match the fixture grammar."
        )

    if len(parseable) == 0:
        raise FragmentError(
            "Fragment contains no parseable slide sections"
        )

    if len(parseable) > 1:
        raise FragmentError(
            f"Fragment contains {len(parseable)} slide sections; "
            f"insert_slide accepts exactly one"
        )


# ---------------------------------------------------------------------------
# Structural validation (FSL-121, FSL-127, FSL-129)
# ---------------------------------------------------------------------------

def strict_validate(deck_html: str) -> List[str]:
    """Comprehensive structural validation. Returns list of failures.

    Invariants (FSL-121):
      1. count_slides == len(parse_slides) == expected_count
      2. Every <section> is parseable by the fixture parser
      3. Every positional class-slide-NN is unique (as set equals 1..N)
      4. Positional numbers in document order = [1, 2, ..., N] (FSL-129)
      5. Each slide's class number, comment number, and counter-current agree
      6. Every counter total equals N
      7. No extra counter-like strings outside parsed slides
      8. Stable data-slide-id values are unique when present
      9. No temporary token markers remain
    """
    failures = []

    sl = parse_slides(deck_html)
    sc = count_slides(deck_html)

    # 1. count_slides == len(parse_slides)
    if sc != len(sl):
        failures.append(f"STRUCT-001: count_slides({sc}) != parse_slides({len(sl)})")

    # Count ALL <section> elements (not just parseable ones)
    all_sections = len(re.findall(r'<section\s', deck_html, re.IGNORECASE))
    if sc != all_sections:
        failures.append(
            f"STRUCT-002: {all_sections} <section> elements but "
            f"only {sc} match the fixture parser"
        )

    # 4. Positional numbers must be [1, 2, ..., N] in document order (FSL-129)
    nums = extract_slide_numbers(deck_html)
    if sc > 0 and nums != list(range(1, sc + 1)):
        failures.append(
            f"STRUCT-003: positional numbers in document order {nums} "
            f"!= [1..{sc}]"
        )

    # 3. Unique positional numbers (set must equal 1..N)
    if sc > 0 and set(nums) != set(range(1, sc + 1)):
        failures.append(
            f"STRUCT-004: positional number set {sorted(set(nums))} "
            f"!= {{1..{sc}}}"
        )

    # 5 & 6. Per-slide agreement
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

    # 7. Extra counter-like strings outside parsed slides
    # Only count <div class="counter"> nodes (FSL-126)
    counter_nodes = COUNTER_PATTERN.findall(deck_html)
    if len(counter_nodes) != len(sl):
        failures.append(
            f"STRUCT-008: {len(counter_nodes)} <div class=\"counter\"> nodes "
            f"but {len(sl)} parsed slides"
        )

    # 8. Stable data-slide-id uniqueness
    ids = extract_data_ids(deck_html)
    positional_ids = [f"slide-{n:02d}" for n in nums]
    stable_ids = [i for i in ids if i not in positional_ids]
    if len(stable_ids) != len(set(stable_ids)):
        from collections import Counter
        dupes = [k for k, v in Counter(stable_ids).items() if v > 1]
        failures.append(f"STRUCT-009: duplicate stable data-slide-id: {dupes}")

    # 9. No temporary marker tokens
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
            f"Source deck validation failed ({len(failures)} issue(s)):\n" +
            "\n".join(f"  - {f}" for f in failures)
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
# Resequencing (FSL-126: per-slide replacement, no global regex)
# ---------------------------------------------------------------------------

def resequence(deck_html: str) -> str:
    """Renumber positional metadata sequentially from 1.

    Updates: slide class numbers, HTML comments, counter elements,
    and positional data-slide-id values (slide-NN format).

    Preserves: non-positional data-slide-id (topic-NNN format),
    payload text, all other content byte-for-byte.

    Uses per-slide replacement — never applies regex to payload text.
    """
    slides = parse_slides(deck_html)
    total = len(slides)

    if total == 0:
        return deck_html

    # Replace slides one by one (backward to preserve positions)
    for idx in range(total - 1, -1, -1):
        s = slides[idx]
        new_num = idx + 1
        new_html = _build_updated_slide(s, new_num, total)
        deck_html = _replace_slide_in_deck(deck_html, s['full_html'], new_html)

    return deck_html


# ---------------------------------------------------------------------------
# Structural operations (FSL-127: pre/post validation)
# ---------------------------------------------------------------------------

def insert_slide(deck_html: str, position: int, new_slide_html: str) -> str:
    """Insert a new slide at 1-based position, then resequence.

    Pre-validates source deck and fragment.
    Post-validates result.
    """
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

    # Post-condition: single DOCTYPE
    if count_doctypes(result) != 1:
        raise RuntimeError(f"Result has {count_doctypes(result)} DOCTYPE declarations")

    # Post-condition validation
    post_failures = verify_operation(
        result, total + 1, check_data_id=True
    )
    if post_failures:
        raise RuntimeError(
            f"Post-condition validation failed:\n" +
            "\n".join(f"  - {f}" for f in post_failures)
        )

    return result


def delete_slide(deck_html: str, position: int) -> str:
    """Delete the slide at 1-based position, then resequence.

    Pre-validates source deck. Post-validates result.
    """
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

    post_failures = verify_operation(
        result, total - 1, check_data_id=True
    )
    if post_failures:
        raise RuntimeError(
            f"Post-condition validation failed:\n" +
            "\n".join(f"  - {f}" for f in post_failures)
        )

    return result


def reorder_slides(deck_html: str, from_pos: int, to_pos: int) -> str:
    """Move a slide from 1-based from_pos to 1-based to_pos.

    Pre-validates source deck. Post-validates result.
    """
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

    post_failures = verify_operation(
        result, total, check_data_id=True
    )
    if post_failures:
        raise RuntimeError(
            f"Post-condition validation failed:\n" +
            "\n".join(f"  - {f}" for f in post_failures)
        )

    return result


# ---------------------------------------------------------------------------
# Exact batch renumbering (FSL-125, FSL-126)
# ---------------------------------------------------------------------------

class MappingError(ValueError):
    """Raised when a batch_renumber mapping is invalid."""


def batch_renumber(deck_html: str, mapping: Dict[int, int]) -> str:
    """Collision-safe batch renumbering with exact complete mapping.

    CONTRACT (FSL-125):
      - mapping must be a complete bijection from every existing positional
        slide number to every desired final positional number.
      - Keys must exactly equal the current set of positional slide numbers.
      - Values must be unique.
      - Values must be exactly {1..N} where N = number of slides.
      - Partial mappings, missing keys, unknown keys, duplicate targets,
        gaps, out-of-range values, and non-monotonic values all fail
        with MappingError.

    Example valid mapping (swap slides 3 and 4 in a 5-slide deck):
      {1: 1, 2: 2, 3: 4, 4: 3, 5: 5}

    Updates: slide class numbers, HTML comments, counter elements,
    and positional data-slide-id values.

    Preserves: non-positional data-slide-id values (topic-NNN), payload text.
    Uses per-slide replacement — never applies regex to payload text.
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

    # FSL-125: values must be exactly {1..N}
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

    # Replace slides one by one with their mapped values
    result = deck_html
    for idx in range(total - 1, -1, -1):
        s = all_slides[idx]
        old_num = s['comment_num']
        new_num = mapping[old_num]
        new_html = _build_updated_slide(s, new_num, total)
        result = _replace_slide_in_deck(result, s['full_html'], new_html)

    # Verify no marker tokens remain (FSL-131)
    for marker in ['__BM_', '__OLD_', 'TMP_', 'MAP_']:
        if marker in result:
            raise RuntimeError(f"Marker '{marker}' remains after batch_renumber")

    # Post-condition validation
    post_failures = verify_operation(result, total, check_data_id=True)
    if post_failures:
        raise RuntimeError(
            f"Post-condition validation failed:\n" +
            "\n".join(f"  - {f}" for f in post_failures)
        )

    return result
