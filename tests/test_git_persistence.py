import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from mexc_scanner.config import Config
from mexc_scanner.state import atomic_json, initial_state
from scripts.state_branch import restore, save


def cmd(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class GitPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.original = Path.cwd()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.remote, self.work = self.root / "remote.git", self.root / "work"
        cmd("git", "init", "--bare", "-q", str(self.remote))
        cmd("git", "clone", "-q", str(self.remote), str(self.work))
        os.chdir(self.work)
        cmd("git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "base")
        cmd("git", "branch", "-M", "main")
        cmd("git", "push", "-q", "origin", "main")

    def tearDown(self):
        os.chdir(self.original)
        self.temp.cleanup()

    def test_state_survives_new_checkout_without_using_cache(self):
        directory = Path(".scanner-state")
        restore(directory)
        state = initial_state(Config())
        state["wallet"]["balance"] = "0.70"
        atomic_json(directory / "state.json", state)
        save(directory)
        other = self.root / "other"
        cmd("git", "clone", "-q", "--branch", "main", str(self.remote), str(other))
        os.chdir(other)
        restore(Path(".scanner-state"))
        restored = json.loads(Path(".scanner-state/state.json").read_text())
        self.assertEqual(restored["wallet"]["balance"], "0.70")

    def test_stale_writer_cannot_overwrite_new_state(self):
        directory = Path(".scanner-state")
        restore(directory)
        atomic_json(directory / "state.json", initial_state(Config()))
        save(directory)
        other = self.root / "other"
        cmd("git", "clone", "-q", "--branch", "main", str(self.remote), str(other))
        os.chdir(other)
        restore(Path(".scanner-state"))
        newer = initial_state(Config())
        newer["wallet"]["balance"] = "0.80"
        atomic_json(Path(".scanner-state/state.json"), newer)
        save(Path(".scanner-state"))
        os.chdir(self.work)
        older = initial_state(Config())
        older["wallet"]["balance"] = "0.90"
        atomic_json(directory / "state.json", older)
        with self.assertRaises(RuntimeError):
            save(directory)

    def test_shallow_restore_fetches_current_snapshot_and_preserves_remote_ancestry(self):
        directory = Path('.scanner-state')
        restore(directory)
        state = initial_state(Config())
        for balance in ('1', '0.9', '0.8'):
            state['wallet']['balance'] = balance
            atomic_json(directory / 'state.json', state)
            save(directory)
        previous = subprocess.check_output(['git', '--git-dir', str(self.remote),
            'rev-parse', 'scanner-state'], text=True).strip()
        remote_count = int(subprocess.check_output(['git', '--git-dir', str(self.remote),
            'rev-list', '--count', 'scanner-state'], text=True))
        fresh = self.root / 'fresh'
        cmd('git', 'init', '-q', str(fresh))
        os.chdir(fresh)
        cmd('git', 'remote', 'add', 'origin', str(self.remote))
        restore(directory)
        local_count = int(subprocess.check_output(['git', 'rev-list', '--count', previous], text=True))
        self.assertEqual(local_count, 1)
        self.assertEqual(remote_count, 3)
        restored = json.loads((directory / 'state.json').read_text())
        self.assertEqual(restored['wallet']['balance'], '0.8')
        restored['wallet']['balance'] = '0.7'
        atomic_json(directory / 'state.json', restored)
        save(directory)
        parent = subprocess.check_output(['git', '--git-dir', str(self.remote),
            'rev-parse', 'scanner-state^'], text=True).strip()
        self.assertEqual(parent, previous)
        new_count = int(subprocess.check_output(['git', '--git-dir', str(self.remote),
            'rev-list', '--count', 'scanner-state'], text=True))
        self.assertEqual(new_count, remote_count + 1)

    def test_decision_ledger_survives_restore_and_appends_without_overwriting(self):
        directory = Path('.scanner-state')
        restore(directory)
        atomic_json(directory / 'state.json', initial_state(Config()))
        audit = directory / 'audit' / 'decisions-2026-11-16.jsonl'
        audit.parent.mkdir()
        first = '{"event":"financial_evaluation","status":"BLOQUEADA"}\n'
        audit.write_text(first)
        save(directory)
        other = self.root / 'ledger-fresh'
        cmd('git', 'init', '-q', str(other))
        os.chdir(other)
        cmd('git', 'remote', 'add', 'origin', str(self.remote))
        restore(directory)
        self.assertEqual(audit.read_text(), first)
        with audit.open('a') as stream:
            stream.write('{"event":"delivery_sent"}\n')
        save(directory)
        remote_ledger = subprocess.check_output(['git', '--git-dir', str(self.remote),
            'show', 'scanner-state:audit/decisions-2026-11-16.jsonl'], text=True)
        self.assertTrue(remote_ledger.startswith(first))
        self.assertEqual(len(remote_ledger.splitlines()), 2)
