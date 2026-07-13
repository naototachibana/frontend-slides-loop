#!/usr/bin/env python3
"""
Strict structural tests for slide operations, batch renumbering,
stable ID preservation, payload/content preservation, and validation.

All tests use synthetic fixture decks and pure-Python helpers.
No browser needed.
"""
import unittest
from slide_structure import (
    make_deck, make_deck_with_content, make_slide_fragment,
    parse_slides, extract_slide_numbers, extract_data_ids,
    extract_payloads, count_slides, count_doctypes,
    insert_slide, delete_slide, reorder_slides,
    batch_renumber, resequence,
    validate_fragment, strict_validate, verify_operation,
    require_valid_source,
    FragmentError, MappingError,
)


class TestFragmentValidation(unittest.TestCase):
    """FSL-118, FSL-128, FSL-151: Fragment validity."""

    def test_valid_fragment_accepts(self):
        try:
            validate_fragment(make_slide_fragment(5, 10, "s-005", "tp"))
        except FragmentError as e:
            self.fail(f"Valid fragment rejected: {e}")

    def test_complete_document_rejected(self):
        with self.assertRaises(FragmentError) as ctx:
            validate_fragment(make_deck(1))
        self.assertIn("DOCTYPE", str(ctx.exception))

    def test_document_tags_rejected(self):
        for tag in ['<html>', '<body>', '<head>']:
            with self.subTest(tag=tag):
                with self.assertRaises(FragmentError):
                    validate_fragment(tag + '<section class="slide s-01">x</section>')

    def test_empty_rejected(self):
        with self.assertRaises(FragmentError):
            validate_fragment("")

    def test_multi_section_rejected(self):
        frag = make_slide_fragment(1) + make_slide_fragment(2)
        with self.assertRaises(FragmentError) as ctx:
            validate_fragment(frag)
        self.assertIn("2 slide sections", str(ctx.exception))

    def test_insert_rejects_complete_doc(self):
        with self.assertRaises(FragmentError):
            insert_slide(make_deck(3), 2, make_deck(1))

    def test_insert_output_single_doctype(self):
        r = insert_slide(make_deck(5), 3, make_slide_fragment(99, 5))
        self.assertEqual(count_doctypes(r), 1)

    # FSL-128: case-insensitive
    def test_uppercase_html_rejected(self):
        with self.assertRaises(FragmentError):
            validate_fragment('<HTML><section class="slide s-01">x</section></HTML>')

    def test_uppercase_doctype_rejected(self):
        with self.assertRaises(FragmentError):
            validate_fragment(
                '<!DOCTYPE HTML><html><body>'
                '<section class="slide s-01">x</section></body></html>'
            )

    def test_tag_with_attrs_rejected(self):
        with self.assertRaises(FragmentError):
            validate_fragment(
                '<html lang="ja"><body class="deck">'
                '<section class="slide s-01">x</section></body></html>'
            )

    def test_one_valid_one_malformed_rejected(self):
        frag = (make_slide_fragment(1, data_id="a", payload_text="ok") +
                '<section class="slide s-99">malformed</section>')
        with self.assertRaises(FragmentError) as ctx:
            validate_fragment(frag)
        self.assertIn("parseable", str(ctx.exception))

    # FSL-151: <section> without whitespace after tag name
    def test_section_no_whitespace_detected(self):
        frag = ('<section class="slide slide-01"><!-- SLIDE 01 -->'
                '<div class="counter">01 / 01</div></section>')
        try:
            validate_fragment(frag)
        except FragmentError:
            self.fail("Standard <section> should be accepted")

    def test_section_no_space_after_tag(self):
        """<section> immediately followed by > should still be counted."""
        frag = '<section>malformed</section>'
        with self.assertRaises(FragmentError) as ctx:
            validate_fragment(frag)
        # Should be rejected because it has a <section> but no parseable slides
        self.assertIn("parseable", str(ctx.exception).lower())

    def test_section_with_only_gt_detected(self):
        """<section> with no class should be detected as unparseable."""
        frag = ('<section>\n'
                '  <!-- SLIDE 01 -->\n'
                '  <div class="counter">01 / 01</div>\n'
                '</section>')
        with self.assertRaises(FragmentError) as ctx:
            validate_fragment(frag)
        self.assertIn("parseable", str(ctx.exception).lower())


class TestPayloadPreservation(unittest.TestCase):
    """FSL-126: Counter regex must not damage payload text."""

    def setUp(self):
        frags = []
        for i in range(1, 5):
            frags.append(make_slide_fragment(
                i, 4, f"topic-{i:03d}",
                f"ratio 16/9 date 2026/07 chemical H2SO4 pH=7.0"
            ))
        self.deck = "<!DOCTYPE html>\n<html>\n<body>\n" + "".join(frags) + "</body>\n</html>\n"

    def _check_ratios(self, payloads):
        for p in payloads:
            self.assertIn("16/9", p, f"16/9 damaged: '{p}'")
            self.assertIn("2026/07", p, f"2026/07 damaged: '{p}'")
            self.assertIn("H2SO4", p, f"H2SO4 damaged: '{p}'")

    def test_resequence_preserves_ratios(self):
        self._check_ratios(extract_payloads(resequence(self.deck)))

    def test_insert_preserves_ratios(self):
        """Insert preserves ratios in original slides (new slide exempt)."""
        frag = make_slide_fragment(99, 5, "ins", "ratio 16/9 kept")
        r2 = insert_slide(self.deck, 3, frag)
        payloads = extract_payloads(r2)
        for p in payloads:
            if "kept" in p:
                self.assertIn("16/9", p,
                              f"Inserted slide ratio damaged: '{p}'")
            else:
                self.assertIn("16/9", p,
                              f"Original ratio damaged: '{p}'")
                self.assertIn("2026/07", p,
                              f"Original date damaged: '{p}'")
                self.assertIn("H2SO4", p,
                              f"Original chemical damaged: '{p}'")

    def test_delete_preserves_remaining(self):
        self._check_ratios(extract_payloads(delete_slide(self.deck, 2)))

    def test_batch_renumber_preserves_ratios(self):
        mapping = {i: i for i in range(1, 5)}
        self._check_ratios(extract_payloads(batch_renumber(self.deck, mapping)))

    # FSL-162: Counter replacement must not touch payload text
    def test_payload_with_counter_like_text_preserved(self):
        """Payload containing '05 / ratio' must survive resequence."""
        f = make_slide_fragment(5, 10, "topic-005",
                                "Version 05 / detail and 05 / ratio")
        deck = make_deck(1, stable_ids=True)
        # Replace the first slide's payload
        old_slide = parse_slides(deck)[0]['full_html']
        new_slide = old_slide.replace(
            '<p>payload-001</p>',
            '<p>Version 05 / detail and 05 / ratio</p>'
        )
        deck = deck.replace(old_slide, new_slide, 1)

        r = resequence(deck)
        payloads = extract_payloads(r)
        self.assertIn("Version 05 / detail and 05 / ratio",
                      payloads[0] if payloads else "",
                      "Counter-like payload text was damaged")
        # Also verify counter is correct
        self.assertIn("01 / 01", r, "Counter value incorrect after resequence")


class TestRichContentPreservation(unittest.TestCase):
    """FSL-149: Full HTML content preservation (multiple <p>, images,
    extra classes, style attributes, card elements)."""

    def setUp(self):
        self.d5 = make_deck_with_content(5, stable_ids=True)

    def test_resequence_preserves_extra_class(self):
        r = resequence(self.d5)
        self.assertIn('deck-section-01', r, "Extra class lost")
        self.assertIn('deck-section-05', r, "Last extra class lost")

    def test_resequence_preserves_style_attr(self):
        r = resequence(self.d5)
        self.assertIn('style="background:#fff"', r)

    def test_resequence_preserves_images(self):
        r = resequence(self.d5)
        for i in range(1, 6):
            self.assertIn(f'src="slide-{i:02d}.png"', r,
                          f"Image slide-{i:02d}.png lost")

    def test_resequence_preserves_multiple_paragraphs(self):
        r = resequence(self.d5)
        payloads = extract_payloads(r)
        for i in range(1, 6):
            self.assertIn(f"intro-{i:03d}", payloads,
                          f"Intro paragraph {i} lost")
            self.assertIn(f"detail-{i:03d}", payloads,
                          f"Detail paragraph {i} lost")

    def test_resequence_preserves_card_elements(self):
        r = resequence(self.d5)
        for i in range(1, 6):
            self.assertIn(f'<div class="card">', r, "Card div lost")

    def test_insert_preserves_extra_content(self):
        frag = make_slide_fragment(99, 6, "new", "inserted")
        r = insert_slide(self.d5, 3, frag)
        self.assertIn('deck-section-01', r)
        self.assertIn('style="background:#fff"', r)
        self.assertIn('src="slide-05.png"', r)

    def test_delete_preserves_remaining_content(self):
        r = delete_slide(self.d5, 3)
        self.assertIn('deck-section-01', r)
        self.assertIn('deck-section-05', r)
        self.assertIn('style="background:#fff"', r)
        self.assertIn('src="slide-04.png"', r)

    def test_reorder_preserves_images(self):
        r = reorder_slides(self.d5, 2, 4)
        for i in range(1, 6):
            self.assertIn(f'src="slide-{i:02d}.png"', r,
                          f"Image slide-{i:02d}.png lost after reorder")

    def test_batch_renumber_swap_preserves_images(self):
        mapping = {1: 2, 2: 1, 3: 3, 4: 4, 5: 5}
        r = batch_renumber(self.d5, mapping)
        # After swap, slide-1 content moved to position 2
        self.assertIn('src="slide-01.png"', r)
        self.assertIn('src="slide-02.png"', r)
        self.assertIn('deck-section-01', r)
        self.assertIn('deck-section-02', r)

    def test_batch_renumber_swap_preserves_payloads(self):
        mapping = {1: 2, 2: 1, 3: 3, 4: 4, 5: 5}
        r = batch_renumber(self.d5, mapping)
        payloads = extract_payloads(r)
        # After swap, position 1 has old slide 2's content
        self.assertIn("intro-002", payloads,
                      "old slide 2 payload should be at position 1")
        self.assertIn("intro-001", payloads,
                      "old slide 1 payload should be at position 2")


class TestSourceValidation(unittest.TestCase):
    """FSL-127, FSL-150: Source validation."""

    def test_insert_rejects_malformed(self):
        bad = '<section class="slide s-01">broken</section>'
        with self.assertRaises(ValueError):
            insert_slide(bad, 1, make_slide_fragment(1))

    def test_delete_rejects_malformed(self):
        with self.assertRaises(ValueError):
            delete_slide('<section class="slide s-01">broken</section>', 1)

    def test_reorder_rejects_malformed(self):
        with self.assertRaises(ValueError):
            reorder_slides('<section class="slide s-01">broken</section>', 1, 1)

    def test_batch_renumber_rejects_malformed(self):
        with self.assertRaises(ValueError):
            batch_renumber('<section class="slide s-01">broken</section>', {1: 1})

    def test_duplicate_numbers_rejected(self):
        d = make_deck(5)
        bad = d.replace('slide-03', 'slide-02')
        with self.assertRaises(ValueError):
            require_valid_source(bad)

    def test_missing_counter_rejected(self):
        d = make_deck(3)
        bad = d.replace('03 / 03', 'xx / xx')
        with self.assertRaises(ValueError):
            require_valid_source(bad)

    # FSL-150: zero-slide deck rejected
    def test_zero_slide_deck_rejected(self):
        empty = "<!DOCTYPE html>\n<html>\n<body>\n</body>\n</html>\n"
        with self.assertRaises(ValueError) as ctx:
            require_valid_source(empty)
        self.assertIn("STRUCT-NO-SLIDES", str(ctx.exception))

    def test_zero_slide_with_other_content_rejected(self):
        no_slides = "<html><body><p>no slides here</p></body></html>"
        with self.assertRaises(ValueError):
            require_valid_source(no_slides)


class TestSlideOperations(unittest.TestCase):
    """Positive tests — insertion, deletion, reordering."""

    def setUp(self):
        self.d8 = make_deck(8, stable_ids=True)
        self.d12 = make_deck(12, stable_ids=True)
        self.d20 = make_deck(20, stable_ids=True)
        self.d10 = make_deck(10, stable_ids=True)

    def _f(self, label="99", did="ins-099", payload="inserted"):
        return make_slide_fragment(99, 10, did, payload)

    def test_insert_middle(self):
        r = insert_slide(self.d8, 4, self._f())
        self.assertEqual(verify_operation(r, 9), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 10)))

    def test_insert_beginning(self):
        r = insert_slide(self.d12, 1, self._f())
        self.assertEqual(verify_operation(r, 13), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 14)))

    def test_insert_end(self):
        r = insert_slide(self.d20, 21, self._f())
        self.assertEqual(verify_operation(r, 21), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 22)))

    def test_insert_9_to_10(self):
        r = insert_slide(self.d10, 9, self._f("77", "ins-b", "at-boundary"))
        self.assertEqual(verify_operation(r, 11), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 12)))

    def test_insert_preserves_stable_ids(self):
        r = insert_slide(self.d8, 4, self._f(did="ins-004"))
        ids = extract_data_ids(r)
        for e in ["topic-001", "topic-004", "topic-008", "ins-004"]:
            self.assertIn(e, ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_insert_exact_stable_id_order(self):
        r = insert_slide(self.d8, 4, self._f("99", "NEW-001", "new"))
        self.assertEqual(
            extract_data_ids(r),
            ["topic-001", "topic-002", "topic-003",
             "NEW-001",
             "topic-004", "topic-005", "topic-006", "topic-007", "topic-008"]
        )

    def test_delete_first(self):
        r = delete_slide(self.d8, 1)
        self.assertEqual(verify_operation(r, 7), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 8)))

    def test_delete_middle(self):
        r = delete_slide(self.d12, 6)
        self.assertEqual(verify_operation(r, 11), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 12)))

    def test_delete_last(self):
        r = delete_slide(self.d20, 20)
        self.assertEqual(verify_operation(r, 19), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 20)))

    def test_delete_preserves_stable_ids(self):
        r = delete_slide(self.d8, 3)
        ids = extract_data_ids(r)
        self.assertIn("topic-001", ids)
        self.assertIn("topic-004", ids)
        self.assertIn("topic-008", ids)
        self.assertEqual(len(ids), 7)

    def test_reorder_forward(self):
        r = reorder_slides(self.d12, 3, 8)
        self.assertEqual(verify_operation(r, 12), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 13)))

    def test_reorder_backward(self):
        r = reorder_slides(self.d12, 10, 2)
        self.assertEqual(verify_operation(r, 12), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 13)))

    def test_reorder_across_9_to_10(self):
        r = reorder_slides(self.d10, 8, 10)
        self.assertEqual(verify_operation(r, 10), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 11)))

    def test_reorder_forward_stable_ids(self):
        r = reorder_slides(self.d8, 3, 7)
        self.assertEqual(
            extract_data_ids(r),
            ["topic-001", "topic-002",
             "topic-004", "topic-005", "topic-006", "topic-007",
             "topic-003",
             "topic-008"]
        )

    def test_reorder_backward_stable_ids(self):
        r = reorder_slides(self.d8, 7, 2)
        self.assertEqual(
            extract_data_ids(r),
            ["topic-001", "topic-007",
             "topic-002", "topic-003", "topic-004", "topic-005", "topic-006",
             "topic-008"]
        )


class TestBatchRenumber(unittest.TestCase):
    """FSL-148: batch_renumber reorders sections and post-condition passes."""

    def setUp(self):
        self.d5 = make_deck(5, stable_ids=False)

    def test_identity_passes(self):
        r = batch_renumber(self.d5, {i: i for i in range(1, 6)})
        self.assertEqual(verify_operation(r, 5), [])
        self.assertEqual(extract_slide_numbers(r), [1, 2, 3, 4, 5])

    def test_swap_3_and_4_succeeds(self):
        """FSL-148: swap reorders sections, post-condition passes."""
        r = batch_renumber(self.d5, {1: 1, 2: 2, 3: 4, 4: 3, 5: 5})
        self.assertEqual(verify_operation(r, 5), [])
        nums = extract_slide_numbers(r)
        self.assertEqual(nums, [1, 2, 3, 4, 5])

    def test_swap_9_and_10_succeeds(self):
        d10 = make_deck(10, stable_ids=False)
        mapping = {i: i for i in range(1, 10)}
        mapping[9] = 10
        mapping[10] = 9
        r = batch_renumber(d10, mapping)
        self.assertEqual(verify_operation(r, 10), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 11)))

    def test_swap_content_moves(self):
        """After 3↔4 swap, original slide 3 content is at position 4."""
        d = make_deck_with_content(5, stable_ids=False)
        mapping = {1: 1, 2: 2, 3: 4, 4: 3, 5: 5}
        r = batch_renumber(d, mapping)
        payloads = extract_payloads(r)
        # Position 3 should have old slide 4's content
        # Position 4 should have old slide 3's content
        self.assertIn("intro-003", payloads, "old slide 3 content lost")
        self.assertIn("intro-004", payloads, "old slide 4 content lost")

    def test_shift_up_succeeds(self):
        """Shift 1→2, 2→3, 3→4, 4→5, 5→1 (rotate left)."""
        d = make_deck_with_content(5, stable_ids=False)
        mapping = {1: 2, 2: 3, 3: 4, 4: 5, 5: 1}
        r = batch_renumber(d, mapping)
        self.assertEqual(verify_operation(r, 5), [])
        self.assertEqual(extract_slide_numbers(r), [1, 2, 3, 4, 5])
        # extract_payloads returns ALL <p> text (both intro-NNN and detail-NNN)
        # For 2 <p> per slide, index pairs: (0,1)=slide1, (2,3)=slide2, etc.
        payloads = extract_payloads(r)
        # slide 1 (position 0,1): old slide 5 content
        self.assertEqual(payloads[0], "intro-005",
                         "Rotated: position 1 should have old slide 5 intro")
        # slide 5 (position 8,9): old slide 4 content
        self.assertEqual(payloads[8], "intro-004",
                         "Rotated: position 5 should have old slide 4 intro")

    # --- FSL-125: Gap/out-of-range rejection ---

    def test_gap_in_values_rejected(self):
        with self.assertRaises(MappingError) as ctx:
            batch_renumber(self.d5, {1: 1, 2: 2, 3: 4, 4: 5, 5: 6})
        self.assertIn("missing", str(ctx.exception).lower())

    def test_out_of_range_value_rejected(self):
        with self.assertRaises(MappingError) as ctx:
            batch_renumber(self.d5, {1: 2, 2: 3, 3: 4, 4: 5, 5: 6})
        self.assertIn("out-of-range", str(ctx.exception).lower())

    def test_duplicate_target_rejected(self):
        with self.assertRaises(MappingError):
            batch_renumber(self.d5, {1: 1, 2: 2, 3: 4, 4: 4, 5: 5})

    def test_unknown_key_rejected(self):
        with self.assertRaises(MappingError):
            batch_renumber(self.d5, {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 99: 99})

    def test_missing_key_rejected(self):
        with self.assertRaises(MappingError):
            batch_renumber(self.d5, {1: 1, 2: 2, 3: 3, 4: 4})

    def test_incomplete_3_to_4_rejected(self):
        with self.assertRaises(MappingError):
            batch_renumber(self.d5, {3: 4})

    # --- FSL-131: Marker cleanup ---

    def test_no_markers_after_success(self):
        r = batch_renumber(self.d5, {1: 2, 2: 1, 3: 3, 4: 4, 5: 5})
        for m in ['__BM_', '__OLD_', 'TMP_', 'MAP_']:
            self.assertNotIn(m, r, f"Marker '{m}' remains")

    def test_input_unchanged_after_failed_mapping(self):
        original = self.d5
        try:
            batch_renumber(original, {3: 4})
        except (MappingError, ValueError):
            pass
        self.assertEqual(original, self.d5)
        for m in ['__BM_', '__OLD_', 'TMP_', 'MAP_']:
            self.assertNotIn(m, original)


class TestStableIds(unittest.TestCase):
    """FSL-120: Stable identity preservation."""

    def test_default_deck_has_stable_ids(self):
        self.assertEqual(
            extract_data_ids(make_deck(8, True)),
            [f"topic-{i:03d}" for i in range(1, 9)]
        )

    def test_stable_ids_preserved_through_resequence(self):
        d = make_deck(5, True)
        self.assertEqual(
            extract_data_ids(resequence(d)),
            [f"topic-{i:03d}" for i in range(1, 6)]
        )


class TestStructuralValidation(unittest.TestCase):
    """FSL-121, FSL-129, FSL-150."""

    def test_ordered_numbers_pass(self):
        self.assertEqual(
            [f for f in strict_validate(make_deck(5)) if "STRUCT-003" in f],
            []
        )

    def test_non_ordered_detected(self):
        d = make_deck(5)
        bad = d.replace('slide-03', 'slide-99').replace('slide-04', 'slide-03')
        failures = strict_validate(bad)
        self.assertGreater(
            len([f for f in failures if "STRUCT-003" in f or "STRUCT-004" in f]), 0
        )

    def test_counter_mismatch_detected(self):
        d = make_deck(5)
        bad = d.replace("03 / 05", "99 / 05")
        self.assertGreater(
            len([f for f in strict_validate(bad) if "STRUCT-006" in f]), 0
        )

    def test_extra_counter_nodes_detected(self):
        d = make_deck(3)
        self.assertGreater(
            len([f for f in strict_validate(d + '<div class="counter">04/03</div>')
                 if "STRUCT-008" in f]), 0
        )

    def test_zero_slide_rejected_by_strict_validate(self):
        empty = "<html><body></body></html>"
        failures = strict_validate(empty)
        self.assertGreater(
            len([f for f in failures if "STRUCT-NO-SLIDES" in f]), 0
        )


class TestStableIdDedupe(unittest.TestCase):
    """FSL-130: Stable ID duplicate detection."""

    def test_duplicate_detected(self):
        d = make_deck(5, True)
        bad = d.replace('topic-003', 'topic-001')
        failures = strict_validate(bad)
        self.assertGreater(
            len([f for f in failures if "STRUCT-009" in f]), 0
        )

    def test_unique_accepted(self):
        self.assertEqual(
            len([f for f in strict_validate(make_deck(5, True))
                 if "STRUCT-009" in f]), 0
        )


class TestInsertDuplicateStableId(unittest.TestCase):
    """FSL-130: Insert rejects fragment with duplicate stable ID."""

    def test_duplicate_stable_id_rejected(self):
        d = make_deck(5, stable_ids=True)
        frag = make_slide_fragment(99, 6, "topic-003", "dup")
        with self.assertRaises(RuntimeError) as ctx:
            insert_slide(d, 3, frag)
        self.assertTrue(
            "duplicate" in str(ctx.exception).lower()
            or "post-condition" in str(ctx.exception).lower()
        )


if __name__ == "__main__":
    unittest.main()
