# 0001 — Backend Python verificável

Status: aceito por Enzo em 19/09/2026.

Contexto: aprender em uma stack familiar com custo e histórico controlados.
Opções: Flask/gerenciamento manual ou FastAPI/Pydantic com uv.
Escolha: Python 3.12, FastAPI e Pydantic v2, um ambiente uv na raiz.
Consequência: validação tipada e OpenAPI reais desde o health; nenhuma camada
de domínio vazia. Ruff, mypy estrito, pytest, pytest-cov e httpx tornam o contrato
verificável. Uvicorn serve ASGI. Cada dependência substitui infraestrutura manual.

SQLModel/Alembic entram na etapa 2; schema público pode divergir da tabela.
