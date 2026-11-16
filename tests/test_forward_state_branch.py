from contextlib import contextmanager
import json,os,subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.forward_state_branch import restore,save,BRANCH


@contextmanager
def repository():
    with TemporaryDirectory() as td:
        root=Path(td);remote=root/'remote.git';repo=root/'repo'
        subprocess.run(['git','init','--bare','-q',str(remote)],check=True)
        subprocess.run(['git','init','-q',str(repo)],check=True)
        subprocess.run(['git','-C',str(repo),'remote','add','origin',str(remote)],check=True)
        previous=Path.cwd();os.chdir(repo)
        try:yield root,repo
        finally:os.chdir(previous)


def sha():
    return subprocess.check_output(['git','ls-remote','--heads','origin','refs/heads/'+BRANCH],text=True).split()[0]


def state(directory,value=1):
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'state.json').write_text(json.dumps(dict(version=1,protocol_sha256='test',counter=value)))


class ForwardStateBranchTests(unittest.TestCase):
    def test_isolated_round_trip_does_not_create_production_branches(self):
        with repository() as (root,repo):
            directory=root/'state';base=root/'base.json';restore(directory,base);state(directory);save(directory,base)
            other=root/'restored';restore(other,root/'other-base.json')
            self.assertEqual(json.loads((other/'state.json').read_text())['counter'],1)
            branches=subprocess.check_output(['git','ls-remote','--heads','origin'],text=True)
            self.assertIn('refs/heads/'+BRANCH,branches)
            self.assertNotIn('refs/heads/main',branches);self.assertNotIn('refs/heads/scanner-state',branches)

    def test_stale_writer_is_rejected_and_history_is_preserved(self):
        with repository() as (root,repo):
            a=root/'a';base=root/'a-base.json';restore(a,base);state(a);save(a,base);first=sha()
            b=root/'b';stale=root/'stale.json';restore(b,stale)
            state(a,2);save(a,base);second=sha();self.assertNotEqual(first,second)
            state(b,3)
            with self.assertRaises(AssertionError):save(b,stale)
            self.assertEqual(sha(),second)
            subprocess.run(['git','merge-base','--is-ancestor',first,second],check=True)

    def test_branch_override_cannot_write_live_state(self):
        with repository() as (root,repo):
            directory=root/'state';base=root/'base.json';restore(directory,base);state(directory)
            base.write_text(json.dumps(dict(branch='scanner-state',base=None)))
            with self.assertRaises(AssertionError):save(directory,base)
            self.assertFalse(subprocess.check_output(['git','ls-remote','--heads','origin'],text=True))

    def test_restore_never_overwrites_a_nonempty_directory(self):
        with repository() as (root,repo):
            directory=root/'state';state(directory)
            with self.assertRaises(ValueError):restore(directory,root/'base.json')

    def test_unexpected_files_are_not_published(self):
        with repository() as (root,repo):
            directory=root/'state';base=root/'base.json';restore(directory,base);state(directory)
            (directory/'unrelated.txt').write_text('not an allowed research artifact')
            with self.assertRaises(AssertionError):save(directory,base)
            self.assertFalse(subprocess.check_output(['git','ls-remote','--heads','origin'],text=True))
