import importlib.util
import json
import plistlib
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
ALIASES = {
    "deepseek-v4-flash-0731": "deepseek-v4-flash-0731-csap-tokenplan",
    "deepseek-v4-pro": "deepseek-v4-pro-csap-tokenplan",
}


class RuntimeDiagnosticsTests(unittest.TestCase):
    def test_detects_runtime_without_max(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "CCSwitchMulti.app"
            info_dir = app / "Contents"
            binary_dir = info_dir / "MacOS"
            binary_dir.mkdir(parents=True)
            (info_dir / "Info.plist").write_bytes(
                plistlib.dumps({"CFBundleShortVersionString": "3.19.1-9"})
            )
            (binary_dir / "cc-switch").write_bytes(
                b'const reasoningEfforts = () => ["low", "medium", "high", "xhigh"].map(...)'
            )

            diagnostics = repair.ccswitch_runtime_diagnostics(app)
            self.assertEqual("3.19.1-9", diagnostics["version"])
            self.assertEqual(["low", "medium", "high", "xhigh"], diagnostics["picker_efforts"])
            self.assertFalse(diagnostics["supports_max"])
            warning = repair.runtime_effort_warning(diagnostics, "max")
            self.assertIsNotNone(warning)
            self.assertIn("normalize the selected effort to xhigh", warning)

    def test_runtime_with_max_has_no_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "CCSwitchMulti.app"
            binary_dir = app / "Contents" / "MacOS"
            binary_dir.mkdir(parents=True)
            (binary_dir / "cc-switch").write_bytes(
                b'const reasoningEfforts = () => ["low", "medium", "high", "xhigh", "max"].map(...)'
            )

            diagnostics = repair.ccswitch_runtime_diagnostics(app)
            self.assertTrue(diagnostics["supports_max"])
            self.assertIsNone(repair.runtime_effort_warning(diagnostics, "max"))


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
        repaired_again, changes_again, unresolved_again = repair.repair_config(
            updated, EXPECTED, DESCRIPTIONS, "max"
        )
        self.assertEqual(updated, repaired_again)
        self.assertEqual([], changes_again)
        self.assertEqual([], unresolved_again)

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

    def test_keeps_deepseek_max_for_active_model(self):
        config = """
model = "deepseek-v4-flash-0731"
model_reasoning_effort = "medium"

[model_providers.custom]
models = [
  { model = "deepseek-v4-flash-0731", upstreamModel = "deepseek-v4-flash-0731", default_reasoning_effort = "medium", default_reasoning_level = "medium", supported_reasoning_levels = [ { effort = "low", description = "Low" }, { effort = "xhigh", description = "Extra high" } ] }
]
"""
        updated, changes, unresolved = repair.repair_config(
            config,
            EXPECTED,
            DESCRIPTIONS,
            "max",
            ALIASES,
        )

        self.assertIn('model_reasoning_effort = "max"', updated)
        self.assertIn('default_reasoning_effort = "max"', updated)
        self.assertIn('default_reasoning_level = "max"', updated)
        self.assertIn('effort = "max"', updated)
        self.assertTrue(any("defaults" in change and "max" in change for change in changes))
        self.assertEqual([], unresolved)

    def test_catalog_alias_repairs_defaults_but_keeps_max_option(self):
        catalog = {
            "models": [
                {
                    "model": "deepseek-v4-flash-0731",
                    "upstream_model": "deepseek-v4-flash-0731",
                    "default_reasoning_effort": "medium",
                    "default_reasoning_level": "medium",
                    "supported_reasoning_levels": [
                        {"effort": "low", "description": "Low"},
                        {"effort": "xhigh", "description": "Extra high"},
                    ],
                }
            ]
        }

        changes, unresolved = repair.repair_catalog(
            catalog,
            EXPECTED,
            DESCRIPTIONS,
            "max",
            ALIASES,
        )

        model = catalog["models"][0]
        self.assertEqual("max", model["default_reasoning_effort"])
        self.assertEqual("max", model["default_reasoning_level"])
        self.assertEqual(
            ["low", "xhigh", "max"],
            [item["effort"] for item in model["supported_reasoning_levels"]],
        )
        self.assertTrue(changes)
        self.assertEqual([], unresolved)
        changes_again, unresolved_again = repair.repair_catalog(
            catalog, EXPECTED, DESCRIPTIONS, "max", ALIASES
        )
        self.assertEqual([], changes_again)
        self.assertEqual([], unresolved_again)


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
            repaired_again, backup_again = repair.repair_database(
                db_path, "max", Path(tmp) / "backups"
            )
            self.assertEqual([], repaired_again)
            self.assertIsNone(backup_again)

    def test_database_keeps_deepseek_max_and_common_config_max(self):
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
            provider_config = json.dumps(
                {
                    "config": (
                        'model = "deepseek-v4-flash-0731"\n'
                        'model_reasoning_effort = "max"'
                    )
                }
            )
            conn.execute(
                "INSERT INTO providers VALUES (?, ?, ?, ?, ?, ?)",
                ("deepseek-provider", "codex", "DeepSeek", provider_config, 0, 0),
            )
            conn.execute(
                "INSERT INTO settings VALUES (?, ?)",
                ("common_config_codex", 'model_reasoning_effort = "max"'),
            )
            conn.execute(
                "INSERT INTO proxy_live_backup VALUES (?, ?, ?)",
                ("codex", provider_config, "now"),
            )
            conn.commit()
            conn.close()

            self.assertEqual([], repair.database_drift(db_path, "max"))
            repaired, backup_path = repair.repair_database(
                db_path, "max", Path(tmp) / "backups"
            )
            self.assertEqual([], repaired)
            self.assertIsNone(backup_path)


if __name__ == "__main__":
    unittest.main()
