"""Cliente do cron: configuração privada no ambiente, somente totais na saída."""

import json
import os
import sys
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirecionamento recusado.")


def run():
    base = os.environ["TATO_API_URL"].rstrip("/")
    url = urlsplit(base)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValueError("URL inválida.")
    token = os.environ["AGENTS_RUN_TOKEN"]
    if len(token) < 32:
        raise ValueError("Token ausente.")
    users = json.loads(os.environ["AGENT_USER_IDS"])
    if not isinstance(users, list) or not 1 <= len(users) <= 25:
        raise ValueError("Lote inválido.")
    users = list(dict.fromkeys(str(UUID(item)) for item in users))
    request = Request(
        f"{base}/internal/agents/run",
        data=json.dumps({"user_ids": users}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with build_opener(NoRedirect()).open(request, timeout=240) as response:
        result = json.loads(response.read(4096))
    counts = {name: result[name] for name in ("processed", "inserted", "sent")}
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError("Resposta inválida.")
    if counts["processed"] != len(users):
        raise ValueError("Lote incompleto.")
    return counts


if __name__ == "__main__":
    try:
        print(json.dumps(run()))
    except (KeyError, ValueError, TypeError, AttributeError, URLError, OSError):
        print("Execução indisponível; confira configuração e serviço sem expor segredos.")
        sys.exit(1)
