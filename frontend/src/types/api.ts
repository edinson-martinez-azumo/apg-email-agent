export interface ThreadEmail {
  id: string
  gmail_id: string
  from_email: string
  from_name: string | null
  subject: string | null
  body_text: string | null
  received_at: string
}

export interface Email {
  id: string
  gmail_id: string
  thread_id: string | null
  from_email: string
  from_name: string | null
  subject: string | null
  body_text: string | null
  received_at: string
  status: 'pending' | 'draft_ready' | 'approved' | 'sent' | 'discarded'
  created_at: string
  thread: ThreadEmail[]
}

export interface EmailListResponse {
  items: Email[]
  total: number
  page: number
  size: number
}

export interface Draft {
  id: string
  email_id: string
  body: string
  edited_body: string | null
  approved_by: string | null
  approved_at: string | null
  sent_at: string | null
  gmail_draft_id: string | null
  confidence_score: number | null
  created_at: string
}

export interface Product {
  sku: string
  title: string
  type: string
  materials: string
  moq: string
  capacities: string
  in_stock: boolean
  price_base: number | string
  price_10k: number | string
  price_25k: number | string
  price_50k: number | string
  price_100k: number | string
  image_url: string | null
  dimensions: string | null
}

export interface DemoCase {
  id: string
  source: string
  customer: string
  contact: string
  email_subject: string
  email_body: string
  expected_skus: string[]
  notes: string
}

export interface DashboardStats {
  total_emails: number
  pending: number
  drafts_sent: number
  avg_response_time_hours: number | null
}

export interface RecentSentEmail {
  id: string
  from_email: string
  from_name: string | null
  subject: string | null
  sent_at: string | null
}

export interface DashboardResponse {
  stats: DashboardStats
  recent_sent: RecentSentEmail[]
}

export interface PollStatus {
  auto_sync: boolean
  auto_generate: boolean
  auto_send: boolean
  polling_interval_seconds: number
  last_poll_at: string | null
  pending_count: number
  new_emails: number
  processed_count: number
  status: string
  message: string
}

export interface ProductValidation {
  suggested: Array<{
    id: string
    sku: string
    title: string | null
    score: number | null
    status: string | null
  }>
  confirmed: Array<{
    id: string
    sku: string
    title: string | null
    score: number | null
    status: string | null
  }>
  rejected: Array<{
    id: string
    sku: string
    title: string | null
    score: number | null
    status: string | null
  }>
}
