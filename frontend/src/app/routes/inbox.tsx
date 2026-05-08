import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { EmailRow } from '@/components/emails/EmailRow'
import { ThreadRow } from '@/components/emails/ThreadRow'
import { useEmails, useSyncEmails } from '@/hooks/useEmails'
import type { Email } from '@/types/api'

const TABS: { label: string; value: string | undefined }[] = [
  { label: 'Pending', value: 'pending' },
  { label: 'Draft Ready', value: 'draft_ready' },
  { label: 'Sent', value: 'sent' },
  { label: 'All', value: undefined },
]

function SkeletonRow() {
  return (
    <div className="flex items-center justify-between rounded-xl border border-border bg-card px-5 py-4 animate-pulse">
      <div className="flex-1 min-w-0 mr-4 space-y-2">
        <div className="h-4 w-40 bg-muted rounded" />
        <div className="h-3.5 w-72 bg-muted rounded" />
      </div>
      <div className="flex items-center gap-2.5">
        <div className="h-3.5 w-16 bg-muted rounded hidden sm:block" />
        <div className="h-5 w-20 bg-muted rounded-full" />
        <div className="h-4 w-4 bg-muted rounded" />
      </div>
    </div>
  )
}

export function InboxPage() {
  const [activeStatus, setActiveStatus] = useState<string | undefined>('pending')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const { data, isLoading, isError } = useEmails(activeStatus)
  const syncMutation = useSyncEmails()

  const handleSync = async () => {
    const t = toast.loading('Syncing emails…')
    try {
      const result = await syncMutation.mutateAsync()
      toast.success(`Synced — ${result.imported} new email${result.imported !== 1 ? 's' : ''}`, { id: t })
    } catch {
      toast.error('Sync failed', { id: t })
    }
  }

  const handleToggle = (id: string) => {
    setExpandedId(prev => (prev === id ? null : id))
  }

  // Close expanded row when switching tabs
  const handleTabChange = (value: string | undefined) => {
    setActiveStatus(value)
    setExpandedId(null)
  }

  const pendingCount = data?.total ?? 0

  // Group emails by thread_id; singles stay as-is
  const threadGroups = useMemo(() => {
    if (!data?.items) return []
    const map = new Map<string, Email[]>()
    for (const email of data.items) {
      const key = email.thread_id ?? email.id
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(email)
    }
    return Array.from(map.values())
      .map(group => group.sort((a, b) => new Date(a.received_at).getTime() - new Date(b.received_at).getTime()))
      .sort((a, b) => new Date(b[b.length - 1].received_at).getTime() - new Date(a[a.length - 1].received_at).getTime())
  }, [data?.items])

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b border-border bg-card/95 backdrop-blur-sm">
        <div className="mx-auto max-w-5xl px-4 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="h-7 w-7 rounded-lg bg-primary flex items-center justify-center">
                <svg aria-hidden="true" className="h-4 w-4 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <h1 className="text-sm font-semibold text-foreground">APG Email Agent</h1>
            </div>
            {pendingCount > 0 && activeStatus === 'pending' && (
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {pendingCount}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {activeStatus === 'pending' && (
              <button
                onClick={handleSync}
                disabled={syncMutation.isPending}
                aria-label="Sync emails from Gmail"
                className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 min-h-[36px] text-sm text-muted-foreground hover:text-foreground hover:border-primary/40 disabled:opacity-50 transition-colors duration-150 cursor-pointer"
              >
                <svg
                  aria-hidden="true"
                  className={`h-3.5 w-3.5 ${syncMutation.isPending ? 'animate-spin' : ''}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                {syncMutation.isPending ? 'Syncing…' : 'Refresh'}
              </button>
            )}
            <Link
              to="/dashboard"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-150 cursor-pointer"
            >
              Dashboard →
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-4 py-5">
        <div role="tablist" aria-label="Filter emails" className="flex gap-0.5 bg-muted rounded-xl p-1 mb-5 w-fit">
          {TABS.map((tab) => (
            <button
              key={tab.label}
              role="tab"
              aria-selected={activeStatus === tab.value}
              onClick={() => handleTabChange(tab.value)}
              className={`px-4 min-h-[44px] text-sm font-medium rounded-lg transition-colors duration-150 cursor-pointer ${
                activeStatus === tab.value
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div role="tabpanel" aria-label={`${TABS.find(t => t.value === activeStatus)?.label ?? 'All'} emails`}>
          {isLoading && (
            <div className="space-y-2">
              {[1, 2, 3].map(i => <SkeletonRow key={i} />)}
            </div>
          )}
          {isError && (
            <div className="py-12 text-center">
              <p className="text-sm text-destructive">Failed to load emails.</p>
              <p className="text-xs text-muted-foreground mt-1">Check that the backend is running.</p>
            </div>
          )}
          {data && data.items.length === 0 && (
            <div className="py-16 text-center">
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-3">
                <svg aria-hidden="true" className="h-6 w-6 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <p className="text-sm text-muted-foreground">No emails in this category</p>
            </div>
          )}
          {data && threadGroups.length > 0 && (
            <div className="space-y-2">
              {threadGroups.map(group => {
                if (group.length === 1) {
                  const email = group[0]
                  return (
                    <EmailRow
                      key={email.id}
                      email={email}
                      isExpanded={expandedId === email.id}
                      onToggle={() => handleToggle(email.id)}
                    />
                  )
                }
                return (
                  <ThreadRow
                    key={group[0].thread_id ?? group[0].id}
                    emails={group}
                  />
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
