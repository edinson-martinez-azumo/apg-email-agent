import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'

function MetricCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 hover:shadow-sm transition-shadow duration-150">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">{label}</p>
      <p className="text-3xl font-semibold text-foreground">{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-border bg-card p-5 animate-pulse">
      <div className="h-3 w-24 bg-muted rounded mb-3" />
      <div className="h-8 w-16 bg-muted rounded" />
    </div>
  )
}

export function DashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard'],
    queryFn: dashboardApi.stats,
  })

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <>
        {isError && (
          <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4 mb-6">
            <p className="text-sm text-destructive">Failed to load dashboard stats.</p>
          </div>
        )}

        {/* Metric cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
          {isLoading ? (
            [1,2,3,4].map(i => <SkeletonCard key={i} />)
          ) : data ? (
            <>
              <MetricCard label="Total Emails" value={data.stats.total_emails} />
              <MetricCard label="Pending" value={data.stats.pending} sub="awaiting draft" />
              <MetricCard label="Replies Sent" value={data.stats.drafts_sent} />
              <MetricCard
                label="Avg Response"
                value={data.stats.avg_response_time_hours != null
                  ? `${data.stats.avg_response_time_hours.toFixed(1)}h`
                  : '—'}
              />
            </>
          ) : null}
        </div>

        {/* Recent sent */}
        <div>
          <h2 className="text-sm font-semibold text-foreground mb-3">Recent Sent</h2>
          {isLoading ? (
            <div className="rounded-xl border border-border overflow-hidden animate-pulse">
              {[1,2,3].map(i => (
                <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-border last:border-0">
                  <div className="h-4 w-32 bg-muted rounded" />
                  <div className="h-4 flex-1 bg-muted rounded" />
                  <div className="h-4 w-20 bg-muted rounded" />
                </div>
              ))}
            </div>
          ) : data && data.recent_sent.length === 0 ? (
            <div className="py-12 text-center rounded-xl border border-border">
              <p className="text-sm text-muted-foreground">No emails sent yet.</p>
            </div>
          ) : data ? (
            <div className="rounded-xl border border-border overflow-hidden">
              <table className="w-full text-sm table-fixed">
                <colgroup>
                  <col className="w-[28%]" />
                  <col className="w-[52%]" />
                  <col className="w-[20%]" />
                </colgroup>
                <thead>
                  <tr className="bg-muted/50 border-b border-border">
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground text-xs uppercase tracking-wider">From</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground text-xs uppercase tracking-wider">Subject</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground text-xs uppercase tracking-wider">Sent</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_sent.map((email, i) => (
                    <tr
                      key={email.id}
                      className={`border-b border-border last:border-0 hover:bg-muted/30 transition-colors duration-100 ${i % 2 === 0 ? '' : 'bg-muted/10'}`}
                    >
                      <td className="px-4 py-3 font-medium text-foreground">
                        <div className="truncate">{email.from_name ?? email.from_email}</div>
                      </td>
                      <td className="px-4 py-3 text-foreground/80">
                        <div className="truncate">{email.subject ?? '(no subject)'}</div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground whitespace-nowrap text-xs">
                        {email.sent_at ? formatRelativeTime(email.sent_at) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </>
    </div>
  )
}
