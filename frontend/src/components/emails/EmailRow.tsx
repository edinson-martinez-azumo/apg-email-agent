import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { StatusBadge } from './StatusBadge'
import { formatRelativeTime } from '@/lib/utils'
import type { Email } from '@/types/api'
import { useDraftByEmail, useApproveDraft, useSendDraft, useDiscardDraft } from '@/hooks/useDrafts'
import { useGenerateDraft } from '@/hooks/useEmails'

// ─── Main row ─────────────────────────────────────────────────────────────────

interface EmailRowProps {
  email: Email
  isExpanded: boolean
  onToggle: () => void
}

export function EmailRow({ email, isExpanded, onToggle }: EmailRowProps) {
  return (
    <article
      className={`rounded-xl border bg-card shadow-sm overflow-hidden transition-[border-color] duration-200 ${
        isExpanded ? 'border-primary/25' : 'border-border hover:border-primary/20'
      }`}
    >
      <button
        onClick={onToggle}
        aria-expanded={isExpanded}
        className="w-full flex items-center gap-4 px-5 py-4 cursor-pointer text-left"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="font-semibold text-sm text-foreground truncate">
              {email.from_name ?? email.from_email}
            </span>
            {email.from_name && (
              <span className="text-xs text-muted-foreground truncate hidden sm:inline">
                &lt;{email.from_email}&gt;
              </span>
            )}
          </div>
          <p className="text-sm text-foreground/75 truncate">
            {email.subject ?? '(no subject)'}
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <span className="text-xs text-muted-foreground whitespace-nowrap hidden sm:inline">
            {formatRelativeTime(email.received_at)}
          </span>
          <StatusBadge status={email.status} />
          <svg
            aria-hidden="true"
            className={`h-4 w-4 text-muted-foreground/60 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-border animate-in fade-in duration-150">
          {email.status === 'pending' && <PendingContent email={email} />}
          {(email.status === 'draft_ready' || email.status === 'approved') && (
            <DraftContent email={email} />
          )}
          {email.status === 'sent' && <SentContent email={email} />}
          {email.status === 'discarded' && <DiscardedContent email={email} />}
        </div>
      )}
    </article>
  )
}

// ─── Pending ──────────────────────────────────────────────────────────────────

function PendingContent({ email }: { email: Email }) {
  const generate = useGenerateDraft()

  const handleGenerate = () => {
    const t = toast.loading('Generating AI draft…')
    generate.mutate(email.id, {
      onSuccess: () => toast.success('Draft ready', { id: t }),
      onError: () => toast.error('Failed to generate draft', { id: t }),
    })
  }

  return (
    <div className="px-5 pt-4 pb-5">
      <EmailMeta email={email} />
      <EmailBody text={email.body_text} />
      <div className="flex justify-end pt-4">
        <button
          onClick={handleGenerate}
          disabled={generate.isPending}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 min-h-[40px] text-sm font-medium text-primary-foreground hover:opacity-90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity duration-150 cursor-pointer"
        >
          {generate.isPending ? (
            <>
              <span className="h-3 w-3 rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground animate-spin" />
              Generating…
            </>
          ) : (
            <>
              <svg aria-hidden="true" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Generate Draft
            </>
          )}
        </button>
      </div>
    </div>
  )
}

// ─── Draft ready / approved ───────────────────────────────────────────────────

function DraftContent({ email }: { email: Email }) {
  const [discardConfirm, setDiscardConfirm] = useState(false)
  const { data: draft, isLoading, isError } = useDraftByEmail(email.id)
  const approveDraft = useApproveDraft()
  const sendDraft = useSendDraft()
  const discardDraft = useDiscardDraft()
  const generate = useGenerateDraft()

  const isSending = approveDraft.isPending || sendDraft.isPending

  const handleApproveAndSend = async () => {
    if (!draft) return
    const t = toast.loading('Sending email…')
    try {
      if (email.status === 'draft_ready') await approveDraft.mutateAsync(draft.id)
      await sendDraft.mutateAsync(draft.id)
      toast.success('Email sent', { id: t })
    } catch {
      toast.error('Failed to send email', { id: t })
    }
  }

  const handleDiscard = async () => {
    if (!draft) return
    try {
      await discardDraft.mutateAsync(draft.id)
      toast.success('Draft discarded')
      setDiscardConfirm(false)
    } catch {
      toast.error('Failed to discard')
    }
  }

  const handleRegenerate = () => {
    const t = toast.loading('Regenerating draft…')
    generate.mutate(email.id, {
      onSuccess: () => toast.success('Draft regenerated', { id: t }),
      onError: () => toast.error('Failed to regenerate', { id: t }),
    })
  }

  const draftBody = draft?.edited_body ?? draft?.body ?? ''

  return (
    <div>
      <div className="grid lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-border">
        <div className="px-5 pt-4 pb-5">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Customer Email
          </p>
          <EmailMeta email={email} />
          <EmailBody text={email.body_text} />
        </div>

        <div className="px-5 pt-4 pb-5">
          <p className="text-xs font-semibold text-primary uppercase tracking-wider mb-3">
            AI Draft Reply
          </p>
          {isLoading && (
            <div className="space-y-2 animate-pulse">
              {[100, 80, 95, 70, 90].map((w, i) => (
                <div key={i} className={`h-3 bg-muted rounded`} style={{ width: `${w}%` }} />
              ))}
            </div>
          )}
          {isError && (
            <p className="text-sm text-muted-foreground">
              Draft unavailable.{' '}
              <Link to={`/draft/${email.id}`} className="text-primary underline underline-offset-2">
                Open editor
              </Link>
            </p>
          )}
          {draft && (
            <div className="max-h-52 overflow-y-auto rounded-lg bg-muted/30 px-3 py-2.5">
              <pre className="text-sm whitespace-pre-wrap font-sans text-foreground/85 leading-relaxed">
                {draftBody}
              </pre>
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-border px-5 py-3 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          {discardConfirm ? (
            <>
              <button
                onClick={() => setDiscardConfirm(false)}
                className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted transition-colors duration-150 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleDiscard}
                className="rounded-lg border border-destructive bg-destructive/5 px-3 py-1.5 text-xs font-medium text-destructive hover:bg-destructive hover:text-white transition-colors duration-150 cursor-pointer"
              >
                Confirm discard
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setDiscardConfirm(true)}
                disabled={!draft}
                className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:border-destructive hover:text-destructive disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150 cursor-pointer"
              >
                Discard
              </button>
              <button
                onClick={handleRegenerate}
                disabled={generate.isPending || !draft}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150 cursor-pointer"
              >
                {generate.isPending
                  ? <span className="h-3 w-3 rounded-full border-2 border-foreground/30 border-t-foreground animate-spin" />
                  : <span aria-hidden="true">↺</span>
                }
                {generate.isPending ? 'Regenerating…' : 'Regenerate'}
              </button>
            </>
          )}
        </div>

        <div className="flex items-center gap-2">
          {draft && (
            <Link
              to={`/draft/${email.id}`}
              className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:border-foreground/25 transition-colors duration-150"
            >
              Edit →
            </Link>
          )}
          <button
            onClick={handleApproveAndSend}
            disabled={isSending || !draft}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity duration-150 cursor-pointer shadow-sm"
          >
            {isSending ? (
              <>
                <span className="h-3 w-3 rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground animate-spin" />
                Sending…
              </>
            ) : (
              email.status === 'approved' ? '✉ Send' : '✉ Approve & Send'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Sent ─────────────────────────────────────────────────────────────────────

function SentContent({ email }: { email: Email }) {
  const { data: draft, isLoading } = useDraftByEmail(email.id)

  return (
    <div>
      <div className="grid lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-border">
        <div className="px-5 pt-4 pb-5">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Customer Email
          </p>
          <EmailMeta email={email} />
          <EmailBody text={email.body_text} />
        </div>

        <div className="px-5 pt-4 pb-5">
          <p className="text-xs font-semibold text-status-sent-fg uppercase tracking-wider mb-3">
            Sent Reply
          </p>
          {isLoading && (
            <div className="space-y-2 animate-pulse">
              {[100, 80, 95, 70].map((w, i) => (
                <div key={i} className="h-3 bg-muted rounded" style={{ width: `${w}%` }} />
              ))}
            </div>
          )}
          {draft ? (
            <div className="max-h-52 overflow-y-auto rounded-lg bg-muted/30 px-3 py-2.5">
              <pre className="text-sm whitespace-pre-wrap font-sans text-foreground/85 leading-relaxed">
                {draft.edited_body ?? draft.body}
              </pre>
            </div>
          ) : !isLoading ? (
            <p className="text-sm text-muted-foreground">Reply not found.</p>
          ) : null}
        </div>
      </div>

      <div className="border-t border-border px-5 py-2.5 flex items-center gap-1.5">
        <svg aria-hidden="true" className="h-3.5 w-3.5 text-status-sent-fg shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <span className="text-xs text-muted-foreground">
          Sent{draft?.sent_at ? ` ${formatRelativeTime(draft.sent_at)}` : ''}
        </span>
      </div>
    </div>
  )
}

// ─── Discarded ────────────────────────────────────────────────────────────────

function DiscardedContent({ email }: { email: Email }) {
  return (
    <div className="px-5 pt-4 pb-5">
      <EmailMeta email={email} />
      <EmailBody text={email.body_text} />
      <div className="mt-4 pt-3 border-t border-border flex items-center gap-1.5">
        <svg aria-hidden="true" className="h-3.5 w-3.5 text-status-discarded-fg shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
        <span className="text-xs text-muted-foreground">This email was discarded.</span>
      </div>
    </div>
  )
}

// ─── Shared primitives ────────────────────────────────────────────────────────

function EmailMeta({ email }: { email: Email }) {
  return (
    <div className="mb-3 space-y-0.5">
      <p className="text-xs text-muted-foreground">
        <span className="font-medium text-foreground/70">From: </span>
        {email.from_name ? `${email.from_name} <${email.from_email}>` : email.from_email}
      </p>
      <p className="text-xs text-muted-foreground">
        <span className="font-medium text-foreground/70">Subject: </span>
        {email.subject ?? '(no subject)'}
      </p>
    </div>
  )
}

function EmailBody({ text }: { text: string | null }) {
  return (
    <div className="max-h-52 overflow-y-auto rounded-lg bg-muted/30 px-3 py-2.5">
      <pre className="text-sm whitespace-pre-wrap font-sans text-foreground/80 leading-relaxed">
        {text ?? '(no body)'}
      </pre>
    </div>
  )
}
