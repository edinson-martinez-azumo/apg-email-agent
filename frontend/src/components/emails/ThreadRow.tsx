import { useState } from 'react'
import { StatusBadge } from './StatusBadge'
import { EmailRow } from './EmailRow'
import { formatRelativeTime } from '@/lib/utils'
import type { Email } from '@/types/api'

interface ThreadRowProps {
  emails: Email[]  // sorted oldest → newest
  latestFirst?: boolean
}

export function ThreadRow({ emails, latestFirst = false }: ThreadRowProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [expandedEmailId, setExpandedEmailId] = useState<string | null>(null)

  const latest = emails[emails.length - 1]
  const sender = latest.from_name ?? latest.from_email
  const displayEmails = latestFirst ? [...emails].reverse() : emails

  // Deduplicate statuses for the badge row
  const statuses = [...new Set(emails.map(e => e.status))]

  // Count unique participants
  const participants = [...new Set(emails.map(e => e.from_name ?? e.from_email))]

  const handleToggleEmail = (id: string) => {
    setExpandedEmailId(prev => (prev === id ? null : id))
  }

  return (
    <article
      className={`rounded-xl border bg-card shadow-sm overflow-hidden transition-[border-color] duration-200 ${
        isExpanded ? 'border-primary/25' : 'border-border hover:border-primary/20'
      }`}
    >
      {/* Thread header */}
      <button
        onClick={() => setIsExpanded(p => !p)}
        aria-expanded={isExpanded}
        className="w-full flex items-center gap-4 px-5 py-4 cursor-pointer text-left"
      >
        {/* Thread icon */}
        <div className="shrink-0 h-7 w-7 rounded-lg bg-muted flex items-center justify-center">
          <svg aria-hidden="true" className="h-3.5 w-3.5 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="font-semibold text-sm text-foreground truncate">{sender}</span>
            {participants.length > 1 && (
              <span className="text-xs text-muted-foreground hidden sm:inline">
                +{participants.length - 1} more
              </span>
            )}
            <span className="shrink-0 inline-flex items-center justify-center rounded-full bg-primary/10 text-primary text-[11px] font-semibold px-1.5 py-0.5 min-w-[20px]">
              {emails.length}
            </span>
          </div>
          <p className="text-sm text-foreground/75 truncate">{latest.subject ?? '(no subject)'}</p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <span className="text-xs text-muted-foreground whitespace-nowrap hidden sm:inline">
            {formatRelativeTime(latest.received_at)}
          </span>
          <div className="flex gap-1">
            {statuses.map(s => <StatusBadge key={s} status={s} />)}
          </div>
          <svg
            aria-hidden="true"
            className={`h-4 w-4 text-muted-foreground/60 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Thread emails */}
      {isExpanded && (
        <div className="border-t border-border animate-in fade-in duration-150">
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-[28px] top-0 bottom-0 w-px bg-border" aria-hidden="true" />

            <div className="space-y-0">
              {displayEmails.map((email, idx) => {
                const isLatest = email.id === latest.id
                return (
                <div key={email.id} className="relative">
                  {/* Timeline dot */}
                  <div
                    className={`absolute left-5 top-5 h-3.5 w-3.5 rounded-full border-2 border-card z-10 ${
                      isLatest ? 'bg-primary' : 'bg-muted-foreground/40'
                    }`}
                    aria-hidden="true"
                  />

                  <div className="pl-12 pr-4 py-3">
                    {/* Mini email header — always visible */}
                    <button
                      onClick={() => handleToggleEmail(email.id)}
                      className="w-full flex items-center gap-2 text-left cursor-pointer group"
                    >
                      <div className="flex-1 min-w-0">
                        <span className="text-xs font-medium text-foreground group-hover:text-primary transition-colors">
                          {email.from_name ?? email.from_email}
                        </span>
                        <span className="text-xs text-muted-foreground ml-2">
                          {formatRelativeTime(email.received_at)}
                        </span>
                        {!isLatest && latestFirst && (
                          <span className="text-xs text-muted-foreground/50 ml-2 italic">read-only</span>
                        )}
                      </div>
                      <StatusBadge status={email.status} />
                      <svg
                        aria-hidden="true"
                        className={`h-3.5 w-3.5 text-muted-foreground/50 transition-transform duration-150 shrink-0 ${
                          expandedEmailId === email.id ? 'rotate-180' : ''
                        }`}
                        fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>

                    {/* Subject preview when collapsed */}
                    {expandedEmailId !== email.id && (
                      <p className="text-xs text-muted-foreground truncate mt-0.5">
                        {email.body_text?.split('\n').find(l => l.trim()) ?? '(no body)'}
                      </p>
                    )}
                  </div>

                  {/* Full email row when expanded */}
                  {expandedEmailId === email.id && (
                    <div className="pl-12 pr-4 pb-4">
                      <EmailRow
                        email={email}
                        isExpanded={true}
                        onToggle={() => handleToggleEmail(email.id)}
                        hideHeader
                        readOnly={latestFirst && !isLatest}
                      />
                    </div>
                  )}

                  {idx < displayEmails.length - 1 && (
                    <div className="ml-12 mr-4 border-b border-border/50" />
                  )}
                </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </article>
  )
}
