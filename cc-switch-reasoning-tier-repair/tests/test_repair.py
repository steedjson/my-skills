import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "repair.py"
SPEC = importlib.util.spec_from_file_location("reasoning_tier_repair", SCRIPT)
assert SPEC and SPEC.loader
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)


DESCRIPTIONS = {
    "low": "Low",
    "xhigh": "Extra high",
    "max": "Maximum",
}
EXPECTED = {
    "deepseek-v4-flash": ["low", "xhigh", "max"],
    "deepseek-v4-flash-0731-csap-tokenplan": ["low", "xhigh", "max"],
}


class RepairConfigTests(unittest.TestCase):
    def test_repairs_dynamic_provider_and_global_effort(self):
        config = """
model_reasoning_effort = "xhigh"

[model_providers.custom]
name = "CCSwitchMulti"
models = [
  { model = "deepseek-v4-flash-0731-csap-tokenplan", supported_reasoning_levels = [
    { effort = "low", description = "Low" },
    { effort = "xhigh", description = "Extra high" }
  ] }
]
"""
        updated, changes, unresolved = repair.repair_config(
            config, EXPECTED, DESCRIPTIONS, "max"
        )

        self.assertIn('model_reasoning_effort = "max"', updated)
        self.assertIn('effort = "max"', updated)
        self.assertTrue(any("custom/deepseek-v4-flash" in change for change in changes))
        self.assertEqual([], unresolved)

    def test_preserves_unknown_models(self):
        config = """
[model_providers.router_generated_id]
models = [
  { model = "unknown-model", supported_reasoning_levels = [
    { effort = "low", description = "Low" }
  ] },
  { model = "deepseek-v4-flash-0731-csap-tokenplan", supported_reasoning_levels = [
    { effort = "low", description = "Low" },
    { effort = "xhigh", description = "Extra high" }
  ] }
]
"""
        updated, _, unresolved = repair.repair_config(
            config, EXPECTED, DESCRIPTIONS
        )

        self.assertIn('model = "unknown-model"', updated)
        self.assertEqual(["unknown-model"], unresolved)

    def test_repairs_deepseek_alias_in_catalog(self):
        catalog = {
            "models": [
                {
                    "slug": "deepseek-v4-flash",
                    "supported_reasoning_levels": [
                        {"effort": "low", "description": "Low"},
                        {"effort": "xhigh", "description": "Extra high"},
                    ],
                }
            ]
        }

        changes, unresolved = repair.repair_catalog(
            catalog, EXPECTED, DESCRIPTIONS
        )

        levels = catalog["models"][0]["supported_reasoning_levels"]
        self.assertEqual(["low", "xhigh", "max"], [item["effort"] for item in levels])
        self.assertTrue(any("deepseek-v4-flash" in change for change in changes))
        self.assertEqual([], unresolved)


if __name__ == "__main__":
    unittest.main()
