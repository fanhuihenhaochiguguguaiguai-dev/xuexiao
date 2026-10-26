"""Integration checks against isolated local Git remotes; no GitHub access."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.sync_progress import ProgressSync, SyncError


class SyncIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.remote = self.base / 'remote.git'
        self.local = self.base / 'local'
        self.peer = self.base / 'peer'
        self.git(self.base, 'init', '--bare', str(self.remote))
        self.git(self.base, 'clone', str(self.remote), str(self.local))
        self.git(self.local, 'checkout', '-b', 'main')
        self.identity(self.local)
        (self.local / 'source.txt').write_text('base\n')
        self.commit(self.local, 'initial')
        self.git(self.local, 'push', '-u', 'origin', 'main')
        self.git(self.remote, 'symbolic-ref', 'HEAD', 'refs/heads/main')
        self.git(self.base, 'clone', str(self.remote), str(self.peer))
        self.identity(self.peer)
        self.config = {'validation_commands': [], 'max_push_attempts': 1,
                       'retry_delay_seconds': 0}
        self.sync = ProgressSync(self.local, self.config)

    @staticmethod
    def git(root, *args):
        result = subprocess.run(['git', *args], cwd=root, text=True,
                                capture_output=True, timeout=15)
        if result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout.strip()

    def identity(self, root):
        self.git(root, 'config', 'user.name', 'Sync test')
        self.git(root, 'config', 'user.email', 'test@example.invalid')

    def commit(self, root, message):
        self.git(root, 'add', '-A')
        self.git(root, 'commit', '-m', message)

    def peer_update(self, filename='remote.txt', content='remote\n'):
        (self.peer / filename).write_text(content)
        self.commit(self.peer, 'remote update')
        self.git(self.peer, 'push', 'origin', 'main')

    def remote_head(self, branch='main'):
        return self.git(self.remote, 'rev-parse', 'refs/heads/' + branch)

    def test_begin_fetches_remote_and_preserves_unrelated_edits(self):
        (self.local / 'active.txt').write_text('unfinished local work\n')
        self.peer_update()
        result = self.sync.begin()
        self.assertEqual(result['status'], 'FAST_FORWARDED')
        self.assertEqual((self.local / 'active.txt').read_text(), 'unfinished local work\n')
        self.assertTrue((self.local / 'remote.txt').exists())

    def test_dirty_overlap_defers_without_overwriting(self):
        (self.local / 'source.txt').write_text('unfinished\n')
        self.peer_update('source.txt', 'remote changed\n')
        result = self.sync.begin()
        self.assertEqual(result['status'], 'SYNC_DEFERRED')
        self.assertEqual((self.local / 'source.txt').read_text(), 'unfinished\n')

    def test_incremental_checkpoint_has_no_duplicate_commit(self):
        (self.local / 'new.txt').write_text('verified output\n')
        self.assertEqual(self.sync.checkpoint('first')['status'], 'SYNCED')
        first = self.sync.head
        result = self.sync.checkpoint('unchanged')
        self.assertEqual(result['status'], 'SYNCED')
        self.assertTrue(result['proof']['cached'])
        self.assertIsNone(result['created_commit'])
        self.assertEqual(first, self.sync.head)
        self.assertEqual(first, self.remote_head())

    def test_clean_divergence_merges_both_sides(self):
        self.peer_update()
        (self.local / 'local.txt').write_text('local result\n')
        result = self.sync.checkpoint('merge')
        self.assertEqual(result['status'], 'SYNCED')
        self.assertTrue((self.local / 'remote.txt').exists())
        self.assertTrue((self.local / 'local.txt').exists())
        self.assertEqual(self.sync.head, self.remote_head())

    def test_conflict_saves_branch_without_changing_remote_main(self):
        self.peer_update('source.txt', 'remote version\n')
        before = self.remote_head()
        (self.local / 'source.txt').write_text('local version\n')
        result = self.sync.checkpoint('conflict')
        self.assertEqual(result['status'], 'CONFLICT_SAVED_TO_BRANCH')
        self.assertEqual(before, self.remote_head())
        self.assertEqual(self.sync.head, self.remote_head(result['backup_branch']))
        self.assertEqual((self.local / 'source.txt').read_text(), 'local version\n')
        self.assertFalse((self.local / '.git/MERGE_HEAD').exists())
        self.assertEqual(self.sync.retry()['status'], 'CONFLICT_REQUIRES_RESOLUTION')

    def test_validation_failure_does_not_commit_or_push(self):
        before = self.sync.head
        self.sync.config['validation_commands'] = [[sys.executable, '-c', 'raise SystemExit(1)']]
        (self.local / 'unfinished.txt').write_text('bad\n')
        result = self.sync.checkpoint('failed')
        self.assertEqual(result['status'], 'VALIDATION_FAILED')
        self.assertEqual(before, self.sync.head)
        self.assertEqual(before, self.remote_head())
        self.assertTrue((self.local / 'unfinished.txt').exists())

    def disconnect(self):
        self.git(self.local, 'remote', 'set-url', 'origin', str(self.base / 'unavailable.git'))

    def reconnect(self):
        self.git(self.local, 'remote', 'set-url', 'origin', str(self.remote))

    def test_network_failure_keeps_commit_and_retry_recovers(self):
        self.disconnect()
        (self.local / 'saved.txt').write_text('must survive\n')
        result = self.sync.checkpoint('offline')
        self.assertEqual(result['status'], 'CHECKPOINT_PENDING')
        saved = self.sync.head
        self.assertNotEqual(saved, self.remote_head())
        self.reconnect()
        self.assertEqual(self.sync.retry()['status'], 'SYNCED')
        self.assertEqual(saved, self.remote_head())

    def test_retry_pushes_only_verified_commit_while_development_continues(self):
        self.disconnect()
        (self.local / 'saved.txt').write_text('verified\n')
        self.sync.checkpoint('offline')
        saved = self.sync.head
        (self.local / 'active.txt').write_text('not a completed phase\n')
        self.reconnect()
        result = self.sync.retry()
        self.assertEqual(result['status'], 'VERIFIED_COMMIT_PUSHED_WORKSPACE_RETAINED')
        self.assertEqual(saved, self.remote_head())
        self.assertIn('active.txt', self.sync.changed())
        self.assertEqual(self.git(self.local, 'ls-tree', '--name-only', saved, 'active.txt'), '')

    def test_long_lived_instance_reloads_pending_state(self):
        watcher = ProgressSync(self.local, self.config)
        self.disconnect()
        (self.local / 'saved.txt').write_text('verified\n')
        self.sync.checkpoint('offline')
        self.reconnect()
        self.assertEqual(watcher.retry()['status'], 'SYNCED')
        self.assertEqual(self.sync.head, self.remote_head())

    def test_parallel_worktrees_use_distinct_branches(self):
        first = self.sync.worktree('water')
        second = self.sync.worktree('buildings')
        self.assertNotEqual(first['branch'], second['branch'])
        self.assertEqual(self.git(Path(first['path']), 'branch', '--show-current'), 'codex/water')
        self.assertEqual(self.git(self.local, 'branch', '--show-current'), 'main')
        with self.assertRaises(SyncError):
            self.sync.worktree('water')

    def test_busy_lock_preserves_data_and_recovers(self):
        other = ProgressSync(self.local, self.config)
        with self.sync.lock():
            with self.assertRaises(SyncError):
                other.begin()
        self.assertEqual(other.begin()['status'], 'UP_TO_DATE')


if __name__ == '__main__':
    unittest.main()
