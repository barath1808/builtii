from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from builtii import prompts


class PromptAssetTests(unittest.TestCase):
    def test_both_actual_prompts_include_shared_rules_and_schema(self):
        for stage, filename in (("ai1", "ai1_extract.md"), ("ai2", "ai2_audit.md")):
            composed = prompts.prompt(stage, 3, 10)
            self.assertIn((prompts.TEMPLATES / filename).read_text().strip(), composed)
            self.assertIn(prompts.RULES, composed)
            self.assertIn('Page 3 of 10. Set page=3.', composed)
            self.assertIn('"additionalProperties": false', composed)

    def test_editing_a_prompt_changes_cache_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ai1_extract.md'
            path.write_text('First instruction')
            with patch.object(prompts, 'TEMPLATES', Path(directory)):
                before = prompts.fingerprint()
                path.write_text('Revised instruction')
                self.assertNotEqual(before, prompts.fingerprint())

    def test_unknown_stage_is_rejected(self):
        with self.assertRaises(ValueError):
            prompts.prompt('other', 1, 1)
