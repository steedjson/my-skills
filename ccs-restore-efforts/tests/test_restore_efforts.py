import importlib.util
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "restore_efforts.py"
SPEC = importlib.util.spec_from_file_location("restore_efforts", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RestoreReasoningCapabilityTests(unittest.TestCase):
    def test_deepseek_nested_capability_is_restored(self):
        model = {"id": "deepseek-v4-pro"}

        changed, _ = MODULE.patch_model_metadata(model)

        self.assertTrue(changed)
        self.assertEqual(model["defaultReasoningEffort"], "high")
        self.assertEqual(model["reasoning"]["supportedEfforts"], ["low", "high", "max"])
        self.assertEqual(model["reasoning"]["defaultEffort"], "high")
        self.assertEqual(model["reasoning"]["upstream"]["effortMap"]["medium"], "high")

    def test_grok_preserves_v31_reasoning_object_shape(self):
        model = {
            "id": "grok-4.5",
            "reasoning": {
                "supported": True,
                "supportedEfforts": ["low"],
                "defaultEffort": "low",
                "upstream": {"format": "string", "parameter": "old"},
            },
        }

        MODULE.patch_model_metadata(model)

        self.assertEqual(model["reasoning"]["supportedEfforts"], ["low", "medium", "high"])
        self.assertEqual(model["reasoning"]["defaultEffort"], "high")
        self.assertEqual(model["reasoning"]["upstream"]["format"], "reasoning_object")
        self.assertEqual(model["reasoning"]["upstream"]["parameter"], "reasoning.effort")

    def test_unknown_model_is_not_given_nested_capability(self):
        model = {"id": "vendor-new-model"}

        MODULE.patch_model_metadata(model)

        self.assertNotIn("reasoning", model)

    def test_nested_capability_patch_is_idempotent(self):
        model = {"id": "deepseek-v4-flash"}

        MODULE.patch_model_metadata(model)
        snapshot = repr(model)
        changed, speed_changed = MODULE.patch_model_metadata(model)

        self.assertFalse(changed)
        self.assertFalse(speed_changed)
        self.assertEqual(repr(model), snapshot)

    def test_inline_model_receives_nested_reasoning_capability(self):
        table = '{ model = "deepseek-v4-pro", id = "deepseek-v4-pro" }'

        patched, changed, _, _, _ = MODULE.patch_inline_model_table(table)
        repeated, repeated_changed, _, _, _ = MODULE.patch_inline_model_table(patched)

        self.assertTrue(changed)
        self.assertIn('supportedEfforts = ["low", "high", "max"]', patched)
        self.assertIn('parameter = "reasoning_effort"', patched)
        self.assertEqual(patched, repeated)
        self.assertFalse(repeated_changed)


if __name__ == "__main__":
    unittest.main()
