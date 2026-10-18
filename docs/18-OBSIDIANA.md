# Obsidiana — identidade e interação

Enzo escolheu a proposta A em 17/10/2026, pedindo mais personalidade e interação.
O objetivo é reconhecer o Tato antes de ler seu nome, sem transformar informação
financeira em decoração. O usuário deve conseguir importar, conferir e perguntar
com o mesmo vocabulário visual em todas as telas.

## Plano e fronteiras

1. Consolidar paleta, superfícies, tipografia e movimento no pacote de identidade.
2. Aplicar o sistema ao site, navegação, autenticação e ferramentas existentes.
3. Conferir estados, acessibilidade e fluxos com dados sintéticos no navegador.
4. Registrar limitações, capturas e validações antes de integrar a mudança.

Esta etapa não altera schema, provedores, cálculo financeiro ou cobrança.
Os protótipos anteriores são referências; nenhuma funcionalidade fictícia deles
deve passar para o produto. “Últimos lançamentos”, por exemplo, depende de uma
consulta detalhada ainda não implementada.

## Identidade

Grafite cria profundidade; menta identifica a ação principal; cobre conecta o
produto ao casco autoral do tatu. Superfícies próximas evitam o contraste duro
de cartões brancos em fundo preto. Bordas de campos precisam continuar visíveis.
Nome, SVG, paleta e estados do mascote permanecem em `packages/mascot/`.

Tipografia sem serifa privilegia a leitura diária. Títulos de ferramentas são
menores que o hero; cifras usam números tabulares. O espaço entre botões e campos
vem de grupos compartilhados, sem depender de espaços no texto ou margens soltas.

## Movimento com propósito

- Hover e pressão confirmam que botões respondem; foco oferece orientação igual
  para quem usa teclado. Controles desabilitados não fingem disponibilidade.
- Entradas curtas ajudam a perceber mudanças de contexto. Não bloquear ações
  até uma animação terminar, nem esconder conteúdo se JavaScript falhar.
- Respiração e piscada dão presença ao Tato. Atenção indica processamento;
  humor financeiro vem do estado validado, nunca de uma animação de sucesso.
- `prefers-reduced-motion` interrompe animações e transições desnecessárias.
  Não há biblioteca de animação nem chamadas externas para produzir efeitos.

## Revisão por superfície

| Superfície | Prioridade |
| --- | --- |
| Landing | Identidade e conversa visíveis, CTA concreto, limitações honestas. |
| Login/recuperação | Campos legíveis, ações separadas e feedback próximo do erro. |
| Navegação | Tela ativa reconhecível e menu móvel utilizável por teclado. |
| Conversa | Compositor familiar, fontes, espera, erro e confirmação preservados. |
| Resumo | Saldo calculado e hipóteses da projeção claros, sem gráficos inventados. |
| Importação | Conta, mapeamento e prévia antes de qualquer gravação. |
| Agentes | Configuração, estado, limites e opt-in de e-mail distinguíveis. |
| Conta/cobrança | Exportação, exclusão e sandbox sem competição visual. |
| PWA/offline | Moldura escura e orientação genérica, sem cache financeiro. |

## Como avaliar

Conferir desktop, celular e largura de 320px; rótulos longos; navegação por Tab;
contraste; alvos de toque; movimento reduzido; mensagens vazias, de espera, erro,
resultado parcial e acesso negado. Mock de API comprova comportamento visual,
nunca uma conexão real. Não usar extratos pessoais ou credenciais nas capturas.

Depois da revisão automatizada, a avaliação do Enzo deve priorizar uso repetido:
é fácil encontrar o botão principal? A fonte do valor é clara? A animação ajuda
a perceber o estado sem cansar? Os formulários permanecem confortáveis no celular?

## Próximas melhorias de produto

O visual não resolve a falta de edição/exclusão detalhada de lançamentos,
reconciliação de transferências/faturas, novas ferramentas SQL ou publicação.
Essas partes seguem o inventário em `13-CONCLUSAO.md` e precisam de implementação
e prova próprias. Validar Safari e aparelhos físicos após esta revisão local.

A rodada de acabamento aplica os refinamentos da primeira revisão: importação
em duas colunas no desktop, rótulo/valor alinhados em avisos e configurações e
cenários autorais para onboarding e estados vazios. No celular, campos e valores
voltam a uma coluna. Barras proporcionais de categorias continuam como evolução
possível, usando somente valores SQL; não acrescentar métricas fictícias.

O parâmetro opcional `scene` de `Mascot` acrescenta órbitas, folhas geométricas e
detalhes de cobre/menta atrás do tatu. A decoração não muda o humor nem o nome
acessível e respeita movimento reduzido. Login, recuperação, onboarding e telas
sem contas/agentes usam o cenário; o chat conserva seu halo para evitar duplicação.
No Resumo vazio, os cartões de métricas aguardam a primeira conta: a ação inicial
fica visível antes da rolagem no celular. Um único Tato preserva o humor derivado
dos dados. “Adicionar minha primeira conta” abre o formulário e foca Nome,
inclusive se ele tiver sido recolhido. Botões ganham borda iluminada e feedback
curto, preservando a distinção de ações destrutivas e desabilitadas.

## Validação local de 18/10/2026

Suíte funcional: 134 testes aprovados. Após corrigir a largura do botão de anexo,
10 testes focados também passaram. Galeria: 30 estados em 1440×1000, 390×844 e
320×844, totalizando 90 capturas com verificação de overflow e alvos de 44px.
Há cenários de processamento, erro, sucesso, vazio, HTTP503 parcial e HTTP403.
`npm run build`, `npm run check:web` e o teste PWA de manifesto/cache/offline
passaram. `make check`: 657 testes, cobertura de 83,94%; os testes Postgres/RLS
não foram repetidos localmente nesta alteração visual.

Reproduzir: `npm run gallery --workspace=tato-web`; se a porta 3000 estiver em uso,
definir `PLAYWRIGHT_PORT=3100` no ambiente do comando. As imagens e o índice ficam
em `test-results/ui-gallery/`, com dados sintéticos. A preferência de movimento
reduzido foi testada; Safari físico e leitor de tela completo continuam pendentes.

Na rodada de acabamento, a suíte completa aprovou 136 testes antes do último
ajuste de hierarquia. Depois dele, quatro testes focados aprovaram cenário,
movimento reduzido, humor e abertura/foco do cadastro; a ação inicial cabe em
844px de altura também na largura de 320px. A galeria final manteve 90 capturas,
com nove imagens adicionais de Resumo, Importar e Agentes sem dados. Dois
revisores avaliaram espaçamento e hierarquia nas capturas sintéticas.
Build, tipos, teste PWA offline e verificador das evidências passaram novamente
após o ajuste final. `make check` manteve 657 testes e 83,94% de cobertura.
