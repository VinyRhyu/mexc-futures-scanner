"""Fast-forward persistence exclusively for the isolated public paper journal."""
import argparse,json,os,subprocess,tempfile
from pathlib import Path,PurePosixPath

BRANCH='research/momentum-forward-state-v1'


def git(*args,input=None,env=None):
    r=subprocess.run(['git',*args],input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    if r.returncode:raise RuntimeError('Forward-state git '+args[0]+' failed; no force push or fallback branch')
    return r.stdout


def allowed(name):
    p=PurePosixPath(name)
    return (not p.is_absolute() and '..' not in p.parts and not any(x.startswith('.') for x in p.parts)
        and p.suffix in ('.json','.jsonl','.md','.gz'))


def restore(directory,base_file):
    root=Path(directory);base=Path(base_file)
    if root.exists() and any(root.iterdir()):raise ValueError('Restore requires a fresh isolated directory')
    root.mkdir(parents=True,exist_ok=True)
    line=git('ls-remote','--heads','origin','refs/heads/'+BRANCH).decode().strip()
    sha=line.split()[0] if line else None
    if sha:
        git('fetch','--depth','1','--no-tags','origin','refs/heads/'+BRANCH)
        assert git('rev-parse','FETCH_HEAD').decode().strip()==sha,'Forward state changed while restoring'
        names=git('ls-tree','-r','--name-only','-z',sha).split(b'\0')
        for raw in names:
            if not raw:continue
            name=raw.decode();assert allowed(name),'Unexpected isolated-state path'
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(git('show',sha+':'+name))
        assert (root/'state.json').is_file(),'Existing forward state lacks state.json; never initialize over it'
    base.parent.mkdir(parents=True,exist_ok=True);base.write_text(json.dumps(dict(branch=BRANCH,base=sha)))
    print(json.dumps(dict(action='restore_forward_state',existing=bool(sha))))


def save(directory,base_file):
    root=Path(directory);base=Path(base_file);record=json.loads(base.read_text())
    assert record['branch']==BRANCH and (root/'state.json').is_file()
    state=json.loads((root/'state.json').read_text())
    assert state.get('version')==1 and state.get('protocol_sha256')
    line=git('ls-remote','--heads','origin','refs/heads/'+BRANCH).decode().strip()
    current=line.split()[0] if line else None
    assert current==record['base'],'Stale forward-state writer; do not overwrite'
    identity=dict(os.environ,GIT_AUTHOR_NAME='github-actions[bot]',GIT_COMMITTER_NAME='github-actions[bot]',
        GIT_AUTHOR_EMAIL='github-actions[bot]@users.noreply.github.com',GIT_COMMITTER_EMAIL='github-actions[bot]@users.noreply.github.com')
    with tempfile.TemporaryDirectory() as tmp:
        identity['GIT_INDEX_FILE']=str(Path(tmp)/'index');git('read-tree','--empty',env=identity)
        for path in sorted(root.rglob('*')):
            if not path.is_file():continue
            name=path.relative_to(root).as_posix()
            assert not path.is_symlink() and allowed(name),'Unsafe isolated-state member'
            assert path.stat().st_size<25_000_000
            blob=git('hash-object','-w','--stdin',input=path.read_bytes()).decode().strip()
            git('update-index','--add','--cacheinfo','100644,'+blob+','+name,env=identity)
        tree=git('write-tree',env=identity).decode().strip()
        if current and git('rev-parse',current+'^{tree}').decode().strip()==tree:
            print(json.dumps(dict(action='save_forward_state',changed=False)));return
        args=['commit-tree',tree]+(['-p',current] if current else [])
        sha=git(*args,input=b'Persist prospective paper observations\n',env=identity).decode().strip()
        git('push','origin',sha+':refs/heads/'+BRANCH)
        base.write_text(json.dumps(dict(branch=BRANCH,base=sha)))
        print(json.dumps(dict(action='save_forward_state',changed=True,commit=sha)))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['restore','save'])
    ap.add_argument('--directory',required=True);ap.add_argument('--base-file',required=True);a=ap.parse_args()
    (restore if a.action=='restore' else save)(a.directory,a.base_file)
