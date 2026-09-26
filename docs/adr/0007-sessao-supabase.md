# 0007 — Validar sessão no servidor de autenticação

Contexto: a API precisa obter o UUID de uma identidade verificada, sem confiar em
headers de usuário, metadados editáveis ou JWT apenas decodificado.

Escolha: consultar `/auth/v1/user` do Supabase com bearer em cada requisição
protegida. Cadastro, login por e-mail/Google e renovação pertencem ao Supabase;
a interface será conectada na etapa 9. Não armazenamos senha ou refresh token.

Alternativa: validar assinatura com JWKS localmente. Reduz latência, mas exige
cuidados extras com revogação e usuários removidos. Nesta etapa priorizamos a
consulta remota, sem cache de identidade. Falha do provedor fecha o acesso (503).

`httpx` passa de dependência de teste a execução: substitui SDKs adicionais para
duas integrações HTTP pequenas. HTTPS é obrigatório fora de localhost.

Referência consultada em 23/09/2026:
[getUser](https://supabase.com/docs/reference/python/auth-getuser).
