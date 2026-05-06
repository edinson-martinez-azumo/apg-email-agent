import { Link } from 'react-router-dom'
import { StatusBadge } from './StatusBadge'
import { formatRelativeTime } from '@/lib/utils'
import type { Email } from '@/types/api'

interface EmailCardProps {
  email: Email
  onGenerate: (id: string) => void
  isGenerating: boolean
}

export function EmailCard({ email, onGenerate, isGenerating }: EmailCardProps) {
  return (
    <div className="flex items-start justify-between rounded-xl border border-border bg-card px-5 py-4 shadow-sm hover:shadow-md hover:border-primary/30 transition-[box-shadow,border-color] duration-200 cursor-default">
      <div className="flex-1 min-w-0 mr-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-semibold text-sm text-foreground truncate">
            {email.from_name ?? email.from_email}
          </span>
          {email.from_name && (
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">
              &lt;{email.from_email}&gt;
            </span>
          )}
        </div>
        <p className="text-sm text-foreground/80 truncate mb-2">
          {email.subject ?? '(no subject)'}
        </p>
        <div className="flex items-center gap-2">
          <StatusBadge status={email.status} />
          <span className="text-xs text-muted-foreground">
            {formatRelativeTime(email.received_at)}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {email.status === 'pending' && (
          <button
            onClick={() => onGenerate(email.id)}
            disabled={isGenerating}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 min-h-[44px] text-xs font-medium text-primary-foreground hover:opacity-90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150 cursor-pointer"
          >
            {isGenerating ? (
              <>
                <span className="h-3 w-3 rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground animate-spin" />
                Generating…
              </>
            ) : (
              'Generate Draft'
            )}
          </button>
        )}
        {(email.status === 'draft_ready' || email.status === 'approved') && (
          <Link
            to={`/draft/${email.id}`}
            className="inline-flex items-center rounded-lg border border-primary px-3.5 min-h-[44px] text-xs font-medium text-primary hover:bg-primary hover:text-primary-foreground active:scale-95 transition-colors duration-150 cursor-pointer"
          >
            Review Draft →
          </Link>
        )}
        {email.status === 'sent' && (
          <span className="text-xs text-muted-foreground">Sent</span>
        )}
      </div>
    </div>
  )
}
