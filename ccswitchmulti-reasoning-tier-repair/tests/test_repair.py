import importlib.util
import json
import sqlite3
import tempfile
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


class DatabaseRepairTests(unittest.TestCase):
    def test_database_drift_and_repair_updates_all_effort_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cc-switch.db"
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE providers (
                    id TEXT NOT NULL,
                    app_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    settings_config TEXT NOT NULL,
                    is_current INTEGER,
                    in_failover_queue INTEGER,
                    PRIMARY KEY (id, app_type)
                );
                CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE proxy_live_backup (
                    app_type TEXT PRIMARY KEY,
                    original_config TEXT NOT NULL,
                    backed_up_at TEXT NOT NULL
                );
                """
            )
            old_provider = json.dumps(
                {
                    "config": (
                        'model_reasoning_effort = "xhigh"\n'
                        'model = "deepseek-v4-flash-0731"'
                    )
                }
            )
            conn.execute(
                "INSERT INTO providers VALUES (?, ?, ?, ?, ?, ?)",
                ("old-provider", "codex", "旧DeepSeek", old_provider, 0, 0),
            )
            conn.execute(
                "INSERT INTO settings VALUES (?, ?)",
                ("common_config_codex", 'model_reasoning_effort = "xhigh"'),
            )
            conn.execute(
                "INSERT INTO proxy_live_backup VALUES (?, ?, ?)",
                (
                    "codex",
                    '{"config":"model_reasoning_effort = \\"xhigh\\""}',
                    "now",
                ),
            )
            conn.commit()
            conn.close()

            changes = repair.database_drift(db_path, "max")
            self.assertEqual(3, len(changes))

            repaired, backup_path = repair.repair_database(
                db_path, "max", Path(tmp) / "backups"
            )
            self.assertEqual(3, len(repaired))
            self.assertTrue(backup_path.exists())
            self.assertEqual([], repair.database_drift(db_path, "max"))

            conn = sqlite3.connect(db_path)
            try:
                provider_config = conn.execute(
                    "SELECT settings_config FROM providers WHERE id=?",
                    ("old-provider",),
                ).fetchone()[0]
                settings_value = conn.execute(
                    "SELECT value FROM settings WHERE key='common_config_codex'"
                ).fetchone()[0]
                live_backup = conn.execute(
                    "SELECT original_config FROM proxy_live_backup WHERE app_type='codex'"
                ).fetchone()[0]
            finally:
                conn.close()

            self.assertIn('model_reasoning_effort = \\"max\\"', provider_config)
            self.assertIn('model_reasoning_effort = "max"', settings_value)
            self.assertIn('model_reasoning_effort = \\"max\\"', live_backup)


if __name__ == "__main__":
    unittest.main()
