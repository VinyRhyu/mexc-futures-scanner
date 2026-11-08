"""Persistência serializada em uma branch exclusiva; nunca usa force-push."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile


BRANCH = "scanner-state"
BASE_FILE = Path(".state-base")


def git(*args, input=None, env=None, check=True):
    result = subprocess.run(["git", *args], input=input, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env)
    if check and result.returncode:
        raise RuntimeError("Git falhou em " + args[0] + "; verificar o log de execução sem divulgar credenciais")
    return result


def restore(directory: Path):
    remote = git("ls-remote", "--heads", "origin", f"refs/heads/{BRANCH}")
    lines = remote.stdout.decode().strip().splitlines()
    base = None
    if lines:
        base = lines[0].split()[0]
        git("fetch", "--no-tags", "origin", f"refs/heads/{BRANCH}")
        actual = git("rev-parse", "FETCH_HEAD").stdout.decode().strip()
        if actual != base:
            raise RuntimeError("Estado mudou durante a recuperação; executar novamente")
        listing = git("ls-tree", "-r", "--name-only", "-z", base).stdout.split(b"\0")
        for name in listing:
            if not name:
                continue
            rel = name.decode()
            path = PurePosixPath(rel)
            if path.is_absolute() or ".." in path.parts or any(part.startswith(".") for part in path.parts):
                raise RuntimeError("Caminho não permitido na branch de estado")
            if path.suffix not in {".json", ".jsonl", ".md"}:
                raise RuntimeError("Tipo não permitido na branch de estado")
            target = directory / str(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git("show", f"{base}:{rel}").stdout)
        if not (directory / "state.json").is_file():
            raise RuntimeError("Branch de estado existente sem state.json; não reinicializar")
    directory.mkdir(parents=True, exist_ok=True)
    BASE_FILE.write_text(json.dumps({"base": base}))
    if not base:
        (directory / "new-state.marker").write_text("bootstrap-paper-only\n")
    print(json.dumps({"action": "restore", "existing": bool(base)}))


def save(directory: Path):
    if not BASE_FILE.exists() or not (directory / "state.json").exists():
        raise RuntimeError("Estado/base ausente; restaurar e validar antes de salvar")
    base = json.loads(BASE_FILE.read_text())["base"]
    remote = git("ls-remote", "--heads", "origin", f"refs/heads/{BRANCH}").stdout.decode().strip()
    current = remote.split()[0] if remote else None
    if current != base:
        raise RuntimeError("Estado remoto mudou; não sobrescrever nem notificar a partir de estado antigo")
    # Confirmar leitura JSON antes de publicar qualquer snapshot de estado.
    json.loads((directory / "state.json").read_text())
    identity = os.environ.copy()
    identity.update({"GIT_AUTHOR_NAME": "github-actions[bot]", "GIT_COMMITTER_NAME": "github-actions[bot]",
        "GIT_AUTHOR_EMAIL": "github-actions[bot]@users.noreply.github.com",
        "GIT_COMMITTER_EMAIL": "github-actions[bot]@users.noreply.github.com"})
    with tempfile.TemporaryDirectory() as temp:
        identity["GIT_INDEX_FILE"] = str(Path(temp) / "index")
        git("read-tree", "--empty", env=identity)
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(directory)
            if rel.as_posix().endswith("snapshot.json"):
                # Capturas de candles são temporárias; evitar regravar MB a cada 15 min.
                continue
            if any(part.startswith(".") for part in rel.parts) or path.suffix not in {".json", ".jsonl", ".md"}:
                continue
            if path.stat().st_size > 25_000_000:
                raise RuntimeError("Arquivo de estado excede 25 MB; arquivar antes de prosseguir")
            blob = git("hash-object", "-w", "--stdin", input=path.read_bytes()).stdout.decode().strip()
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{rel.as_posix()}", env=identity)
        tree = git("write-tree", env=identity).stdout.decode().strip()
        if base:
            previous_tree = git("rev-parse", f"{base}^{{tree}}").stdout.decode().strip()
            if previous_tree == tree:
                print(json.dumps({"action": "save", "changed": False}))
                return
        args = ["commit-tree", tree]
        if base:
            args += ["-p", base]
        commit = git(*args, input=b"Persist scanner state\n", env=identity).stdout.decode().strip()
        # Push normal exige avanço de histórico: uma gravação concorrente provoca falha.
        git("push", "origin", f"{commit}:refs/heads/{BRANCH}")
        BASE_FILE.write_text(json.dumps({"base": commit}))
        print(json.dumps({"action": "save", "changed": True, "commit": commit}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["restore", "save"])
    parser.add_argument("--directory", default=".scanner-state")
    args = parser.parse_args()
    (restore if args.action == "restore" else save)(Path(args.directory))
