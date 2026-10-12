# Empacotamento e deploy

## Estado em 12/10/2026

Existe uma imagem local da API e um ensaio reproduzível sem serviços externos.
Nenhum deploy, provisionamento ou escolha de hospedagem foi realizado. O destino
continua sujeito ao checkpoint de custo, retenção de dados e recursos disponíveis.

## Imagem local

O `apps/api/Dockerfile` usa dois estágios: uv instala o lockfile no primeiro;
o segundo recebe somente o ambiente Python, código da API e identidade pública
do mascote. Python 3.12 slim usa glibc para aproveitar os wheels existentes de
ONNX/psycopg. Python e uv estão fixados por digest, e a versão uv acompanha o CI.
Não há dependência nova nem uv, pytest ou compilador na imagem final.

A `.dockerignore` começa negando todos os arquivos e permite somente o necessário.
`.env`, backups, extratos, Git, frontend, testes e caches/modelos locais ficam fora
do contexto. O Dockerfile também usa cópias explícitas, sem `COPY . .`.

```powershell
docker build -f apps/api/Dockerfile -t tato-api:local .
python scripts/smoke_api_image.py tato-api:local
```

O ensaio cria um contêiner descartável com rede `none`, sem segredos, sem portas
publicadas, raiz somente leitura, 2 CPUs e limite de 512 MiB. Consulta `/health`
por loopback, confere UID 1000, porta configurada, identidade do mascote e ausência
de arquivos privados/ferramentas de build. `/ready` deve responder 503 sem banco
configurado: processo vivo não implica prontidão operacional. Remove o contêiner
mesmo após falha.

Para inspecionar a API no navegador local, sem configurar provedores:

```powershell
docker run --rm -p 127.0.0.1:7860:7860 tato-api:local
```

`PORT` aceita outra porta; o padrão é 7860. Um único processo uvicorn evita
duplicar memória dos modelos. Access logs estão desligados para não registrar
URLs de webhook com segredos. Segredos operacionais serão injetados apenas pelo
ambiente do destino aprovado, nunca por argumentos de build ou camadas.

## Medição e limites da prova

Build e smoke locais aprovados em Docker Desktop 29.8.0, Linux amd64, com código
da API na base `4964988`. Imagem: 529.623.254 bytes (aproximadamente 505 MiB).
Uma cópia diagnóstica do contexto confirmou somente os 71 arquivos permitidos
pela lista, sem extratos, frontend ou testes do repositório.
Uma amostra ociosa após início na base atual: 106 MiB, limite de 512 MiB,
`OOMKilled=false`. Porta alternativa 8765 respondeu HTTP 200, usando UID 1000,
sem rede externa e com sistema de arquivos somente leitura. `/ready` respondeu
503 por falta de banco, como esperado; a imagem não foi considerada pronta para
operações financeiras a partir do HTTP 200 de `/health`.

Essa memória é uma amostra de liveness, não pico nem teste de carga. `/health`
confirma processo HTTP; não testa banco, Supabase, Redis, LLM ou RAG. Os modelos
não estão embutidos nem foram baixados nesse ensaio; inferência real, cache
gravável, cold start e pico de RAM precisam de medição antes de escolher host.
Não se pode concluir que 512 MiB suportam o produto apenas desse resultado.

## Verificações de segurança e CI

O CI adiciona jobs separados de imagem e segurança, sem secrets de aplicação.
O primeiro constrói o Dockerfile e executa o mesmo smoke isolado acima. O segundo
exporta somente dependências de runtime travadas com hashes e usa pip-audit
2.10.1 efêmero, sem instalar a ferramenta no ambiente da API. Falha em auditoria
ou coleta de dependências não é convertida em aprovação.

Auditorias locais em 12/10: 53 dependências Windows e 50 Linux, ambas com zero
vulnerabilidades conhecidas e exit 0. A execução Linux usou o estágio de
dependências da imagem, sem segredos; o job remoto no CI ainda é prova separada.
O resultado consulta avisos conhecidos do PyPI; não prova ausência de bugs,
vulnerabilidades desconhecidas ou falhas da imagem base Debian.

Gitleaks CLI 8.30.1 usa licença MIT, sem action paga ou chave de licença. O CI
baixa o binário oficial Linux x64 e verifica SHA-256 literal antes de executar.
Checkout completo permite verificar o histórico; `--redact=100`, sem modo
verbose, evita expor correspondências. Ensaio local no histórico de todas as
refs: exit 0, zero achados. Arquivos ignorados de trabalho não são alvo desse
modo Git; o ensaio não leu `.env` ou extratos locais.

Migrations continuam sendo uma operação administrativa separada; não rodam
automaticamente ao iniciar a imagem. Credenciais administrativas não devem ser
entregues ao processo da API. Publicação, smoke autenticado pós-deploy, rollback
e coleta de quotas permanecem pendentes do destino aprovado e da etapa 10.

## Referências

- [Docker: build em múltiplos estágios](https://docs.docker.com/build/building/multi-stage/).
- [Docker: contexto e dockerignore](https://docs.docker.com/build/concepts/context/#dockerignore-files).
- [Astral: uv em Docker, fonte oficial](https://github.com/astral-sh/uv/blob/main/docs/guides/integration/docker.md).
- [PyPA: pip-audit](https://pypi.org/project/pip-audit/).
- [Gitleaks: release oficial 8.30.1](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1).
- [Gitleaks: licença MIT](https://github.com/gitleaks/gitleaks/blob/master/LICENSE).
