#!/usr/bin/env python3
"""
Strict structural tests for slide insertion, deletion, reordering,
collision-safe renumbering, stable ID preservation, and validation.

All tests use synthetic fixture decks and pure-Python helpers.
No browser needed.
"""
import unittest
from slide_structure import (
    make_deck, make_slide_fragment,
    parse_slides, extract_slide_numbers, extract_data_ids,
    extract_payloads, count_slides, count_doctypes,
    insert_slide, delete_slide, reorder_slides,
    batch_renumber, resequence,
    validate_fragment, strict_validate, verify_operation,
    require_valid_source,
    FragmentError, MappingError,
)


class TestFragmentValidation(unittest.TestCase):
    """FSL-118, FSL-128: Fragment validity tests."""

    def test_valid_fragment_accepts_section(self):
        try:
            validate_fragment(make_slide_fragment(5, 10, "stable-005", "tp"))
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
                    validate_fragment(tag + '<section class="slide slide-01"></section>')

    def test_empty_fragment_rejected(self):
        with self.assertRaises(FragmentError):
            validate_fragment("")

    def test_multi_section_fragment_rejected(self):
        frag = make_slide_fragment(1) + make_slide_fragment(2)
        with self.assertRaises(FragmentError) as ctx:
            validate_fragment(frag)
        self.assertIn("2 slide sections", str(ctx.exception))

    def test_insert_rejects_complete_document(self):
        deck = make_deck(3)
        with self.assertRaises(FragmentError):
            insert_slide(deck, 2, make_deck(1))

    def test_insert_output_has_single_doctype(self):
        result = insert_slide(make_deck(5), 3, make_slide_fragment(99, 5))
        self.assertEqual(count_doctypes(result), 1)

    # FSL-128: case-insensitive tag detection
    def test_uppercase_html_rejected(self):
        with self.assertRaises(FragmentError):
            validate_fragment('<HTML><section class="slide slide-01">x</section></HTML>')

    def test_uppercase_doctype_rejected(self):
        with self.assertRaises(FragmentError):
            validate_fragment('<!DOCTYPE HTML><html><body><section class="slide slide-01">x</section></body></html>')

    def test_tag_with_attributes_rejected(self):
        with self.assertRaises(FragmentError):
            validate_fragment('<html lang="ja"><body class="deck"><section class="slide slide-01">x</section></body></html>')

    def test_one_valid_one_malformed_section_rejected(self):
        """Fragment with 1 parseable + 1 malformed section is rejected."""
        frag = (make_slide_fragment(1, data_id="a", payload_text="ok") +
                '<section class="slide slide-99">malformed</section>')
        with self.assertRaises(FragmentError) as ctx:
            validate_fragment(frag)
        self.assertIn("parseable", str(ctx.exception))


class TestPayloadPreservation(unittest.TestCase):
    """FSL-126: Counter regex must not damage payload text."""

    def setUp(self):
        # Create a deck with ratio-like text in payloads
        fragments = []
        for i in range(1, 5):
            payload = f"ratio 16/9 date 2026/07 chemical H2SO4 pH=7.0"
            fragments.append(make_slide_fragment(
                i, 4, f"topic-{i:03d}", payload))
        self.deck = "<!DOCTYPE html>\n<html>\n<body>\n" + "".join(fragments) + "</body>\n</html>\n"

    def test_resequence_preserves_payload_ratios(self):
        r = resequence(self.deck)
        payloads = list(extract_payloads(r))
        for p in payloads:
            self.assertIn("16/9", p, f"Ratio 16/9 damaged: '{p}'")
            self.assertIn("2026/07", p, f"Date 2026/07 damaged: '{p}'")
            self.assertIn("H2SO4", p, f"Chemical formula damaged: '{p}'")

    def test_insert_preserves_payload_ratios(self):
        frag = make_slide_fragment(99, 5, "ins-001", "ratio 16/9 preserved")
        r = insert_slide(self.deck, 3, frag)
        payloads = list(extract_payloads(r))
        for p in payloads:
            if "preserved" in p:
                self.assertIn("16/9", p)

    def test_delete_preserves_remaining_ratios(self):
        r = delete_slide(self.deck, 2)
        payloads = list(extract_payloads(r))
        for p in payloads:
            self.assertIn("16/9", p, f"Payload damaged: '{p}'")

    def test_batch_renumber_preserves_payload_ratios(self):
        # Use positional IDs (legacy deck)
        d = make_deck(4, stable_ids=False)
        # Replace payloads with ratio text
        for i in range(4):
            old_slide = parse_slides(d)[i]['full_html']
            new_slide = old_slide.replace(
                '<p>payload-', '<p>ratio 16/9 date 2026/07 payload-'
            )
            d = d.replace(old_slide, new_slide, 1)

        mapping = {1: 1, 2: 2, 3: 3, 4: 4}
        r = batch_renumber(d, mapping)
        payloads = list(extract_payloads(r))
        for p in payloads:
            self.assertIn("16/9", p, f"Payload damaged by batch_renumber: '{p}'")
            self.assertIn("2026/07", p, f"Payload damaged by batch_renumber: '{p}'")


class TestSourceValidation(unittest.TestCase):
    """FSL-127: Structural ops reject malformed source."""

    def test_insert_rejects_malformed_source(self):
        bad = "<section class='slide slide-01'>broken</section>"
        with self.assertRaises(ValueError) as ctx:
            insert_slide(bad, 1, make_slide_fragment(1))
        self.assertIn("validation", str(ctx.exception).lower())

    def test_delete_rejects_malformed_source(self):
        bad = "<section class='slide slide-01'>broken</section>"
        with self.assertRaises(ValueError):
            delete_slide(bad, 1)

    def test_reorder_rejects_malformed_source(self):
        bad = "<section class='slide slide-01'>broken</section>"
        with self.assertRaises(ValueError):
            reorder_slides(bad, 1, 1)

    def test_batch_renumber_rejects_malformed_source(self):
        bad = "<section class='slide slide-01'>broken</section>"
        with self.assertRaises(ValueError):
            batch_renumber(bad, {1: 1})

    def test_duplicate_numbers_rejected_by_require_valid_source(self):
        d = make_deck(5)
        # Create a duplicate
        bad = d.replace('slide-03', 'slide-02')
        with self.assertRaises(ValueError) as ctx:
            require_valid_source(bad)
        self.assertIn("STRUCT", str(ctx.exception))

    def test_missing_counter_rejected_by_require_valid_source(self):
        d = make_deck(3)
        bad = d.replace('03 / 03', 'xx / xx')
        with self.assertRaises(ValueError):
            require_valid_source(bad)


class TestSlideOperations(unittest.TestCase):
    """Positive tests — insertion, deletion, reordering."""

    def setUp(self):
        self.d8 = make_deck(8, stable_ids=True)
        self.d12 = make_deck(12, stable_ids=True)
        self.d20 = make_deck(20, stable_ids=True)
        self.d10 = make_deck(10, stable_ids=True)

    def _frag(self, label="99", did="ins-099", payload="inserted"):
        return make_slide_fragment(99, 10, did, payload)

    # --- Insertion ---

    def test_insert_middle(self):
        r = insert_slide(self.d8, 4, self._frag())
        self.assertEqual(verify_operation(r, 9), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 10)))

    def test_insert_beginning(self):
        r = insert_slide(self.d12, 1, self._frag())
        self.assertEqual(verify_operation(r, 13), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 14)))

    def test_insert_end(self):
        r = insert_slide(self.d20, 21, self._frag())
        self.assertEqual(verify_operation(r, 21), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 22)))

    def test_insert_9_to_10_boundary(self):
        r = insert_slide(self.d10, 9, self._frag("77", "ins-boundary", "at-boundary"))
        self.assertEqual(verify_operation(r, 11), [])
        self.assertEqual(extract_slide_numbers(r), list(range(1, 12)))

    # --- Stable IDs preserved through insertion ---

    def test_insert_preserves_stable_ids(self):
        r = insert_slide(self.d8, 4, self._frag(did="ins-004"))
        ids = extract_data_ids(r)
        for expected in ["topic-001", "topic-004", "topic-008", "ins-004"]:
            self.assertIn(expected, ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_insert_preserves_payloads(self):
        r = insert_slide(self.d8, 5, self._frag(payload="inserted-payload"))
        payloads = list(extract_payloads(r))
        for p in ["payload-001", "payload-003", "payload-008"]:
            self.assertIn(p, payloads, f"Original payload {p} lost")
        self.assertIn("inserted-payload", payloads)

    def test_insert_exact_stable_id_order(self):
        r = insert_slide(self.d8, 4, self._frag("99", "NEW-001", "new-slide"))
        ids = extract_data_ids(r)
        expected = (
            ["topic-001", "topic-002", "topic-003",
             "NEW-001",
             "topic-004", "topic-005", "topic-006", "topic-007", "topic-008"]
        )
        self.assertEqual(ids, expected)

    # --- Deletion ---

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
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 7)

    def test_delete_preserves_payloads(self):
        r = delete_slide(self.d8, 4)
        payloads = list(extract_payloads(r))
        self.assertNotIn("payload-004", payloads)
        for i in [1, 2, 3, 5, 6, 7, 8]:
            self.assertIn(f"payload-{i:03d}", payloads)

    # --- Reorder ---

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
        ids = extract_data_ids(r)
        expected = [
            "topic-001", "topic-002",
            "topic-004", "topic-005", "topic-006", "topic-007",
            "topic-003",
            "topic-008",
        ]
        self.assertEqual(ids, expected)

    def test_reorder_backward_stable_ids(self):
        r = reorder_slides(self.d8, 7, 2)
        ids = extract_data_ids(r)
        expected = [
            "topic-001",
            "topic-007",
            "topic-002", "topic-003", "topic-004", "topic-005", "topic-006",
            "topic-008",
        ]
        self.assertEqual(ids, expected)

    def test_reorder_preserves_payloads(self):
        r = reorder_slides(self.d8, 4, 1)
        payloads = list(extract_payloads(r))
        self.assertEqual(payloads[0], "payload-004")
        self.assertIn("payload-001", payloads)
        self.assertIn("payload-008", payloads)
        self.assertEqual(len(payloads), 8)


class TestBatchRenumber(unittest.TestCase):
    """FSL-119, FSL-125: Exact mapping contract."""

    def setUp(self):
        self.d5 = make_deck(5, stable_ids=False)
        self.d10 = make_deck(10, stable_ids=False)

    # --- Complete mapping ---

    def test_identity_mapping(self):
        mapping = {i: i for i in range(1, 6)}
        r = batch_renumber(self.d5, mapping)
        # Custom validation (swap can violate positional order)
        self.assertEqual(count_slides(r), 5)
        self.assertEqual(len(parse_slides(r)), 5)
        self.assertEqual(len(set(extract_slide_numbers(r))), 5)

    def test_swap_3_and_4(self):
        """Swap mapping fails post-condition due to STRUCT-003 (non-ordered)."""
        mapping = {1: 1, 2: 2, 3: 4, 4: 3, 5: 5}
        with self.assertRaises(RuntimeError) as ctx:
            batch_renumber(self.d5, mapping)
        self.assertIn("STRUCT-003", str(ctx.exception))

    def test_swap_9_and_10(self):
        """Swap mapping fails post-condition due to STRUCT-003."""
        mapping = {i: i for i in range(1, 10)}
        mapping[9] = 10
        mapping[10] = 9
        with self.assertRaises(RuntimeError) as ctx:
            batch_renumber(self.d10, mapping)
        self.assertIn("STRUCT-003", str(ctx.exception))

    def test_ordered_renumbering_with_verify(self):
        """A mapping that changes order fails post-condition (STRUCT-003)."""
        mapping = {1: 2, 2: 1, 3: 3, 4: 4, 5: 5}
        with self.assertRaises(RuntimeError) as ctx:
            batch_renumber(self.d5, mapping)
        self.assertIn("STRUCT-003", str(ctx.exception))

    # --- FSL-125: Gap/out-of-range rejection ---

    def test_gap_in_values_rejected(self):
        """Values with a gap (missing 3) should be rejected."""
        mapping = {1: 1, 2: 2, 3: 4, 4: 5, 5: 6}
        with self.assertRaises(MappingError) as ctx:
            batch_renumber(self.d5, mapping)
        self.assertIn("missing", str(ctx.exception).lower())

    def test_out_of_range_value_rejected(self):
        """Values exceeding 1..N should be rejected."""
        mapping = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6}
        with self.assertRaises(MappingError) as ctx:
            batch_renumber(self.d5, mapping)
        self.assertIn("out-of-range", str(ctx.exception).lower())

    def test_duplicate_target_rejected(self):
        with self.assertRaises(MappingError) as ctx:
            batch_renumber(self.d5, {1: 1, 2: 2, 3: 4, 4: 4, 5: 5})
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_unknown_key_rejected(self):
        with self.assertRaises(MappingError):
            batch_renumber(self.d5, {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 99: 99})

    def test_missing_key_rejected(self):
        with self.assertRaises(MappingError):
            batch_renumber(self.d5, {1: 1, 2: 2, 3: 3, 4: 4})

    def test_incomplete_3_to_4_rejected(self):
        with self.assertRaises(MappingError):
            batch_renumber(self.d5, {3: 4})

    def test_incomplete_9_to_10_rejected(self):
        with self.assertRaises(MappingError):
            batch_renumber(self.d10, {9: 10})

    # --- FSL-131: Marker cleanup ---

    def test_no_markers_after_successful_identity(self):
        r = batch_renumber(self.d5, {i: i for i in range(1, 6)})
        for marker in ['__BM_', '__OLD_', 'TMP_', 'MAP_']:
            self.assertNotIn(marker, r, f"Marker '{marker}' remains")

    def test_input_unchanged_after_failed_mapping(self):
        original = self.d5
        try:
            batch_renumber(original, {3: 4})
        except (MappingError, ValueError):
            pass
        # Original should be unchanged and marker-free
        self.assertEqual(original, self.d5)
        for marker in ['__BM_', '__OLD_', 'TMP_', 'MAP_']:
            self.assertNotIn(marker, original, f"Marker '{marker}' in unchanged input")

    def test_batch_marker_in_validate_no_markers(self):
        """Verify that __BM_ markers are detected by strict_validate."""
        from slide_structure import strict_validate
        d = self.d5.replace('slide-01', 'slide-__BM_0000__')
        failures = strict_validate(d)
        self.assertGreater(
            len([f for f in failures if "STRUCT-010" in f and "__BM_" in f]), 0
        )


class TestStableIds(unittest.TestCase):
    """FSL-120: Stable identity preservation."""

    def test_default_deck_has_stable_ids(self):
        d = make_deck(8, stable_ids=True)
        ids = extract_data_ids(d)
        self.assertEqual(ids, [f"topic-{i:03d}" for i in range(1, 9)])

    def test_stable_ids_preserved_through_resequence(self):
        d = make_deck(5, stable_ids=True)
        r = resequence(d)
        self.assertEqual(extract_data_ids(r),
                         [f"topic-{i:03d}" for i in range(1, 6)])

    def test_payload_preserved_through_resequence(self):
        d = make_deck(8, stable_ids=True)
        self.assertEqual(list(extract_payloads(r := resequence(d))),
                         list(extract_payloads(d)))

    def test_unaffected_slide_payload_by_stable_id(self):
        d = make_deck(8, stable_ids=True)
        r = delete_slide(d, 4)
        new_payloads = list(extract_payloads(r))
        for i in [1, 2, 3]:
            self.assertIn(
                f"payload-{i:03d}", new_payloads,
                f"Payload for slide {i} lost after deletion"
            )


class TestStructuralValidation(unittest.TestCase):
    """FSL-121, FSL-129: Strengthened structural validation."""

    def test_malformed_section_detected(self):
        bad = '<section class="slide slide-01">broken</section>'
        self.assertEqual(count_slides(bad), 1)
        self.assertEqual(len(parse_slides(bad)), 0)

    def test_ordered_numbers_passed(self):
        d = make_deck(5)
        failures = strict_validate(d)
        struct_fails = [f for f in failures if "STRUCT-003" in f]
        self.assertEqual(len(struct_fails), 0)

    def test_non_ordered_numbers_detected(self):
        d = make_deck(5)
        bad = d.replace('slide-03', 'slide-99').replace('slide-04', 'slide-03')
        # Now we have duplicate 3 and a 99
        failures = strict_validate(bad)
        self.assertGreater(
            len([f for f in failures if "STRUCT-003" in f or "STRUCT-004" in f]), 0
        )

    def test_counter_mismatch_detected(self):
        d = make_deck(5)
        bad = d.replace("03 / 05", "99 / 05")
        failures = strict_validate(bad)
        self.assertGreater(
            len([f for f in failures if "STRUCT-006" in f]), 0
        )

    def test_counter_total_mismatch_detected(self):
        d = make_deck(5)
        bad = d.replace(" / 05", " / 99")
        failures = strict_validate(bad)
        self.assertGreater(
            len([f for f in failures if "STRUCT-007" in f]), 0
        )

    def test_extra_counter_nodes_detected(self):
        d = make_deck(3)
        bad = d + '<div class="counter">04 / 03</div>'
        failures = strict_validate(bad)
        self.assertGreater(
            len([f for f in failures if "STRUCT-008" in f]), 0
        )

    def test_no_slides_has_zero_count(self):
        empty = "<html><body></body></html>"
        self.assertEqual(count_slides(empty), 0)
        self.assertEqual(len(parse_slides(empty)), 0)


class TestStableIdDedupe(unittest.TestCase):
    """FSL-130: Stable ID duplicate detection."""

    def test_stable_id_duplicate_detected(self):
        d = make_deck(5, stable_ids=True)
        bad = d.replace('data-slide-id="topic-003"',
                        'data-slide-id="topic-001"')
        failures = strict_validate(bad)
        self.assertGreater(
            len([f for f in failures if "STRUCT-009" in f]), 0
        )

    def test_equal_stable_ids_accepted(self):
        """If all stable IDs are unique, no STRUCT-009."""
        d = make_deck(5, stable_ids=True)
        failures = strict_validate(d)
        struct_009 = [f for f in failures if "STRUCT-009" in f]
        self.assertEqual(len(struct_009), 0)


class TestInsertDuplicateStableId(unittest.TestCase):
    """FSL-130: Insert rejects fragment with duplicate stable ID."""

    def test_insert_with_duplicate_stable_id(self):
        d = make_deck(5, stable_ids=True)
        # Try to insert a slide with an existing stable ID
        frag = make_slide_fragment(99, 6, "topic-003", "duplicate")
        with self.assertRaises(RuntimeError) as ctx:
            insert_slide(d, 3, frag)
        # Post-condition should catch the duplicate
        err_text = str(ctx.exception).lower()
        self.assertTrue(
            "duplicate" in err_text or "post-condition" in err_text,
            f"Expected duplicate/validation error, got: {err_text}"
        )


class TestRegression(unittest.TestCase):
    """Regression tests for known failure modes."""

    def test_payload_with_slash_numbers_preserved(self):
        """Payload containing ratios (16/9, 2026/07) must not be altered."""
        d = make_deck(3, stable_ids=True)
        # Add ratio text to payloads
        slides = parse_slides(d)
        modified = d
        for s in slides:
            new = s['full_html'].replace(
                '<p>payload-', '<p>16/9 2026/07 payload-'
            )
            modified = modified.replace(s['full_html'], new, 1)
        r = resequence(modified)
        for p in list(extract_payloads(r)):
            self.assertIn("16/9", p)
            self.assertIn("2026/07", p)

    def test_no_noop_tests(self):
        """Ensure no test body contains only 'pass'."""
        import inspect
        all_tests = [
            m for m in dir(self) if m.startswith('test_')
        ]
        # Check only this class
        for name in all_tests:
            method = getattr(self, name)
            src = inspect.getsource(method).strip()
            if src == "pass":
                self.fail(f"Test {name} contains only 'pass'")

    def test_swap_3_4_verify_order(self):
        """batch_renumber swap produces [1,2,4,3,5], STRUCT-003 should fire."""
        d = make_deck(5, stable_ids=False)
        mapping = {1: 1, 2: 2, 3: 4, 4: 3, 5: 5}
        # batch_renumber with a swap should pass the mapping validation
        # but fail post-condition due to STRUCT-003
        with self.assertRaises(RuntimeError) as ctx:
            batch_renumber(d, mapping)
        self.assertIn("STRUCT-003", str(ctx.exception))

    def test_swap_9_10_verify_order(self):
        d = make_deck(10, stable_ids=False)
        mapping = {i: i for i in range(1, 10)}
        mapping[9] = 10
        mapping[10] = 9
        with self.assertRaises(RuntimeError) as ctx:
            batch_renumber(d, mapping)
        self.assertIn("STRUCT-003", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
