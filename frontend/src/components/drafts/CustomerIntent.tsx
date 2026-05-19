import { useEmailIntent } from '@/hooks/useEmails'

interface Props {
  emailId: string
  confidenceScore?: number | null
}

function ScoreBadge({ score }: { score: number }) {
  const high = score >= 4
  const low = score <= 2
  const cls = high
    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
    : low
    ? 'bg-amber-50 text-amber-700 border-amber-200'
    : 'bg-muted text-muted-foreground border-border'
  const dot = high ? 'bg-emerald-500' : low ? 'bg-amber-500' : 'bg-muted-foreground'
  const label = high ? 'High match' : low ? 'Low match' : 'Partial match'
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {score.toFixed(1)}/5 — {label}
    </span>
  )
}

export function CustomerIntent({ emailId, confidenceScore }: Props) {
  const { data, isLoading, isError } = useEmailIntent(emailId)

  return (
    <div className="flex flex-col rounded-xl border border-border overflow-hidden shrink-0">
      <div className="px-4 py-2.5 bg-muted/50 border-b border-border flex items-center gap-2">
        <div className="h-2 w-2 rounded-full bg-amber-400" />
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Customer Intent
        </p>
        {confidenceScore != null && (
          <span className="ml-auto">
            <ScoreBadge score={confidenceScore} />
          </span>
        )}
      </div>

      <div className="px-4 py-3 bg-card">
        {isLoading && (
          <div className="space-y-2 animate-pulse">
            {[80, 65, 75].map((w, i) => (
              <div key={i} className="h-3 bg-muted rounded" style={{ width: `${w}%` }} />
            ))}
          </div>
        )}

        {isError && (
          <p className="text-xs text-muted-foreground">Could not extract request.</p>
        )}

        {data && data.bullets.length > 0 && (
          <ul className="space-y-1">
            {data.bullets.map((bullet, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-foreground/85">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0" />
                {bullet}
              </li>
            ))}
          </ul>
        )}

        {data && data.bullets.length === 0 && (
          <p className="text-xs text-muted-foreground">No structured request found.</p>
        )}
      </div>
    </div>
  )
}
