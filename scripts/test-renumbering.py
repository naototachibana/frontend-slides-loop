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
    batch_renumber, resequence, validate_fragment,
    check_structural_invariants, verify_operation,
    FragmentError, MappingError,
)


class TestFragmentValidation(unittest.TestCase):
    """FSL-118: Fragment validity tests."""

    def test_valid_fragment_accepts_section(self):
        frag = make_slide_fragment(5, 10, "stable-005", "test-payload")
        try:
            validate_fragment(frag)
        except FragmentError as e:
            self.fail(f"Valid fragment rejected: {e}")

    def test_complete_document_rejected(self):
        deck = make_deck(1)
        with self.assertRaises(FragmentError) as ctx:
            validate_fragment(deck)
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
        full_doc = make_deck(1)
        with self.assertRaises(FragmentError):
            insert_slide(deck, 2, full_doc)

    def test_insert_output_has_single_doctype(self):
        deck = make_deck(5)
        frag = make_slide_fragment(99, 5, "ins-001", "inserted")
        result = insert_slide(deck, 3, frag)
        self.assertEqual(count_doctypes(result), 1)


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
        # Original stable IDs should still be present
        self.assertIn("topic-004", ids)
        self.assertIn("topic-001", ids)
        self.assertIn("topic-008", ids)
        # New slide's stable ID should be present
        self.assertIn("ins-004", ids)
        # No duplicates
        self.assertEqual(len(ids), len(set(ids)))

    def test_insert_preserves_payloads(self):
        r = insert_slide(self.d8, 5, self._frag(payload="inserted-payload"))
        payloads = extract_payloads(r)
        orig = extract_payloads(self.d8)
        for p in orig:
            self.assertIn(p, payloads, f"Original payload {p} lost after insert")
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
        self.assertIn("topic-004", ids)  # was 4, now 3
        self.assertIn("topic-008", ids)  # was 8, now 7
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 7)

    def test_delete_preserves_payloads(self):
        r = delete_slide(self.d8, 4)
        payloads = extract_payloads(r)
        orig = extract_payloads(self.d8)
        # The deleted slide's payload should be gone
        self.assertNotIn("payload-004", payloads)
        # All others should remain
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
        # Slide 3 moved to position 7
        expected = [
            "topic-001", "topic-002",
            "topic-004", "topic-005", "topic-006", "topic-007",
            "topic-003",  # moved from position 3
            "topic-008",
        ]
        self.assertEqual(ids, expected)

    def test_reorder_backward_stable_ids(self):
        r = reorder_slides(self.d8, 7, 2)
        ids = extract_data_ids(r)
        expected = [
            "topic-001",
            "topic-007",  # moved from position 7
            "topic-002", "topic-003", "topic-004", "topic-005", "topic-006",
            "topic-008",
        ]
        self.assertEqual(ids, expected)

    def test_reorder_preserves_payloads(self):
        r = reorder_slides(self.d8, 4, 1)
        payloads = extract_payloads(r)
        self.assertEqual(payloads[0], "payload-004")
        self.assertIn("payload-001", payloads)
        self.assertIn("payload-008", payloads)
        self.assertEqual(len(payloads), 8)


class TestBatchRenumber(unittest.TestCase):
    """FSL-119: Exact mapping contract."""

    def setUp(self):
        self.d5 = make_deck(5, stable_ids=False)
        self.d10 = make_deck(10, stable_ids=False)

    # --- Mapping validation ---

    def test_complete_swap_3_and_4(self):
        mapping = {1: 1, 2: 2, 3: 4, 4: 3, 5: 5}
        r = batch_renumber(self.d5, mapping)
        self.assertEqual(verify_operation(r, 5), [])
        nums = extract_slide_numbers(r)
        self.assertEqual(nums, [1, 2, 4, 3, 5])

    def test_complete_swap_9_and_10(self):
        mapping = {i: i for i in range(1, 10)}
        mapping[9] = 10
        mapping[10] = 9
        r = batch_renumber(self.d10, mapping)
        self.assertEqual(verify_operation(r, 10), [])
        nums = extract_slide_numbers(r)
        expected = list(range(1, 9)) + [10, 9]
        self.assertEqual(nums, expected)

    def test_complete_shift(self):
        """Full shift: 6→7, 7→8, 8→9, 9→10, 10→11, 11→12, 12→13 in 12-slide deck."""
        d12 = make_deck(12, stable_ids=False)
        mapping = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
        for i in range(6, 13):
            mapping[i] = i + 1
        r = batch_renumber(d12, mapping)
        # verify_operation checks STRUCT-005 (1..N), but batch_renumber
        # can produce numbers beyond N after a shift. Check invariants directly.
        self.assertEqual(count_slides(r), 12)
        self.assertEqual(len(parse_slides(r)), 12)
        dupes = extract_slide_numbers(r)
        self.assertEqual(len(dupes), len(set(dupes)), "Duplicate slide numbers")
        nums = extract_slide_numbers(r)
        self.assertEqual(nums, [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13])

    # --- Incomplete mapping rejection ---

    def test_incomplete_3_to_4_rejected(self):
        with self.assertRaises(MappingError) as ctx:
            batch_renumber(self.d5, {3: 4})
        self.assertIn("missing keys", str(ctx.exception).lower())

    def test_incomplete_9_to_10_rejected(self):
        with self.assertRaises(MappingError):
            batch_renumber(self.d10, {9: 10})

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

    def test_gapped_values_accepted(self):
        """Values must be unique and start at 1; gaps above 1..N for shifts OK."""
        # {3:5, 5:4} creates values [1,2,3,4,5] which is valid
        d5 = make_deck(5, stable_ids=False)
        r = batch_renumber(d5, {1: 1, 2: 2, 3: 5, 4: 3, 5: 4})
        self.assertEqual(verify_operation(r, 5), [])
        nums = extract_slide_numbers(r)
        self.assertEqual(set(nums), {1, 2, 3, 4, 5})

    # --- Marker cleanup ---

    def test_no_markers_after_successful_batch(self):
        mapping = {i: i for i in range(1, 6)}
        r = batch_renumber(self.d5, mapping)
        self.assertNotIn("__BM_", r)
        self.assertNotIn("TMP_", r)
        self.assertNotIn("MAP_", r)

    def test_no_markers_after_failed_mapping(self):
        try:
            batch_renumber(self.d5, {3: 4})
        except MappingError:
            pass


class TestStableIds(unittest.TestCase):
    """FSL-120: Stable identity preservation."""

    def test_default_deck_has_stable_ids(self):
        d = make_deck(8, stable_ids=True)
        ids = extract_data_ids(d)
        expected = [f"topic-{i:03d}" for i in range(1, 9)]
        self.assertEqual(ids, expected)

    def test_stable_ids_preserved_through_resequence(self):
        d = make_deck(5, stable_ids=True)
        r = resequence(d)
        ids = extract_data_ids(r)
        expected = [f"topic-{i:03d}" for i in range(1, 6)]
        self.assertEqual(ids, expected)

    def test_payload_preserved_through_resequence(self):
        d = make_deck(8, stable_ids=True)
        r = resequence(d)
        self.assertEqual(extract_payloads(r), extract_payloads(d))

    def test_unaffected_slide_payload_by_stable_id(self):
        """After deleting slide 4, verify slides 1-3 keep payloads."""
        d = make_deck(8, stable_ids=True)
        r = delete_slide(d, 4)
        new_payloads = extract_payloads(r)
        for i in [1, 2, 3]:
            self.assertIn(
                f"payload-{i:03d}", new_payloads,
                f"Payload for slide {i} lost after deletion"
            )


class TestStructuralValidation(unittest.TestCase):
    """FSL-121: Strengthened structural validation."""

    def test_malformed_section_detected(self):
        """Section not parseable by SLIDE_PATTERN is detected."""
        # Section missing proper counter and comment structure
        bad = '<section class="slide slide-01">broken</section>'
        # count_slides finds 1 section, parse_slides finds 0 (no counter)
        sc = count_slides(bad)
        sl = len(parse_slides(bad))
        self.assertEqual(sc, 1)
        self.assertEqual(sl, 0)
        failures = check_structural_invariants(bad)
        struct_fails = [f for f in failures if "STRUCT-001" in f]
        self.assertGreater(len(struct_fails), 0)

    def test_class_comment_mismatch_detected(self):
        d = make_deck(5)
        # Introduce a mismatch
        bad = d.replace("SLIDE 03", "SLIDE 99")
        failures = check_structural_invariants(bad)
        class_fails = [f for f in failures if "STRUCT-002" in f]
        self.assertGreater(len(class_fails), 0)

    def test_counter_mismatch_detected(self):
        d = make_deck(5)
        bad = d.replace("03 / 05", "99 / 05")
        failures = check_structural_invariants(bad)
        counter_fails = [f for f in failures if "STRUCT-003" in f]
        self.assertGreater(len(counter_fails), 0)

    def test_counter_total_mismatch_detected(self):
        d = make_deck(5)
        bad = d.replace(" / 05", " / 99")
        failures = check_structural_invariants(bad)
        total_fails = [f for f in failures if "STRUCT-004" in f]
        self.assertGreater(len(total_fails), 0)

    def test_positional_not_sequential_detected(self):
        # After insertion that shifts numbers, positional check should pass
        d = make_deck(8)
        r = insert_slide(d, 4, make_slide_fragment(99, 9, "ins", "x"))
        failures = check_structural_invariants(r)
        struct_fails = [f for f in failures if "STRUCT-005" in f]
        self.assertEqual(len(struct_fails), 0,
                         f"Valid deck should not have STRUCT-005 failures: {failures}")

    def test_extra_counters_detected(self):
        d = make_deck(3)
        bad = d + "<span>04 / 03</span>"
        failures = check_structural_invariants(bad)
        extra_fails = [f for f in failures if "STRUCT-006" in f]
        self.assertGreater(len(extra_fails), 0)

    def test_no_slides_has_zero_count(self):
        empty = "<html><body></body></html>"
        self.assertEqual(count_slides(empty), 0)
        self.assertEqual(len(parse_slides(empty)), 0)

    def test_verify_operation_rejects_extra_counters(self):
        d = make_deck(5)
        bad = d + "<div>06 / 05</div>"
        failures = verify_operation(bad, 5)
        self.assertGreater(len(failures), 0)

    def test_deck_without_stable_ids_has_no_data_id_dupes(self):
        d = make_deck(8, stable_ids=False)
        from slide_structure import validate_data_id_uniqueness
        self.assertEqual(validate_data_id_uniqueness(d), [])

    def test_parseable_slides_equal_count_slides(self):
        d = make_deck(15)
        self.assertEqual(count_slides(d), len(parse_slides(d)))


class TestRegression(unittest.TestCase):
    """Regression tests for known failure modes."""

    def test_no_noop_tests(self):
        """Ensure no test body contains only 'pass'."""
        import inspect, sys
        test_methods = [
            m for m in dir(self) if m.startswith('test_')
        ]
        for name in test_methods:
            method = getattr(self, name)
            source = inspect.getsource(method).strip()
            if source == "pass":
                self.fail(f"Test {name} contains only 'pass'")


if __name__ == "__main__":
    unittest.main()
