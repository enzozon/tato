import { createClient } from '@supabase/supabase-js';

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
export const auth = url && key ? createClient(url, key, {
  auth: { persistSession: false, detectSessionInUrl: true },
}) : null;
export const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function request<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, {
    ...init, cache: 'no-store', credentials: 'omit',
    headers: { ...(init.body instanceof FormData ? {} : {'Content-Type': 'application/json'}),
      ...init.headers, Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const messages: Record<number, string> = {
      401: 'Sua sessão expirou. Entre novamente.', 403: 'O limite do seu plano foi atingido.',
      409: 'Esta operação não está disponível no estado atual da conta.',
      413: 'O arquivo deve ter no máximo 2 MiB.',
      422: 'Confira os dados e o formato do arquivo.', 429: 'Aguarde um momento antes de tentar novamente.',
    };
    throw new Error(messages[response.status] || 'Serviço indisponível. Tente novamente em instantes.');
  }
  return response.status === 204 ? undefined as T : response.json();
}
export function money(value: string | number) {
  if (typeof value === 'number' && !Number.isSafeInteger(value)) return 'Valor fora do limite de exibição';
  const cents = BigInt(value), absolute = cents < 0n ? -cents : cents;
  return `${cents < 0n ? '−' : ''}R$ ${(absolute / 100n).toLocaleString('pt-BR')},${String(absolute % 100n).padStart(2, '0')}`;
}
export function cents(text: string): number {
  if (!/^-?\d+(,\d{1,2})?$/.test(text)) throw new Error('Use reais com vírgula, sem separador de milhar.');
  const [whole, fraction = ''] = text.replace('-', '').split(',');
  const result = (BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'))) * (text.startsWith('-') ? -1n : 1n);
  if (result > BigInt(Number.MAX_SAFE_INTEGER) || result < BigInt(Number.MIN_SAFE_INTEGER)) throw new Error('Valor acima do limite de entrada.');
  return Number(result);
}
export type Account = { id: string; name: string; kind: string; opening_date: string; balance_cents: string };
export type Summary = { accounts: Account[]; balance_cents: string; expense_cents: string; as_of: string;
  projected_balance_cents?: string | null;
  categories: { name: string; amount_cents: string }[] };
export type Profile = { onboarding_completed: boolean; plan: { name: string; agents: number; messages_per_month: number | null } };
