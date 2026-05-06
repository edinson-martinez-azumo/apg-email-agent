export interface Email {
  id: string
  gmail_id: string
  from_email: string
  from_name: string | null
  subject: string | null
  body_text: string | null
  received_at: string
  status: 'pending' | 'draft_ready' | 'approved' | 'sent' | 'discarded'
  created_at: string
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
  created_at: string
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
