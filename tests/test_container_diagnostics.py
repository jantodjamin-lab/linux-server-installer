"""Offline checks for isolated layer-2 failure artifacts; no tool execution."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_core import fixture


class ContainerDiagnosticsTests(unittest.TestCase):
    def harness(self):
        path=Path(__file__).resolve().parents[1]/'tools/container-test.py'
        spec=importlib.util.spec_from_file_location('container_harness_test',path)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_failed_probe_saved_before_resolve_with_long_harness_transport(self):
        module=self.harness(); data=fixture()
        data.update(errors=['package-source-inventory'],
                    diagnostics=[{'stage':'package-source-inventory',
                                  'code':'package-source-inventory-probe-failed',
                                  'tool':'https://user:password@example.org',
                                  'stderr':'private-password'}],
                    source_policy_valid=True,key_valid=True,
                    source_metadata='verified-cached')
        out=io.StringIO(); err=io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'layer2.json'
            with patch.dict(os.environ,{'RC5_TEST_OUTPUT':str(output)}), \
                 patch.object(module,'inventory',return_value=data) as inventory, \
                 patch.object(module,'resolve') as resolve, \
                 contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
                with self.assertRaisesRegex(ValueError,'preflight-failed'):
                    module.resolve_profiles([],'canonical-image-sources')
            inventory.assert_called_once_with(query_fn=module.command,allow_mirrors=())
            resolve.assert_not_called()
            result=json.loads(output.read_text())
            self.assertEqual(result['status'],'FAIL')
            self.assertEqual(result['profiles'][0]['failure']['code'],'preflight-failed')
            self.assertIn('package-source-inventory',result['profiles'][0]['preflight']['errors'])
            content=output.read_text()+out.getvalue()+err.getvalue()
            self.assertNotIn('password',content)
            self.assertNotIn('example.org',content)
            self.assertTrue(result['profiles'][0]['preflight']['checks'])


if __name__=='__main__':
    unittest.main()
