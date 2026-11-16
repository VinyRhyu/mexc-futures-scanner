from contextlib import ExitStack, redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.run_round import run


class RoundObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.original = Path.cwd()
        self.temp = tempfile.TemporaryDirectory()
        os.chdir(self.temp.name)
        Path('.scanner-state').mkdir()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(os.chdir, self.original)

    def exercise(self, *, complete=True, save_error=False, notify_code=0):
        calls, output = [], io.StringIO()
        def cli(args):
            calls.append(args[0])
            if args[0] == 'scan' and complete:
                Path('.scanner-state/round-complete.marker').write_text('1')
            return notify_code if args[0] == 'notify' else 0
        def persist(_):
            calls.append('save')
            if save_error:
                raise RuntimeError('state conflict')
        with ExitStack() as stack:
            stack.enter_context(patch('scripts.run_round.restore', side_effect=lambda _: calls.append('restore')))
            stack.enter_context(patch('scripts.run_round.main', side_effect=cli))
            stack.enter_context(patch('scripts.run_round.save', side_effect=persist))
            stack.enter_context(patch('scripts.run_round.process_commands', return_value=0))
            stack.enter_context(redirect_stdout(output))
            try:
                result = run(50)
            except RuntimeError as exc:
                result = str(exc)
        rows = [json.loads(line) for line in output.getvalue().splitlines() if line.startswith('{')]
        return calls, rows, result

    def test_persists_before_delivery_and_records_distinct_phases(self):
        calls, rows, result = self.exercise()
        self.assertEqual(result, 0)
        self.assertEqual(calls, ['restore', 'scan', 'save', 'notify', 'save', 'save'])
        ends = [row['phase'] for row in rows if row['event'] == 'end']
        self.assertEqual(ends, ['restore', 'scan', 'persist_before_notify', 'notify',
            'persist_after_notify', 'telegram_commands', 'persist_after_commands', 'round'])

    def test_incomplete_scan_cannot_deliver_and_round_failure_is_measured(self):
        calls, rows, result = self.exercise(complete=False)
        self.assertNotIn('notify', calls)
        self.assertNotIn('save', calls)
        self.assertEqual(rows[-1]['status'], 'ERROR')

    def test_stale_writer_cannot_deliver_and_exception_survives(self):
        calls, rows, result = self.exercise(save_error=True)
        self.assertEqual(result, 'state conflict')
        self.assertNotIn('notify', calls)
        self.assertEqual(rows[-1]['status'], 'ERROR')

    def test_delivery_error_code_survives_without_skipping_persistence(self):
        calls, rows, result = self.exercise(notify_code=1)
        self.assertEqual(result, 1)
        self.assertEqual(calls.count('save'), 3)
