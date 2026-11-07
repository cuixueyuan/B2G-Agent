import unittest

from b2g_agent.evaluation.goal_attainment import (family_scores,
                        family_windows, interval_coverage, scope_matches)


def source(families, target=100, windows=None):
    return {
        "operating_day": "day_1", "target_bems": ["bem_01"], "target_buses": [3],
        "task_families": families,
        "windows": windows or [{"start": "16:00", "end": "18:00"}],
        "fields": {"target_power": {"value": target, "unit": "kW"},
                   "offer_price": {"value": 50, "unit": "USD/MWh"}},
        "objectives": [{"name": f, "priority": i + 1} for i, f in enumerate(families)],
    }


class GoalRulesTests(unittest.TestCase):
    def test_clip_before_averaging_no_cross_interval_compensation(self):
        series = [0.0] * 96
        series[64] = 200
        self.assertEqual(interval_coverage(series, [64, 65], 100), 0.5)

    def test_absorption_direction(self):
        self.assertEqual(interval_coverage([-50.0] * 96, [1, 2], 100, -1), 0.5)
        self.assertEqual(interval_coverage([50.0] * 96, [1, 2], 100, -1), 0)

    def test_original_request_not_counteroffer_denominator(self):
        g, _, _, _ = family_scores(source(["reserve_service"]), {},
                                   {"native": [20.0] * 96})
        self.assertAlmostEqual(g, 0.2)

    def test_peak_requires_actual_peak_improvement(self):
        g, _, _, _ = family_scores(source(["peak_shaving"]),
                                   {"feeder_peak_reduction_kw": 30}, {"native": [100.0] * 96})
        self.assertEqual(g, 0.3)

    def test_zero_violation_baseline_does_not_award_goal_credit(self):
        g, _, _, _ = family_scores(source(["voltage_management"]),
                                   {"baseline_voltage_violation_area_pu_h": 0},
                                   {"native": [0.0] * 96})
        self.assertEqual(g, 0)

    def test_envelope_uses_weaker_direction_and_original_offer(self):
        g, _, _, _ = family_scores(source(["baseline_flexibility"]),
                                   {"validated_downward_flexibility_kw": 80,
                                    "validated_upward_flexibility_kw": 20}, {})
        self.assertEqual(g, 0.2)

    def test_market_checks_original_full_offer_settlement(self):
        g, _, _, _ = family_scores(source(["market_trading"]),
                                   {"settlement_usd": 5}, {"native": [100.0] * 96})
        self.assertEqual(g, 0.5)  # full original offer: 100 kW x 2 h x $50/MWh = $10

    def test_composite_priority_weights_sum_to_one(self):
        g, _, w, _ = family_scores(source(["peak_shaving", "reserve_service"]),
                                   {"feeder_peak_reduction_kw": 50}, {"native": [100.0] * 96})
        self.assertAlmostEqual(g, 2 / 3)
        self.assertAlmostEqual(sum(w.values()), 1)





    def test_original_scope_and_full_day_convention(self):
        s = source(["reserve_service"], windows=[{"start": "00:00", "end": "23:45"}])
        self.assertEqual(len(family_windows(s)["reserve_service"]), 96)
        self.assertTrue(scope_matches(s, s))
        other = dict(s, operating_day="another_day")
        self.assertFalse(scope_matches(s, other))


if __name__ == "__main__":
    unittest.main()
