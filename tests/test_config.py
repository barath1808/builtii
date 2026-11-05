import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import config


class EnvironmentConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = Path(self.temp.name) / '.env'

    def test_dotenv_loads_key_and_model_without_interpolation(self):
        self.env.write_text('GEMINI_API_KEY=synthetic-${unchanged}\nGEMINI_MODEL=test-preview-model\n', encoding='utf-8-sig')
        with patch.dict(os.environ, {}, clear=True):
            config.load_environment(self.env)
            self.assertEqual(config.api_key(), 'synthetic-${unchanged}')
            self.assertEqual(config.models(), {'ai1':'test-preview-model', 'ai2':'test-preview-model'})

    def test_existing_environment_has_priority(self):
        self.env.write_text('GEMINI_API_KEY=file-value\nGEMINI_MODEL=file-model\n')
        with patch.dict(os.environ, {'GEMINI_API_KEY':'process-value', 'GEMINI_MODEL':'process-model'}, clear=True):
            config.load_environment(self.env)
            self.assertEqual(config.api_key(), 'process-value')
            self.assertEqual(config.models()['ai1'], 'process-model')

    def test_missing_dotenv_does_not_invent_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            config.load_environment(self.env)
            self.assertEqual(config.api_key(), '')

    def test_fresh_process_automatically_loads_working_directory_dotenv(self):
        self.env.write_text('GEMINI_API_KEY=synthetic-fixture-key\nGEMINI_MODEL=test-preview-model\n')
        process_env = os.environ.copy()
        for key in ('GEMINI_API_KEY','GEMINI_MODEL','GEMINI_AUDIT_MODEL'):
            process_env.pop(key, None)
        process_env['PYTHONPATH'] = str(Path(config.__file__).resolve().parent)
        result = subprocess.run([sys.executable, '-c',
            'import config; from pipeline.gemini_service import Gemini; '
            'p=Gemini(); assert bool(p.key); assert p.models["ai1"]=="test-preview-model"'],
            cwd=self.temp.name, env=process_env, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
