# 0008 — Geração validada antes de devolver ou cachear

Status: implementação da política de provedores já aprovada no ADR 0005.

Contexto: o mesmo JSON pode estar bem formado e conter um número financeiro falso.
Cache e fallback não podem contornar verificação nem ressuscitar conta excluída.
Opções: confiar na saída do modelo ou validar formato e semântica no chamador.
Escolha: Pydantic mais guardrail obrigatório; dinheiro por ID/centavos conferidos
contra SQL. Cache cifrado por usuário/pedido e nova validação no hit. Conta ativa
conferida antes e após rede; cache removido na exclusão recuperável.
Consequência: sem resposta validada, indisponibilidade explícita e apresentação
determinística pelo chamador. Não transmitir JSON parcial por streaming.

Adapters usam httpx existente, sem SDK ou gateway adicional. Dados pessoais
continuam bloqueados até revisão operacional. Provedores desativados por padrão,
modelo OpenRouter somente :free e sem expansão automática para planos pagos.
Circuitos locais por processo são suficientes para ensaio; antes de múltiplos
workers, centralizar limitação e coordenação conforme medições, sem fingir quota global.
