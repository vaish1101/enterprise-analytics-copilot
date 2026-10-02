import unittest
from decimal import Decimal

import pytest

from src.validation.reconciliation import (
    reconcile_henkel_nominal_change,
    reconcile_henkel_price_volume,
    reconcile_mercedes_bridge,
    reconcile_mercedes_reported_ebit,
)


class ReconciliationTests(unittest.TestCase):
    def test_henkel_price_volume_accepts_published_rounding(self):
        result = reconcile_henkel_price_volume("1.8", "2.8", "4.5")
        self.assertTrue(result.passed)
        self.assertEqual(Decimal("0.1"), result.difference)

    def test_henkel_price_volume_fails_outside_tolerance(self):
        result = reconcile_henkel_price_volume("1.8", "2.8", "4.5", "0.09")
        self.assertFalse(result.passed)

    @pytest.mark.negative
    def test_henkel_difference_beyond_point_one_fails(self):
        result = reconcile_henkel_price_volume("1.8", "2.9", "4.5", "0.1")
        self.assertFalse(result.passed)
        self.assertEqual(Decimal("0.2"), result.difference)

    def test_henkel_nominal_change_reconciles(self):
        result = reconcile_henkel_nominal_change("-3.9", "0.2", "3.2", "-0.5")
        self.assertTrue(result.passed)

    def test_mercedes_cars_bridge_reconciles(self):
        result = reconcile_mercedes_bridge(
            "1228", ["-602", "17", "482", "-194", "-28", "143", "-137"], "909"
        )
        self.assertTrue(result.passed)

    def test_mercedes_vans_bridge_reconciles(self):
        result = reconcile_mercedes_bridge(
            "441", ["98", "-16", "-94", "7", "-1", "38", "-19"], "454"
        )
        self.assertTrue(result.passed)

    def test_mercedes_financial_services_bridge_reconciles(self):
        result = reconcile_mercedes_bridge("290", ["-7", "66", "188", "31", "2", "-78"], "492")
        self.assertTrue(result.passed)

    def test_mercedes_adjusted_to_reported_reconciles(self):
        cases = [("909", "-860", "49"), ("454", "48", "502"), ("492", "-17", "475")]
        self.assertTrue(all(reconcile_mercedes_reported_ebit(*case).passed for case in cases))

    @pytest.mark.negative
    def test_mercedes_bridge_wrong_sign_fails(self):
        result = reconcile_mercedes_bridge(
            "1228", ["602", "17", "482", "-194", "-28", "143", "-137"], "909"
        )
        self.assertFalse(result.passed)

    @pytest.mark.negative
    def test_mercedes_bridge_wrong_component_fails(self):
        result = reconcile_mercedes_bridge(
            "1228", ["-601", "17", "482", "-194", "-28", "143", "-137"], "909"
        )
        self.assertFalse(result.passed)

    @pytest.mark.negative
    def test_mercedes_bridge_wrong_endpoint_fails(self):
        result = reconcile_mercedes_bridge(
            "1228", ["-602", "17", "482", "-194", "-28", "143", "-137"], "910"
        )
        self.assertFalse(result.passed)

    def test_negative_tolerance_is_rejected(self):
        with self.assertRaises(ValueError):
            reconcile_mercedes_bridge("1", [], "1", "-0.1")


if __name__ == "__main__":
    unittest.main()
