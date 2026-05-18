import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { demoApi } from '@/lib/api'
import type { DemoCase } from '@/types/api'

function CaseCard({ c }: { c: DemoCase }) {
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSend = async () => {
    setSending(true)
    setError(null)
    try {
      await demoApi.send(c.id)
      setSent(true)
      toast.success(`Sent "${c.email_subject}" to inbox`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Send failed'
      setError(msg)
      toast.error(msg)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground truncate">{c.customer}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{c.contact}</p>
        </div>
        <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full shrink-0">{c.id}</span>
      </div>

      <div>
        <p className="text-xs font-medium text-foreground/70 mb-1">Subject</p>
        <p className="text-sm text-foreground">{c.email_subject}</p>
      </div>

      <div>
        <p className="text-xs font-medium text-foreground/70 mb-1">Email</p>
        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-4 whitespace-pre-wrap">{c.email_body}</p>
      </div>

      {c.expected_skus.length > 0 && (
        <div>
          <p className="text-xs font-medium text-foreground/70 mb-1.5">Expected SKUs</p>
          <div className="flex flex-wrap gap-1.5">
            {c.expected_skus.map(sku => (
              <span key={sku} className="text-xs font-mono bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                {sku}
              </span>
            ))}
          </div>
        </div>
      )}

      {c.expected_skus.length === 0 && (
        <p className="text-xs text-muted-foreground italic">No expected SKUs (skip in eval)</p>
      )}

      {error && (
        <p className="text-xs text-destructive bg-destructive/5 rounded-md px-3 py-1.5">{error}</p>
      )}

      <button
        onClick={handleSend}
        disabled={sending || sent}
        className={`mt-auto w-full rounded-lg px-4 py-2 text-sm font-medium transition-all duration-150 cursor-pointer ${
          sent
            ? 'bg-emerald-100 text-emerald-700 border border-emerald-200 cursor-default'
            : 'bg-primary text-primary-foreground hover:opacity-90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed'
        }`}
      >
        {sent ? '✓ Sent to inbox' : sending ? 'Sending…' : 'Send Test Email'}
      </button>
    </div>
  )
}

export function DemoPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['demo', 'cases'],
    queryFn: demoApi.cases,
    staleTime: Infinity,
  })

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-6xl px-4 py-6">
        <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 flex items-start gap-2.5">
          <span className="text-amber-500 mt-0.5">⚠</span>
          <div>
            <p className="text-sm font-medium text-amber-800">Demo mode</p>
            <p className="text-xs text-amber-700 mt-0.5">
              Each button sends a real email to your connected Gmail inbox. After sending, click <strong>Refresh</strong> on the inbox to sync and process it.
            </p>
          </div>
        </div>

        {isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} className="rounded-xl border border-border bg-card p-5 h-64 animate-pulse">
                <div className="space-y-3">
                  <div className="h-4 w-32 bg-muted rounded" />
                  <div className="h-3 w-24 bg-muted rounded" />
                  <div className="h-3 w-full bg-muted rounded" />
                  <div className="h-3 w-5/6 bg-muted rounded" />
                </div>
              </div>
            ))}
          </div>
        )}

        {isError && (
          <div className="py-12 text-center">
            <p className="text-sm text-destructive">Failed to load demo cases.</p>
          </div>
        )}

        {data && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {data.map(c => <CaseCard key={c.id} c={c} />)}
          </div>
        )}
      </div>
    </div>
  )
}
