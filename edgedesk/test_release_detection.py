"""Check published-release skipping and unpublished source-tag retries."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class ReleaseDetectionTest(unittest.TestCase):
    def test_published_release_skips_and_draft_retries(self):
        for published in (True, False):
            with self.subTest(published=published), tempfile.TemporaryDirectory() as directory:
                outputs = Path(directory) / 'outputs'
                summary = Path(directory) / 'summary'

                def query(args, **kwargs):
                    if args == ('gh', 'api', 'repos/rustdesk/rustdesk/releases/latest'):
                        return json.dumps({'tag_name': '1.2.3', 'draft': False, 'prerelease': False})
                    self.assertEqual(args[:2], ('git', 'ls-remote'))
                    return 'existing-source-tag'

                def release(args, **kwargs):
                    self.assertEqual(args[:3], ['gh', 'release', 'view'])
                    return subprocess.CompletedProcess(args, 0, json.dumps({'isDraft': not published}), '')

                env = {'GITHUB_OUTPUT': str(outputs), 'GITHUB_STEP_SUMMARY': str(summary),
                       'GITHUB_REPOSITORY': 'EdgeAlphix/EdgeDesk'}
                with patch.dict(os.environ, env), patch('subprocess.check_output', side_effect=query), \
                        patch('subprocess.run', side_effect=release), self.assertRaises(SystemExit) as result:
                    runpy.run_path(str(Path(__file__).with_name('prepare_release.py')))
                self.assertEqual(result.exception.code, 0)
                values = dict(line.split('=', 1) for line in outputs.read_text().splitlines())
                self.assertEqual(values['build'], 'false' if published else 'true')
                self.assertIn(f"https://github.com/EdgeAlphix/EdgeDesk/releases/tag/{values['tag']}", summary.read_text())
                if published:
                    self.assertNotIn('source_ref', values)
                    self.assertIn('already published; compilation and publishing were skipped', summary.read_text())
                else:
                    self.assertEqual(values['source_ref'], values['tag'])
                    self.assertIn('Platform compilation and publishing will follow', summary.read_text())


if __name__ == '__main__':
    unittest.main()
