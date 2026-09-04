import os
import sys
import unittest
from pathlib import Path

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from generate_image import resolve_configuration, mask_key, OFFICIAL_BASE_URL, DEFAULT_MODEL


class TestGrokConfigurationResolution(unittest.TestCase):
    def setUp(self):
        # Clean up any test environment variables
        self.orig_env = os.environ.copy()
        for k in ["XAI_API_KEY", "XAI_BASE_URL", "GROK_API_KEY", "GROK_BASE_URL", "GROK_IMAGE_MODEL"]:
            if k in os.environ:
                del os.environ[k]

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.orig_env)

    def test_cli_explicit_override(self):
        base_url, api_key, model, src = resolve_configuration(
            cli_base_url="https://custom-grok.com/v1",
            cli_api_key="xai-cli-test-key",
            cli_model="grok-imagine-image",
        )
        self.assertEqual(base_url, "https://custom-grok.com/v1")
        self.assertEqual(api_key, "xai-cli-test-key")
        self.assertEqual(model, "grok-imagine-image")
        self.assertEqual(src, "cli:custom_base_url")

    def test_force_official_override(self):
        os.environ["XAI_BASE_URL"] = "https://some-proxy.com/v1"
        os.environ["XAI_API_KEY"] = "xai-env-key"

        base_url, api_key, model, src = resolve_configuration(
            force_official=True
        )
        self.assertEqual(base_url, OFFICIAL_BASE_URL)
        self.assertEqual(api_key, "xai-env-key")
        self.assertEqual(src, "cli:force_official")

    def test_mask_key(self):
        self.assertEqual(mask_key(""), "(none)")
        self.assertEqual(mask_key(None), "(none)")
        self.assertEqual(mask_key("1234"), "****")
        self.assertEqual(mask_key("xai-1234567890abcdef"), "xai-...cdef")


if __name__ == "__main__":
    unittest.main()
