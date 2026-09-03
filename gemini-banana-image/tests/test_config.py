import os
import sys
import unittest
from pathlib import Path

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from generate_image import resolve_configuration, mask_key


class TestConfigurationResolution(unittest.TestCase):
    def setUp(self):
        # Clean up any test environment variables
        self.orig_env = os.environ.copy()
        for k in ["GEMINI_BASE_URL", "GOOGLE_GEMINI_BASE_URL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_IMAGE_MODEL"]:
            if k in os.environ:
                del os.environ[k]

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.orig_env)

    def test_cli_explicit_override(self):
        base_url, api_key, model, src = resolve_configuration(
            cli_base_url="https://proxy.example.com",
            cli_api_key="sk-cli-12345",
            cli_model="imagen-3.0-generate-002",
        )
        self.assertEqual(base_url, "https://proxy.example.com")
        self.assertEqual(api_key, "sk-cli-12345")
        self.assertEqual(model, "imagen-3.0-generate-002")
        self.assertEqual(src, "cli:custom_base_url")

    def test_force_official_override(self):
        os.environ["GEMINI_BASE_URL"] = "https://some-proxy.com"
        os.environ["GEMINI_API_KEY"] = "sk-env-key"

        base_url, api_key, model, src = resolve_configuration(
            force_official=True
        )
        self.assertIsNone(base_url)
        self.assertEqual(api_key, "sk-env-key")
        self.assertEqual(src, "cli:force_official")

    def test_mask_key(self):
        self.assertEqual(mask_key(""), "(none)")
        self.assertEqual(mask_key(None), "(none)")
        self.assertEqual(mask_key("12345"), "****")
        self.assertEqual(mask_key("sk-1234567890abcdef"), "sk-1...cdef")


if __name__ == "__main__":
    unittest.main()
