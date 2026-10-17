"""Exporta uma conta própria para revisão no importador; não importa no ledger."""

import argparse
import os
import tempfile
from datetime import date
from pathlib import Path
from uuid import uuid4

import httpx

from app.meu_pluggy import MeuPluggy, PluggyError

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "test-results" / "meu-pluggy"
VARIABLES = (
    "MEU_PLUGGY_CLIENT_ID",
    "MEU_PLUGGY_CLIENT_SECRET",
    "MEU_PLUGGY_ITEM_ID",
    "MEU_PLUGGY_ACCOUNT_ID",
)


def save_csv(content: bytes) -> None:
    if not OUTPUT.resolve().is_relative_to(ROOT):
        raise PluggyError("Diretório de saída não pode apontar para fora do projeto.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=OUTPUT, suffix=".tmp", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.link(temporary_path, OUTPUT / f"conta-{uuid4().hex}.csv")
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-personal-use", action="store_true")
    parser.add_argument("--from", dest="start", type=date.fromisoformat, required=True)
    parser.add_argument("--to", dest="end", type=date.fromisoformat, required=True)
    args = parser.parse_args(argv)
    if not args.confirm_personal_use:
        print("Não executado: use --confirm-personal-use somente para suas próprias contas.")
        return 2
    configuration = [os.environ.get(key, "").strip() for key in VARIABLES]
    if not all(configuration):
        print(
            "Configure as quatro variáveis MEU_PLUGGY_* descritas em docs/17-MEU-PLUGGY-PESSOAL.md."
        )
        return 1
    if (
        args.start > args.end
        or (args.end - args.start).days > 366
        or args.start == date.min
        or args.end == date.max
    ):
        print("Período inválido; use até 366 dias.")
        return 1
    try:
        with httpx.Client(trust_env=False) as client:
            service = MeuPluggy(client)
            accounts = service.accounts(*configuration[:3])
            selected = next((a for a in accounts if a["id"] == configuration[3]), None)
            if selected is None:
                raise PluggyError("Conta configurada não pertence ao item; nenhum arquivo criado.")
            print(f"Conta selecionada: {selected['type']} / BRL.")
            content, pending = service.export(selected, args.start, args.end)
            save_csv(content)
    except PluggyError as error:
        print(str(error))
        return 1
    except (ValueError, OSError, EOFError, KeyboardInterrupt):
        print(
            "Leitura/exportação não concluída; confira configuração, período, quota e permissões."
        )
        return 1
    print(f"CSV local em test-results/meu-pluggy. Pendentes excluídos: {pending}.")
    print("Arquivo financeiro em claro: revise no Tato antes de confirmar. Não abra em planilha.")
    print("Não misture fontes/períodos já importados; pagamento de fatura pode duplicar compras.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
