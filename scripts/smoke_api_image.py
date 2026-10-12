"""Valida a imagem local sem credenciais, portas publicadas ou rede externa."""

import subprocess
import sys

PROBE = """
import json, os, pathlib, shutil, time, urllib.error, urllib.request
assert os.getuid() == 1000
assert os.environ['PORT'] == '8765'
for _ in range(30):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=1) as response:
            assert response.status == 200 and json.load(response) == {'status': 'ok'}
        break
    except OSError:
        time.sleep(0.5)
else:
    raise AssertionError('API nao iniciou')
try:
    urllib.request.urlopen('http://127.0.0.1:8765/ready', timeout=1)
except urllib.error.HTTPError as error:
    assert error.code == 503
else:
    raise AssertionError('Prontidao sem banco nao pode ser aprovada')
root = pathlib.Path('/app')
assert not list(root.rglob('.env*'))
assert not (root / 'extratos_exemplo').exists()
assert not (root / 'models').exists()
assert shutil.which('uv') is None and shutil.which('pytest') is None
from app.mascot import identity
assert identity()['name'] == 'Tato'
print('Health 200; readiness 503 sem banco; UID 1000; PORT configuravel; sem segredos')
"""


def main() -> None:
    image = sys.argv[1] if len(sys.argv) == 2 else "tato-api:local"
    container = subprocess.check_output(
        [
            "docker",
            "run",
            "-d",
            "--network",
            "none",
            "--memory",
            "512m",
            "--cpus",
            "2",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--tmpfs",
            "/home/tato:rw,noexec,nosuid,size=64m,uid=1000,gid=1000",
            "-e",
            "PORT=8765",
            image,
        ],
        text=True,
    ).strip()
    try:
        subprocess.run(
            ["docker", "exec", "-i", container, "python", "-"],
            input=PROBE,
            text=True,
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container],
            check=True,
            timeout=10,
        )
    finally:
        subprocess.run(["docker", "rm", "-f", container], check=True, timeout=10)


if __name__ == "__main__":
    main()
