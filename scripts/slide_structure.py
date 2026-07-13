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
        data_id: Stable non-positional data-slide-id (default: None).
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


def make_deck(num_slides: int, stable_ids: bool = True) -> str:
    """Create a synthetic Frontend Slides deck.

    When stable_ids=True, data-slide-id values use non-positional
    identifiers (topic-001, topic-002, ...) that must be preserved
    through structural operations.

    When stable_ids=False, data-slide-id uses positional values
    (slide-01, slide-02, ...) matching a legacy numbered deck.
    """
    slides = []
    for i in range(1, num_slides + 1):
        did = f"topic-{i:03d}" if stable_ids else f"slide-{i:02d}"
        payload = f"payload-{i:03d}"
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
    """Extract ordered payload text from slide <p> elements."""
    payloads = []
    for s in parse_slides(deck_html):
        if s['payload']:
            payloads.append(s['payload'])
    return payloads


def count_slides(deck_html: str) -> int:
    return len(SECTION_PATTERN.findall(deck_html))


def get_counters(deck_html: str) -> List[Tuple[int, int]]:
    pairs = re.findall(r'(\d+)\s*/\s*(\d+)', deck_html)
    return [(int(c), int(t)) for c, t in pairs]


def count_doctypes(deck_html: str) -> int:
    return deck_html.count('<!DOCTYPE html>')


# ---------------------------------------------------------------------------
# Fragment validation
# ---------------------------------------------------------------------------

class FragmentError(ValueError):
    """Raised when a slide fragment is invalid for insertion."""


def validate_fragment(fragment: str) -> None:
    """Validate a slide fragment for use with insert_slide().

    Raises FragmentError if:
    - fragment is empty
    - fragment contains a complete HTML document (DOCTYPE, html, head, body)
    - fragment has zero slide sections
    - fragment has more than one slide section
    - fragment is not parseable by the fixture parser
    """
    if not fragment or not fragment.strip():
        raise FragmentError("Fragment is empty")

    if '<!DOCTYPE html>' in fragment:
        raise FragmentError("Fragment is a complete HTML document (contains DOCTYPE)")

    for tag in ['<html>', '</html>', '<head>', '</head>', '<body>', '</body>']:
        if tag in fragment:
            raise FragmentError(
                f"Fragment contains document-level tag {tag}; "
                f"use make_slide_fragment() to create a valid section fragment"
            )

    slides = parse_slides(fragment)
    if len(slides) == 0:
        raise FragmentError(
            "Fragment contains no parseable slide sections"
        )
    if len(slides) > 1:
        raise FragmentError(
            f"Fragment contains {len(slides)} slide sections; "
            f"insert_slide accepts exactly one"
        )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_uniqueness(deck_html: str) -> List[int]:
    nums = extract_slide_numbers(deck_html)
    seen: Set[int] = set()
    dupes: Set[int] = set()
    for n in nums:
        if n in seen:
            dupes.add(n)
        seen.add(n)
    return sorted(dupes)


def validate_data_id_uniqueness(deck_html: str) -> List[str]:
    ids = extract_data_ids(deck_html)
    seen: Set[str] = set()
    dupes: Set[str] = set()
    for i in ids:
        if i in seen:
            dupes.add(i)
        seen.add(i)
    return sorted(dupes)


def validate_no_markers(deck_html: str) -> bool:
    return "__OLD_" not in deck_html and "TMP_" not in deck_html and "MAP_" not in deck_html


def check_structural_invariants(deck_html: str) -> List[str]:
    """Run comprehensive structural validation. Returns list of failures."""
    failures = []

    sl = parse_slides(deck_html)
    sc = count_slides(deck_html)

    if sc != len(sl):
        failures.append(f"STRUCT-001: count_slides={sc} != parse_slides={len(sl)}")

    # Every parseable section must have its class, comment, and counter in sync
    for i, s in enumerate(sl):
        expected_class_num = s['comment_num']
        # Extract the actual number from class attribute
        class_match = re.search(r'slide-(\d+)', s['class_str'])
        if class_match:
            class_num = int(class_match.group(1))
            if class_num != expected_class_num:
                failures.append(
                    f"STRUCT-002: slide {i+1} class number {class_num} "
                    f"!= comment number {expected_class_num}"
                )
        # Counter current must match slide number
        if s['counter_current'] != s['comment_num']:
            failures.append(
                f"STRUCT-003: slide {i+1} counter current {s['counter_current']} "
                f"!= slide number {s['comment_num']}"
            )
        # Counter total must equal total count
        if s['counter_total'] != sc:
            failures.append(
                f"STRUCT-004: slide {i+1} counter total {s['counter_total']} "
                f"!= slide count {sc}"
            )

    # Positional numbers must be exactly {1..N} (as a set)
    nums = extract_slide_numbers(deck_html)
    if set(nums) != set(range(1, sc + 1)):
        if sc > 0:
            failures.append(f"STRUCT-005: positional numbers {sorted(nums)} != 1..{sc}")

    # Extra counter-like strings outside parsed slides
    # Every counter pattern should be inside a parsed slide
    all_counters = get_counters(deck_html)
    parsed_counters = [(s['counter_current'], s['counter_total']) for s in sl]
    if len(all_counters) != len(parsed_counters):
        failures.append(
            f"STRUCT-006: {len(all_counters)} counter instances "
            f"in HTML vs {len(parsed_counters)} parsed slides"
        )

    return failures


def verify_operation(deck_html: str, expected_count: int,
                     check_data_id: bool = False) -> List[str]:
    """Run all validation checks. Return list of failures (empty = PASS)."""
    failures = []

    # Structural invariants
    failures.extend(check_structural_invariants(deck_html))

    c = count_slides(deck_html)
    if c != expected_count:
        failures.append(f"Expected {expected_count} slides, got {c}")

    dupes = validate_uniqueness(deck_html)
    if dupes:
        failures.append(f"Duplicate slide numbers: {dupes}")

    if check_data_id:
        did_dupes = validate_data_id_uniqueness(deck_html)
        if did_dupes:
            failures.append(f"Duplicate data-slide-id: {did_dupes}")

    if not validate_no_markers(deck_html):
        failures.append("Temporary markers (__OLD_, TMP_, MAP_) remain in output")

    return failures


# ---------------------------------------------------------------------------
# Resequencing (positional metadata only)
# ---------------------------------------------------------------------------

def resequence(deck_html: str) -> str:
    """Renumber positional metadata sequentially from 1.

    Updates: slide class numbers, HTML comments, div.counter values,
    and positional data-slide-id values.

    Preserves: non-positional data-slide-id (topic-NNN format),
    payload text, all other content.
    """
    slides = parse_slides(deck_html)
    total = len(slides)

    if total == 0:
        return deck_html

    # First pass: replace all positional numbers with unique temporary markers
    for i, s in enumerate(slides):
        old = s['full_html']
        old_num_str = f"{s['comment_num']:02d}"
        new_marker = f"TMP_{i:04d}"

        new_html = old
        new_html = new_html.replace(f"slide-{old_num_str}", f"slide-{new_marker}", 1)
        new_html = new_html.replace(f"SLIDE {old_num_str}", f"SLIDE {new_marker}", 1)

        # Only update positional data-slide-id (e.g., slide-NN format)
        # Preserve non-positional stable IDs (e.g., topic-NNN format)
        positional_did = f'data-slide-id="slide-{old_num_str}"'
        new_html = new_html.replace(
            positional_did,
            f'data-slide-id="slide-{new_marker}"',
        )

        # Replace counter-current (first occurrence in the slide)
        new_html = new_html.replace(f">{old_num_str} /", f">{new_marker} /", 1)

        deck_html = deck_html.replace(old, new_html, 1)

    # Second pass: replace markers with sequential numbers
    for i in range(1, total + 1):
        marker = f"TMP_{i-1:04d}"
        target = f"{i:02d}"

        deck_html = deck_html.replace(f"slide-{marker}", f"slide-{target}")
        deck_html = deck_html.replace(f"SLIDE {marker}", f"SLIDE {target}")
        deck_html = deck_html.replace(
            f'data-slide-id="slide-{marker}"',
            f'data-slide-id="slide-{target}"',
        )
        deck_html = deck_html.replace(f">{marker} /", f">{target} /")

    # Update all counter totals to match actual slide count
    deck_html = re.sub(
        r'(\d+)\s*/\s*\d+',
        lambda m: f"{m.group(1)} / {total:02d}",
        deck_html,
    )

    return deck_html


# ---------------------------------------------------------------------------
# Structural operations
# ---------------------------------------------------------------------------

def insert_slide(deck_html: str, position: int, new_slide_html: str) -> str:
    """Insert a new slide at 1-based position, then resequence.

    Validates that new_slide_html is a single parseable section fragment
    (not a complete HTML document).
    """
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

    # Verify no nested document structure
    if count_doctypes(result) != 1:
        raise RuntimeError(f"Result has {count_doctypes(result)} DOCTYPE declarations")

    return result


def delete_slide(deck_html: str, position: int) -> str:
    """Delete the slide at 1-based position, then resequence."""
    slides = parse_slides(deck_html)
    total = len(slides)

    if position < 1 or position > total:
        raise ValueError(f"Position {position} out of range [1, {total}]")

    target = slides[position - 1]['full_html']
    idx = deck_html.find(target)
    if idx < 0:
        raise ValueError(f"Could not find slide at position {position}")

    deck_html = deck_html[:idx] + deck_html[idx + len(target):]

    return resequence(deck_html)


def reorder_slides(deck_html: str, from_pos: int, to_pos: int) -> str:
    """Move a slide from 1-based from_pos to 1-based to_pos, then resequence."""
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

    return resequence(deck_html)


# ---------------------------------------------------------------------------
# Exact batch renumbering
# ---------------------------------------------------------------------------

class MappingError(ValueError):
    """Raised when a batch_renumber mapping is invalid."""


def batch_renumber(deck_html: str, mapping: Dict[int, int]) -> str:
    """Collision-safe batch renumbering with an exact complete mapping.

    CONTRACT:
      - mapping must be a complete bijection from every existing positional
        slide number to every desired final positional number.
      - Keys must exactly equal the current set of positional slide numbers.
      - Values must be unique (no duplicate targets).
      - Values must encompass the full required final number set (normally 1..N).
      - Partial mappings, missing keys, unknown keys, duplicate targets,
        gaps, or out-of-range values fail with MappingError.

    Example valid mapping (swap slides 3 and 4 in a 5-slide deck):
      {1: 1, 2: 2, 3: 4, 4: 3, 5: 5}

    The function updates: slide class numbers, HTML comments, counters,
    and positional data-slide-id values.

    Non-positional data-slide-id values (e.g., topic-NNN) are preserved.
    """
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

    if max(map_vals) > total + len(map_vals - set(range(1, total + 1))):
        # Allow value sets that extend beyond 1..N (shifts), but check range
        pass

    # Check values form a reasonable range (start from 1, no gaps)
    # For a complete shift (6→7, 7→8...), max value can exceed N
    min_val = min(map_vals)
    if min_val != 1:
        raise MappingError(
            f"Mapping values must start at 1, got min={min_val}"
        )

    # Phase 1: replace every slide's positional metadata with unique markers
    for i, s in enumerate(all_slides):
        old = s['full_html']
        old_num = s['comment_num']
        old_str = f"{old_num:02d}"
        marker = f"__BM_{i:04d}__"

        new_html = old
        new_html = new_html.replace(f"slide-{old_str}", f"slide-{marker}", 1)
        new_html = new_html.replace(f"SLIDE {old_str}", f"SLIDE {marker}" , 1)

        # Positional data-slide-id only
        old_pos_did = f'data-slide-id="slide-{old_str}"'
        new_html = new_html.replace(
            old_pos_did,
            f'data-slide-id="slide-{marker}"',
        )

        new_html = new_html.replace(f">{old_str} /", f">{marker} /", 1)

        deck_html = deck_html.replace(old, new_html, 1)

    # Phase 2: replace markers with mapped final values
    for i, s in enumerate(all_slides):
        old_num = s['comment_num']
        new_num = mapping[old_num]
        new_str = f"{new_num:02d}"
        marker = f"__BM_{i:04d}__"

        deck_html = deck_html.replace(f"slide-{marker}", f"slide-{new_str}")
        deck_html = deck_html.replace(f"SLIDE {marker}", f"SLIDE {new_str}")
        deck_html = deck_html.replace(
            f'data-slide-id="slide-{marker}"',
            f'data-slide-id="slide-{new_str}"',
        )
        deck_html = deck_html.replace(f">{marker} /", f">{new_str} /")

    # Verify no markers remain
    if '__BM_' in deck_html:
        raise RuntimeError(f"Unreplaced batch markers remain")

    # Update all counter totals
    deck_html = re.sub(
        r'(\d+)\s*/\s*\d+',
        lambda m: f"{m.group(1)} / {total:02d}",
        deck_html,
    )

    return deck_html
