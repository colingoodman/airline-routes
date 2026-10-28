import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import refresh_runner as runner
from rebuild import write_json

class RunnerTests(unittest.TestCase):
    def args(self,root,*extra):
        return runner.parser().parse_args(['--state',str(root),*extra])
    def successful_candidate(self,command,*_):
        candidate=Path(command[command.index('--candidate')+1])
        write_json(candidate/'manifest.json',{'status':'validated','validation':'reviewed_snapshot'})
        write_json(candidate/'changes.json',{'semantic_change':False,'hold_reasons':[]})
    def test_lock_prevents_overlapping_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            lock=runner.locked(root)
            try:
                with patch.object(runner,'execute') as execute:
                    self.assertEqual(runner.run(self.args(root)),{'status':'already_running'})
                execute.assert_not_called()
            finally:lock.close()
    def test_unchanged_run_records_success_without_touching_published_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(runner,'execute',side_effect=self.successful_candidate):
                state=runner.run(self.args(root))
            self.assertEqual(state['status'],'unchanged')
            self.assertIn('last_successful_at',state)
    def test_collection_failure_preserves_last_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            write_json(root/'state.json',{'last_successful_at':'2026-10-01','last_published_at':'2026-09-30'})
            with patch.object(runner,'execute',side_effect=RuntimeError('source unavailable')):
                state=runner.run(self.args(root))
            self.assertEqual(state['status'],'failed')
            self.assertEqual(state['last_successful_at'],'2026-10-01')
            self.assertEqual(state['last_published_at'],'2026-09-30')
            lock=runner.locked(root)
            self.assertIsNotNone(lock)
            lock.close()
    def test_disk_budget_stops_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'cache').write_bytes(b'x'*1024*1024)
            with patch.object(runner,'execute') as execute:
                state=runner.run(self.args(root,'--max-disk-mib','1'))
            self.assertEqual(state['status'],'failed')
            execute.assert_not_called()
    def test_runtime_budget_terminates_process_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaisesRegex(RuntimeError,'runtime budget'):
                runner.execute([sys.executable,'-c','import time;time.sleep(30)'],root/'job.log',root,0.05,1024*1024)
    def test_retention_only_deletes_owned_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ['001','002','003']:write_json(root/name/'manifest.json',{})
            (root/'unrelated').mkdir()
            runner.prune_candidates(root,2)
            self.assertFalse((root/'001').exists())
            self.assertTrue((root/'002').exists())
            self.assertTrue((root/'unrelated').exists())

if __name__=='__main__':unittest.main()
