"""
slide_structure.py — Parse, validate, and transform synthetic
Frontend Slides fixture decks. Standard library only, no browser.
"""
import re
from typing import List, Dict, Tuple, Optional, Set


# ---------------------------------------------------------------------------
# Fixture generation
# ---------------------------------------------------------------------------

def make_deck(num_slides: int, use_data_id: bool = False) -> str:
    """Create a synthetic Frontend Slides deck with numbered slides."""
    slides = []
    for i in range(1, num_slides + 1):
        cls = f"slide slide-{i:02d}"
        sid = f' data-slide-id="slide-{i:02d}"' if use_data_id else ""
        slides.append(
            f'    <section class="{cls}"{sid}>\n'
            f'      <!-- SLIDE {i:02d} -->\n'
            f'      <div class="counter">{i:02d} / {num_slides:02d}</div>\n'
            f'    </section>'
        )
    return "<!DOCTYPE html>\n<html>\n<body>\n" + "\n".join(slides) + "\n</body>\n</html>\n"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

SLIDE_PATTERN = re.compile(
    r'(<section\s+class="([^"]*)"(.*?)>)\s*'
    r'<!--\s*SLIDE\s+(\d+)\s*-->\s*'
    r'<div\s+class="counter">(\d+)\s*/\s*(\d+)</div>\s*'
    r'</section>',
    re.DOTALL,
)

SECTION_PATTERN = re.compile(
    r'<section[^>]*class="[^"]*slide-\d+[^"]*"[^>]*>',
)


def parse_slides(deck_html: str) -> List[Dict]:
    """Extract ordered slide data from a fixture deck."""
    slides = []
    for m in SLIDE_PATTERN.finditer(deck_html):
        attrs = m.group(3)
        did = None
        did_m = re.search(r'data-slide-id="([^"]*)"', attrs)
        if did_m:
            did = did_m.group(1)
        slides.append({
            'full_html': m.group(0),
            'class_str': m.group(2),
            'attrs': attrs,
            'comment_num': int(m.group(4)),
            'counter_current': int(m.group(5)),
            'counter_total': int(m.group(6)),
            'data_id': did,
        })
    return slides


def extract_slide_numbers(deck_html: str) -> List[int]:
    """Extract ordered positional slide numbers from section elements."""
    return [int(s) for s in re.findall(
        r'<section[^>]*class="[^"]*slide-(\d+)[^"]*"[^>]*>',
        deck_html,
    )]


def extract_data_ids(deck_html: str) -> List[str]:
    return re.findall(r'data-slide-id="([^"]*)"', deck_html)


def count_slides(deck_html: str) -> int:
    return len(SECTION_PATTERN.findall(deck_html))


def get_counters(deck_html: str) -> List[Tuple[int, int]]:
    pairs = re.findall(r'(\d+)\s*/\s*(\d+)', deck_html)
    return [(int(c), int(t)) for c, t in pairs]


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


def validate_continuity(deck_html: str) -> List[int]:
    nums = extract_slide_numbers(deck_html)
    if not nums:
        return []
    expected = list(range(min(nums), max(nums) + 1))
    return sorted(set(expected) - set(nums))


def validate_no_markers(deck_html: str) -> bool:
    return "__OLD_" not in deck_html


def verify_operation(deck_html: str, expected_count: int,
                     check_data_id: bool = False) -> List[str]:
    """Run all validation checks. Return list of failures (empty = PASS)."""
    failures = []

    c = count_slides(deck_html)
    if c != expected_count:
        failures.append(f"Expected {expected_count} slides, got {c}")

    dupes = validate_uniqueness(deck_html)
    if dupes:
        failures.append(f"Duplicate slide numbers: {dupes}")

    gaps = validate_continuity(deck_html)
    if gaps:
        failures.append(f"Gaps in numbering: {gaps}")

    if check_data_id:
        did_dupes = validate_data_id_uniqueness(deck_html)
        if did_dupes:
            failures.append(f"Duplicate data-slide-id: {did_dupes}")

    if not validate_no_markers(deck_html):
        failures.append("Temporary markers (__OLD_) remain in output")

    nums = extract_slide_numbers(deck_html)
    counters = get_counters(deck_html)
    for i, (cur, tot) in enumerate(counters):
        if i < len(nums):
            if cur != nums[i]:
                failures.append(
                    f"Counter mismatch at slide {i+1}: shows {cur}, expected {nums[i]}"
                )
            if tot != expected_count:
                failures.append(
                    f"Counter total at slide {i+1}: shows {tot}, expected {expected_count}"
                )

    return failures


# ---------------------------------------------------------------------------
# Structural operations
# ---------------------------------------------------------------------------

def resequence(deck_html: str) -> str:
    """Renumber all slides sequentially from 1."""
    slides = parse_slides(deck_html)
    total = len(slides)

    # First pass: replace all slide-NN with unique temporary markers
    for i, s in enumerate(slides):
        old = s['full_html']
        old_class_num = f"slide-{s['comment_num']:02d}"
        old_comment = f"SLIDE {s['comment_num']:02d}"
        old_counter_cur = f"{s['comment_num']:02d} /"
        new_num_str = f"TMP_{i:04d}"

        new_html = old
        new_html = new_html.replace(old_class_num, f"slide-{new_num_str}", 1)
        new_html = new_html.replace(old_comment, f"SLIDE {new_num_str}", 1)
        new_html = new_html.replace(old_counter_cur, f"{new_num_str} /", 1)
        new_html = new_html.replace(
            f'data-slide-id="slide-{s["comment_num"]:02d}"',
            f'data-slide-id="slide-{new_num_str}"',
        )

        deck_html = deck_html.replace(old, new_html, 1)

    # Second pass: replace markers with sequential numbers
    for i in range(1, total + 1):
        new_num_str = f"TMP_{i-1:04d}"
        target = f"{i:02d}"

        deck_html = deck_html.replace(f"slide-{new_num_str}", f"slide-{target}")
        deck_html = deck_html.replace(f"SLIDE {new_num_str}", f"SLIDE {target}")
        deck_html = deck_html.replace(f"{new_num_str} /", f"{target} /")
        deck_html = deck_html.replace(
            f'data-slide-id="slide-{new_num_str}"',
            f'data-slide-id="slide-{target}"',
        )

    # Update all counter totals to match actual slide count
    deck_html = re.sub(
        r'(\d+)\s*/\s*\d+',
        lambda m: f"{m.group(1)} / {total:02d}",
        deck_html,
    )

    return deck_html


def insert_slide(deck_html: str, position: int, new_slide_html: str) -> str:
    """Insert a new slide at 1-based position, then resequence."""
    slides = parse_slides(deck_html)
    total = len(slides)

    if position < 1 or position > total + 1:
        raise ValueError(f"Position {position} out of range [1, {total + 1}]")

    if position == total + 1:
        # Append at end
        idx = deck_html.rfind('</section>')
        if idx < 0:
            raise ValueError("No </section> found")
        deck_html = (
            deck_html[:idx + len('</section>')] + '\n' +
            new_slide_html +
            deck_html[idx + len('</section>'):]
        )
    else:
        target = slides[position - 1]['full_html']
        idx = deck_html.find(target)
        if idx < 0:
            raise ValueError(f"Could not find slide at position {position}")
        deck_html = deck_html[:idx] + new_slide_html + '\n' + deck_html[idx:]

    return resequence(deck_html)


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

    # Remove from current position
    deck_html = deck_html[:idx] + deck_html[idx + len(moving):]

    # Re-insert at new position
    new_slides = parse_slides(deck_html)
    if to_pos == 1:
        body_end = deck_html.find('<body>') + len('<body>\n')
        deck_html = deck_html[:body_end] + moving + '\n' + deck_html[body_end:]
    elif to_pos > len(new_slides):
        idx = deck_html.rfind('</section>')
        deck_html = (
            deck_html[:idx + len('</section>')] + '\n' +
            moving +
            deck_html[idx + len('</section>'):]
        )
    else:
        target = new_slides[to_pos - 1]['full_html']
        idx = deck_html.find(target)
        deck_html = deck_html[:idx] + moving + '\n' + deck_html[idx:]

    return resequence(deck_html)


def batch_renumber(deck_html: str, mapping: Dict[int, int]) -> str:
    """
    Collision-safe batch renumbering using two-pass tokens.

    mapping: {old: new, old: new, ...}
    After renumbering, resequences all slides to be 1..N.
    """
    all_slides = parse_slides(deck_html)
    total = len(all_slides)

    # First pass: replace ALL slide-NN with unique temporary markers
    for i, s in enumerate(all_slides):
        old = s['full_html']
        old_num = s['comment_num']
        old_num_str = f"{old_num:02d}"
        new_marker = f"TMP_{i:04d}"

        new_html = old
        new_html = new_html.replace(f"slide-{old_num_str}", f"slide-{new_marker}", 1)
        new_html = new_html.replace(f"SLIDE {old_num_str}", f"SLIDE {new_marker}", 1)
        new_html = new_html.replace(f"{old_num_str} /", f"{new_marker} /", 1)
        new_html = new_html.replace(
            f'data-slide-id="slide-{old_num_str}"',
            f'data-slide-id="slide-{new_marker}"',
        )
        deck_html = deck_html.replace(old, new_html, 1)

    # Second pass: apply mapping
    for old_n, new_n in mapping.items():
        # Find which marker corresponds to old_n
        for i, s in enumerate(all_slides):
            if s['comment_num'] == old_n:
                marker = f"TMP_{i:04d}"
                new_str = f"{new_n:02d}"
                deck_html = deck_html.replace(f"slide-{marker}", f"slide-MAP_{new_str}", 1)
                deck_html = deck_html.replace(f"SLIDE {marker}", f"SLIDE MAP_{new_str}", 1)
                deck_html = deck_html.replace(f"{marker} /", f"MAP_{new_str} /", 1)
                deck_html = deck_html.replace(
                    f'data-slide-id="slide-{marker}"',
                    f'data-slide-id="slide-MAP_{new_str}"',
                )
                break

    # Third pass: resequence everything to be 1..N
    # Find all remaining TMP_ markers (unmapped slides) and MAP_ markers
    slide_pattern = re.compile(r'slide-(TMP_\d{4}|MAP_\d{2})')
    markers = slide_pattern.findall(deck_html)
    unique_markers = []
    seen = set()
    for m in markers:
        if m not in seen:
            unique_markers.append(m)
            seen.add(m)

    for i, marker in enumerate(unique_markers):
        target = f"{i + 1:02d}"
        deck_html = deck_html.replace(f"slide-{marker}", f"slide-{target}")
        deck_html = deck_html.replace(f"SLIDE {marker}", f"SLIDE {target}")
        deck_html = deck_html.replace(f"{marker} /", f"{target} /")
        deck_html = deck_html.replace(
            f'data-slide-id="slide-{marker}"',
            f'data-slide-id="slide-{target}"',
        )

    # Clean up any remaining MAP_ in data-slide-id or elsewhere
    deck_html = re.sub(r'MAP_\d{2}', '', deck_html)

    # Update counter totals
    deck_html = re.sub(
        r'(\d+)\s*/\s*\d+',
        lambda m: f"{m.group(1)} / {total:02d}",
        deck_html,
    )

    return deck_html
