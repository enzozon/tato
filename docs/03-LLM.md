# Camada LLM — etapa 5

Plano: contratos → adapters HTTP → fallback/retry/circuit breaker → cache por
usuário → testes e documentação. Branch baseada na etapa 4 enquanto PR 8 está aberto.
Sem schema novo, SDK adicional ou transmissão automática de dados reais.

Um token é um pedaço de texto usado pelo modelo, não necessariamente uma palavra.
Contamos entrada e saída informadas pelo provedor; ausência de medição não vira zero
inventado. Limites de caracteres na entrada e tokens na saída limitam cada pedido.
Temperatura zero reduz variação, mas não garante verdade nem determinismo completo.

`Generation` separa instrução confiável e dado não confiável. Classificação padrão
é pessoal; o chamador precisa declarar explicitamente material sintético/público.
`Completion` contém texto e contagens; representações não incluem conteúdo privado.
Pydantic garante formato, não veracidade: `verify_money` compara ID/centavos com
fatos obtidos pelo chamador do SQL. Respostas monetárias livres não são aceitas
por esse contrato; o código deve renderizar os valores verificados.

Groq → Gemini → OpenRouter continua sendo a ordem aprovada no ADR 0005.
Gemini gratuito nunca recebe dados pessoais. Inicialmente nenhuma chamada pessoal
é habilitada, pois a revisão operacional de privacidade dos provedores está pendente.

Referências consultadas em 27/09/2026: [Groq structured outputs](https://console.groq.com/docs/structured-outputs),
[Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output),
[limites OpenRouter](https://openrouter.ai/docs/api_reference/limits).
JSON estruturado e streaming/tool calling não são combinados nesta implementação;
SSE para o produto pertence à etapa 7 e não deve transmitir JSON parcial não validado.
