export type Transaction = {
  id: number
  description: string
  amount: number
  category: string
  date: string
  notes?: string
}

export type Budget = {
  id: number
  category: string
  limit: number
  spent: number
}

export type Goal = {
  id: number
  name: string
  target: number
  saved: number
}

export type Dashboard = {
  totalBalance: number
  income: number
  expenses: number
  savingsRate: number
  categories: { category: string; amount: number }[]
  transactions: Transaction[]
  budgets: Budget[]
  goals: Goal[]
}
