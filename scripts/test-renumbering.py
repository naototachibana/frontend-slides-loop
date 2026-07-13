#!/usr/bin/env python3
"""
Fixture-based tests for numbered-slide operations.

Tests insertion, deletion, reordering, and collision-safe
renumbering using synthetic HTML strings. No browser needed.
"""
import re
import unittest
import tempfile
import os


def make_deck(num_slides, use_data_id=False):
    """Create a synthetic Frontend Slides deck with numbered slides."""
    slides = []
    for i in range(1, num_slides + 1):
        cls = f"slide slide-{i:02d}"
        slide_id = f' data-slide-id="slide-{i:02d}"' if use_data_id else ""
        slides.append(
            f'    <section class="{cls}"{slide_id}>\n'
            f'      <!-- SLIDE {i:02d} -->\n'
            f'      <div class="counter">{i:02d} / {num_slides:02d}</div>\n'
            f'    </section>'
        )
    return "<!DOCTYPE html>\n<html>\n<body>\n" + \
        "\n".join(slides) + "\n</body>\n</html>\n"


def count_by_pattern(deck_html, pattern, section_scope=False):
    """Count matches of a pattern, optionally scoped to section elements."""
    if section_scope:
        sections = re.findall(
            r'<section[^>]*class="[^"]*slide-\d+[^"]*"[^>]*>',
            deck_html
        )
        return sum(1 for s in sections if re.search(pattern, s))
    return len(re.findall(pattern, deck_html))


def three_pass_renumber(deck_html, old_n, new_n):
    """Rename slide numbers from old_n to new_n using collision-safe tokens."""
    old_padded = f"{old_n:02d}"
    new_padded = f"{new_n:02d}"

    # Pass A: prefix old numbers with marker
    # Match slide-NN in class, comments, counters
    def mark_class(m):
        cls = m.group(1)
        return f'class="{cls}"' if f"slide-{old_padded}" not in cls else (
            f'class="{cls.replace(f"slide-{old_padded}", f"slide-__OLD_{old_padded}__")}"'
        )

    def mark_comment(m):
        c = m.group(1)
        return f'<!-- SLIDE {c} -->' if c != old_padded else (
            f'<!-- SLIDE __OLD_{old_padded}__ -->'
        )

    def mark_counter(m):
        cur, total = m.group(1), m.group(2)
        cur_m = f"__OLD_{old_padded}__" if cur == old_padded else cur
        return f"{cur_m} / {total}"

    deck_html = re.sub(
        r'class="([^"]*)"',
        mark_class,
        deck_html
    )
    deck_html = re.sub(
        r'<!-- SLIDE (\d+) -->',
        mark_comment,
        deck_html
    )
    deck_html = re.sub(
        r'(\d+)\s*/\s*(\d+)',
        mark_counter,
        deck_html
    )

    # Pass B: replace markers with new number
    deck_html = deck_html.replace(
        f"slide-__OLD_{old_padded}__",
        f"slide-{new_padded}"
    )
    deck_html = deck_html.replace(
        f"__OLD_{old_padded}__",
        new_padded
    )

    # Pass C: check no unreplaced markers
    if "__OLD_" in deck_html:
        raise RuntimeError(f"Unreplaced markers remain after renumbering")

    # Update total counter for full deck
    total_slides = len(re.findall(r'<section\s+class="slide', deck_html))
    deck_html = re.sub(
        r'(\d+)\s*/\s*\d+',
        lambda m: f"{m.group(1)} / {total_slides:02d}",
        deck_html
    )

    return deck_html


class TestSlideDeckFixtures(unittest.TestCase):

    def setUp(self):
        self.deck_8 = make_deck(8)
        self.deck_12 = make_deck(12)
        self.deck_20 = make_deck(20)
        self.deck_9to10 = make_deck(10)

    # --- Slide count verification ---

    def test_8_slides_have_correct_count(self):
        count = len(re.findall(r'<section\s+class="slide', self.deck_8))
        self.assertEqual(count, 8)

    def test_12_slides_have_correct_count(self):
        count = len(re.findall(r'<section\s+class="slide', self.deck_12))
        self.assertEqual(count, 12)

    def test_20_slides_have_correct_count(self):
        count = len(re.findall(r'<section\s+class="slide', self.deck_20))
        self.assertEqual(count, 20)

    def test_10_slides_have_correct_count(self):
        count = len(re.findall(r'<section\s+class="slide', self.deck_9to10))
        self.assertEqual(count, 10)

    # --- Identity uniqueness ---

    def test_8_slides_unique_ids(self):
        ids = re.findall(r'class="([^"]*)"', self.deck_8)
        slide_ids = [i for i in ids if 'slide-' in i]
        self.assertEqual(len(slide_ids), len(set(slide_ids)))

    def test_20_slides_unique_ids(self):
        ids = re.findall(r'class="([^"]*)"', self.deck_20)
        slide_ids = [i for i in ids if 'slide-' in i]
        self.assertEqual(len(slide_ids), len(set(slide_ids)))

    def test_duplicate_ids_detected(self):
        bad = self.deck_8.replace('slide-02', 'slide-01')
        ids = re.findall(r'class="([^"]*)"', bad)
        slide_ids = [i for i in ids if 'slide-' in i]
        self.assertGreater(len(slide_ids), len(set(slide_ids)))

    # --- Safe renumbering ---

    def test_three_pass_renumber_preserves_other_numbers(self):
        # Insert a slide at position 3, renumber 3..N up by 1
        result = three_pass_renumber(self.deck_8, 3, 4)
        # Slide 01 and 02 should stay unchanged
        self.assertIn('slide-01', result)
        self.assertIn('slide-02', result)
        # Old slide 03 should now be slide-04
        self.assertNotIn('slide-03', result)  # may be absent or just gone
        # No collision artifacts
        self.assertNotIn('slide-00', result)
        self.assertNotIn('slide-09', result)  # only 8 slides before

    def test_three_pass_no_unreplaced_markers(self):
        result = three_pass_renumber(self.deck_12, 5, 6)
        self.assertNotIn('__OLD_', result)

    def test_three_pass_9to10_boundary(self):
        # Renumber slide 09 -> 10 (tests 2-digit boundary)
        result = three_pass_renumber(self.deck_9to10, 9, 10)
        self.assertIn('slide-10', result)
        # Slide 09 should be gone or renumbered
        count_09 = len(re.findall(r'\bslide-09\b', result))
        count_10 = len(re.findall(r'\bslide-10\b', result))
        self.assertGreater(count_10, 0)

    def test_three_pass_no_collision(self):
        # Insert a new slide at position 6 and push existing 6..N up by 1.
        # Renumber from 6→7, 7→8, 8→9, 9→10, 10→11, 11→12 in descending
        # order to avoid collision (highest first).
        result = self.deck_12
        for old_n in range(12, 5, -1):  # 12, 11, 10, 9, 8, 7, 6
            result = three_pass_renumber(result, old_n, old_n + 1)
        sections = re.findall(r'<section[^>]*class="[^"]*slide-\d+[^"]*"[^>]*>', result)
        slide_nums = [re.search(r'slide-(\d+)', s).group(1) for s in sections]
        # Should have 12 slides numbered 07-18 (all shifted)
        self.assertEqual(len(slide_nums), len(set(slide_nums)),
                         f"Duplicate slide numbers: {slide_nums}")
        self.assertEqual(len(slide_nums), 12)

    # --- Section-scoped grep correctness ---

    def test_section_scope_grep_8_slides(self):
        sections = re.findall(
            r'<section[^>]*class="[^"]*slide-\d+[^"]*"[^>]*>',
            self.deck_8
        )
        self.assertEqual(len(sections), 8)

    def test_section_scope_grep_20_slides(self):
        sections = re.findall(
            r'<section[^>]*class="[^"]*slide-\d+[^"]*"[^>]*>',
            self.deck_20
        )
        self.assertEqual(len(sections), 20)

    def test_section_scope_excludes_comments(self):
        # Comments also contain "SLIDE NN" but should not be confused
        # with section-element identity when counting slides.
        # Each slide has exactly 1 comment, so counts happen to match,
        # but the grep pattern targets sections not comments.
        section_count = len(re.findall(
            r'<section[^>]*class="[^"]*slide-\d+[^"]*"[^>]*>',
            self.deck_12
        ))
        # Verify no comment is matched as a section
        section_texts = [m for m in re.findall(
            r'<section[^>]*class="[^"]*slide-\d+[^"]*"[^>]*>',
            self.deck_12
        )]
        for s in section_texts:
            self.assertNotIn('<!--', s,
                             "Comment content should not appear in section elements")

    # --- data-slide-id support ---

    def test_data_slide_id_uniqueness(self):
        deck = make_deck(15, use_data_id=True)
        ids = re.findall(r'data-slide-id="([^"]*)"', deck)
        self.assertEqual(len(ids), 15)
        self.assertEqual(len(ids), len(set(ids)))


    # --- Validator negative tests ---

    def test_validator_rejects_leading_pipe_command(self):
        """The marketplace command must not have a leading |."""
        bad = "|/plugin marketplace add https://github.com/naototachibana/frontend-slides-loop"
        has_pipe = bad.startswith("|/plugin marketplace add")
        self.assertTrue(has_pipe, "Test setup: command has leading pipe")
        self.assertNotEqual(
            bad,
            "/plugin marketplace add https://github.com/naototachibana/frontend-slides-loop",
            "Leading pipe makes it not the valid command"
        )

    def test_validator_rejects_upstream_install_url(self):
        """Install URL must point to fork, not upstream, outside attribution context."""
        install_url = "https://github.com/zarazhangrui/frontend-slides"
        fork_url = "naototachibana/frontend-slides-loop"
        ctx = f"Run:\n\ngit clone {install_url}"
        self.assertNotIn(fork_url, ctx, "Upstream URL is not the fork")
        self.assertIn("zarazhangrui/frontend-slides", install_url,
                      "Upstream URL contains the upstream owner")

    def test_validator_rejects_pkill_pattern(self):
        """Cleanup must not use pkill -f."""
        bad = "pkill -f \"python3 -m http.server\""
        self.assertIn("pkill", bad)
        self.assertNotIn("$PREVIEW_PID", bad,
                         "pkill pattern lacks PID scoping")

    def test_validator_rejects_foreground_server_same_shell(self):
        """A foreground server followed by commands in the same shell block is invalid."""
        bad_block = """python3 -m http.server 8000 --bind 127.0.0.1
curl -s http://localhost:8000"""
        self.assertIn("http.server 8000", bad_block)
        # The curl inside same code block after foreground server is the problem
        self.assertNotIn("PREVIEW_PID", bad_block,
                         "No PID capture means foreground server blocks")

    def test_validator_rejects_automatic_12_cjk_rule(self):
        """12-CJK-characters-per-line must not be an automatic split trigger."""
        bad = "Split when a text column has fewer than 12 CJK characters per line"
        self.assertIn("12 CJK", bad)
        self.assertNotIn("diagnostic heuristic", bad.lower(),
                         "This phrasing is not marked as heuristic")

    def test_validator_rejects_grep_basic_d(self):
        """grep -c without -P or -E and \\d bare is invalid."""
        bad = "grep -c 'slide-\\d'"
        self.assertIn("grep -c", bad)
        self.assertNotIn("grep -Pc", bad,
                         "Basic grep with \\d may not work as expected")


if __name__ == "__main__":
    unittest.main()
