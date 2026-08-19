import type { Account, Dashboard, Goal, Transaction } from './types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('ledgerly_token')
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  })

  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(data.error || data.msg || 'Request failed', response.status)
  return data as T
}

export type TransactionInput = {
  description: string
  amount: number
  category: string
  date: string
  notes?: string
}

export const api = {
  register: (email: string, password: string) =>
    request<{ accessToken: string; user: { email: string } }>('/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<{ accessToken: string; user: { email: string } }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  account: () => request<Account>('/account'),
  changePassword: (currentPassword: string, newPassword: string) =>
    request<{ updated: boolean }>('/account/password', { method: 'PATCH', body: JSON.stringify({ currentPassword, newPassword }) }),
  deleteAccount: (password: string) =>
    request<{ deleted: boolean }>('/account', { method: 'DELETE', body: JSON.stringify({ password }) }),
  dashboard: () => request<Dashboard>('/dashboard'),
  addTransaction: (payload: TransactionInput) => request<Transaction>('/transactions', { method: 'POST', body: JSON.stringify(payload) }),
  importTransactions: (transactions: TransactionInput[]) =>
    request<{ imported: number }>('/transactions/import', { method: 'POST', body: JSON.stringify({ transactions }) }),
  updateTransaction: (id: number, payload: TransactionInput) => request<Transaction>(`/transactions/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteTransaction: (id: number) => request<{ deleted: number }>(`/transactions/${id}`, { method: 'DELETE' }),
  addBudget: (payload: { category: string; limit: number }) => request('/budgets', { method: 'POST', body: JSON.stringify(payload) }),
  updateBudget: (id: number, limit: number) => request(`/budgets/${id}`, { method: 'PATCH', body: JSON.stringify({ limit }) }),
  deleteBudget: (id: number) => request<{ deleted: number }>(`/budgets/${id}`, { method: 'DELETE' }),
  addGoal: (payload: { name: string; target: number; saved: number }) => request<Goal>('/goals', { method: 'POST', body: JSON.stringify(payload) }),
  updateGoal: (id: number, payload: Partial<Pick<Goal, 'name' | 'target' | 'saved'>>) => request<Goal>(`/goals/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  contributeGoal: (id: number, amount: number) => request<Goal>(`/goals/${id}/contribute`, { method: 'POST', body: JSON.stringify({ amount }) }),
  deleteGoal: (id: number) => request<{ deleted: number }>(`/goals/${id}`, { method: 'DELETE' }),
  clearData: () => request<{ cleared: boolean }>('/data', { method: 'DELETE' }),
  seedDemo: () => request<{ seeded: boolean }>('/demo/seed', { method: 'POST' }),
  resetDemo: () => request<{ seeded: boolean; reset: boolean }>('/demo/reset', { method: 'POST' }),
}
