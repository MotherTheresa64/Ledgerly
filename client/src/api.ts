import type { Dashboard } from './types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'

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
  if (!response.ok) throw new Error(data.error || 'Request failed')
  return data as T
}

export const api = {
  register: (email: string, password: string) =>
    request<{ accessToken: string }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<{ accessToken: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  dashboard: () => request<Dashboard>('/dashboard'),
  addTransaction: (payload: { description: string; amount: number; category: string; date: string }) =>
    request('/transactions', { method: 'POST', body: JSON.stringify(payload) }),
  deleteTransaction: (id: number) => request(`/transactions/${id}`, { method: 'DELETE' }),
  addBudget: (payload: { category: string; limit: number }) =>
    request('/budgets', { method: 'POST', body: JSON.stringify(payload) }),
  addGoal: (payload: { name: string; target: number; saved: number }) =>
    request('/goals', { method: 'POST', body: JSON.stringify(payload) }),
  seedDemo: () => request('/demo/seed', { method: 'POST' }),
}
