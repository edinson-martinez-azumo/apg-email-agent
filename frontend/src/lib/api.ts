import axios from 'axios'
import { API_URL } from './config'
import type { Email, EmailListResponse, Draft, DashboardResponse, Product, DemoCase, PollStatus } from '@/types/api'

const http = axios.create({ baseURL: API_URL })

export const emailsApi = {
  list: (status?: string, page = 1, size = 20) =>
    http.get<EmailListResponse>('/api/v1/emails/', { params: { status, page, size } }).then(r => r.data),
  get: (id: string) =>
    http.get<Email>(`/api/v1/emails/${id}`).then(r => r.data),
  generate: (id: string) =>
    http.post(`/api/v1/emails/${id}/generate`).then(r => r.data),
  discard: (id: string) =>
    http.post(`/api/v1/emails/${id}/discard`).then(r => r.data),
  sync: () =>
    http.post('/api/v1/emails/sync').then(r => r.data),
  intent: (id: string) =>
    http.get<{ bullets: string[] }>(`/api/v1/emails/${id}/intent`).then(r => r.data),
  getDetectedProducts: (id: string) =>
    http.get<{ intent: string[]; products: Array<{ sku: string; title: string | null; score: number | null; status: string | null }> }>(`/api/v1/emails/${id}/detected-products`).then(r => r.data),
  validateProducts: (id: string, body: { confirmed: string[]; rejected: string[] }) =>
    http.post<{ confirmed: string[]; rejected: string[]; suggested: string[] }>(`/api/v1/emails/${id}/products/validate`, body).then(r => r.data),
  addProduct: (id: string, sku: string) =>
    http.post<{ status: string; sku: string }>(`/api/v1/emails/${id}/products/add`, { sku }).then(r => r.data),
}

export const draftsApi = {
  get: (id: string) =>
    http.get<Draft>(`/api/v1/drafts/${id}`).then(r => r.data),
  getByEmailId: (emailId: string) =>
    http.get<Draft>(`/api/v1/drafts/by-email/${emailId}`).then(r => r.data),
  update: (id: string, editedBody: string) =>
    http.put<Draft>(`/api/v1/drafts/${id}`, { edited_body: editedBody }).then(r => r.data),
  approve: (id: string) =>
    http.post(`/api/v1/drafts/${id}/approve`).then(r => r.data),
  send: (id: string) =>
    http.post(`/api/v1/drafts/${id}/send`).then(r => r.data),
  discard: (id: string) =>
    http.post(`/api/v1/drafts/${id}/discard`).then(r => r.data),
  preview: (id: string, body: string) =>
    http.post(`/api/v1/drafts/${id}/preview`, { body }, { responseType: 'text' }).then(r => r.data as string),
}

export const dashboardApi = {
  stats: () =>
    http.get<DashboardResponse>('/api/v1/dashboard/stats').then(r => r.data),
}

export const productsApi = {
  search: (q: string, limit = 12) =>
    http.get<Product[]>('/api/v1/products/search', { params: { q, limit } }).then(r => r.data),
}

export const demoApi = {
  cases: () =>
    http.get<DemoCase[]>('/api/v1/demo/cases').then(r => r.data),
  send: (caseId: string) =>
    http.post<{ sent: boolean; case_id: string; subject: string }>(`/api/v1/demo/cases/${caseId}/send`).then(r => r.data),
}

export const settingsApi = {
  get: () =>
    http.get<{ auto_sync: boolean; auto_generate: boolean; auto_send: boolean; polling_interval_seconds: number; draft_count: number }>('/api/v1/settings').then(r => r.data),
  update: (payload: { auto_sync: boolean; auto_generate: boolean; auto_send: boolean; polling_interval_seconds: number }) =>
    http.put<{ auto_sync: boolean; auto_generate: boolean; auto_send: boolean; polling_interval_seconds: number; draft_count: number }>('/api/v1/settings', payload).then(r => r.data),
}

export const pollApi = {
  status: () =>
    http.get<PollStatus>('/api/v1/tasks/poll/status').then(r => r.data),
  trigger: () =>
    http.post<PollStatus>('/api/v1/tasks/poll').then(r => r.data),
}
