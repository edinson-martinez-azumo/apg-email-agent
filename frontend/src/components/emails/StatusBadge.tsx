import { cn } from '@/lib/utils'
import type { Email } from '@/types/api'

const STATUS_CONFIG: Record<Email['status'], { label: string; className: string }> = {
  pending:    { label: 'Pending',    className: 'bg-status-pending-bg text-status-pending-fg' },
  reviewed:   { label: 'Reviewed',   className: 'bg-status-reviewed-bg text-status-reviewed-fg' },
  draft_ready:{ label: 'Draft Ready',className: 'bg-status-draft-bg text-status-draft-fg' },
  approved:   { label: 'Approved',   className: 'bg-status-approved-bg text-status-approved-fg' },
  sent:       { label: 'Sent',       className: 'bg-status-sent-bg text-status-sent-fg' },
  discarded:  { label: 'Discarded',  className: 'bg-status-discarded-bg text-status-discarded-fg' },
}

interface StatusBadgeProps {
  status: Email['status']
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        config.className,
        className,
      )}
    >
      {config.label}
    </span>
  )
}
