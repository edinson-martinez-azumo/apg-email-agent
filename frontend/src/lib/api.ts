import axios from 'axios'
import { API_URL } from './config'
import type { Email, EmailListResponse, Draft, DashboardResponse } from '@/types/api'

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
}

export const dashboardApi = {
  stats: () =>
    http.get<DashboardResponse>('/api/v1/dashboard/stats').then(r => r.data),
}
