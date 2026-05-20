import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useEmail, useGenerateDraft } from '@/hooks/useEmails'
import { useDraftByEmail, useUpdateDraft, useApproveDraft, useSendDraft, useDiscardDraft } from '@/hooks/useDrafts'
import { DraftEditor, toHtml } from '@/components/drafts/DraftEditor'
import { PreviewModal } from '@/components/drafts/PreviewModal'
import { draftsApi } from '@/lib/api'

function LoadingSkeleton() {
  return (
    <div className="h-[calc(100vh-61px)] bg-background flex flex-col overflow-hidden">
      <header className="border-b border-border bg-card shrink-0">
        <div className="px-4 py-2.5 flex items-center gap-3">
          <div className="h-4 w-16 bg-muted rounded animate-pulse" />
          <div className="h-4 w-px bg-border" />
          <div className="h-4 w-48 bg-muted rounded animate-pulse flex-1" />
          <div className="h-8 w-24 bg-muted rounded animate-pulse" />
          <div className="h-8 w-32 bg-muted rounded animate-pulse" />
        </div>
      </header>
      <div className="flex-1 grid grid-cols-[280px_1fr_300px]">
        <div className="border-r border-border bg-muted/20 animate-pulse" />
        <div className="border-r border-border animate-pulse" />
        <div className="bg-muted/10 animate-pulse" />
      </div>
      <footer className="border-t border-border shrink-0 px-6 py-2">
        <div className="h-8 w-20 bg-muted rounded animate-pulse" />
      </footer>
    </div>
  )
}

export function DraftPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: email, isLoading: emailLoading } = useEmail(id!)
  const { data: draft, isLoading: draftLoading } = useDraftByEmail(id!)
  const updateDraft = useUpdateDraft()
  const approveDraft = useApproveDraft()
  const sendDraft = useSendDraft()
  const discardDraft = useDiscardDraft()
  const generateDraft = useGenerateDraft()

  const [currentHtml, setCurrentHtml] = useState('')
  const [previewHtml, setPreviewHtml] = useState<string | null>(null)
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [discardConfirm, setDiscardConfirm] = useState(false)
  const [saved, setSaved] = useState(false)

  if (emailLoading || draftLoading) return <LoadingSkeleton />

  if (!email) {
    return (
      <div className="h-[calc(100vh-61px)] flex items-center justify-center">
        <p className="text-sm text-destructive">Email not found.</p>
      </div>
    )
  }

  if (!draft) {
    return (
      <div className="h-[calc(100vh-61px)] flex flex-col items-center justify-center gap-3">
        <p className="text-sm text-muted-foreground">No draft yet for this email.</p>
        <button
          onClick={() => {
            toast.loading('Generating draft…')
            generateDraft.mutate(email.id, {
              onSuccess: () => toast.success('Draft generated'),
              onError: () => toast.error('Failed to generate draft'),
            })
          }}
          disabled={generateDraft.isPending}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 min-h-[44px] text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50 transition-opacity duration-150 cursor-pointer"
        >
          {generateDraft.isPending ? 'Generating…' : 'Generate Draft'}
        </button>
      </div>
    )
  }

  const initialHtml = toHtml(draft.edited_body ?? draft.body)

  const handlePreview = async () => {
    const html = currentHtml || initialHtml
    setIsPreviewing(true)
    try {
      const result = await draftsApi.preview(draft.id, html)
      setPreviewHtml(result)
    } finally {
      setIsPreviewing(false)
    }
  }

  const handleApproveAndSend = async () => {
    const sendToast = toast.loading('Sending email…')
    try {
      await approveDraft.mutateAsync(draft.id)
      await sendDraft.mutateAsync(draft.id)
      toast.success('Email sent successfully', { id: sendToast })
      navigate('/inbox')
    } catch {
      toast.error('Failed to send email', { id: sendToast })
    }
  }

  const handleDiscard = async () => {
    try {
      await discardDraft.mutateAsync(draft.id)
      toast.success('Draft discarded')
      navigate('/inbox')
    } catch {
      toast.error('Failed to discard draft')
    }
  }

  const handleRegenerate = () => {
    const t = toast.loading('Regenerating draft…')
    generateDraft.mutate(email.id, {
      onSuccess: () => toast.success('Draft regenerated', { id: t }),
      onError: () => toast.error('Failed to regenerate', { id: t }),
    })
  }

  const handleSave = (body: string) => {
    updateDraft.mutate(
      { id: draft.id, editedBody: body },
      { onError: () => toast.error('Failed to save changes') },
    )
  }

  const isSending = approveDraft.isPending || sendDraft.isPending

  return (
    <div className="h-[calc(100vh-61px)] bg-background flex flex-col overflow-hidden">

      {/* HEADER — action zone */}
      <header className="sticky top-0 z-10 border-b border-border bg-card/95 backdrop-blur-sm shrink-0">
        <div className="px-4 py-2.5 flex items-center gap-3 min-w-0">
          <button
            onClick={() => navigate('/inbox')}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-150 cursor-pointer shrink-0"
          >
            ← Inbox
          </button>
          <span className="text-border select-none shrink-0">|</span>
          <h1 className="text-sm font-medium text-foreground truncate flex-1">
            {email.subject ?? '(no subject)'}
          </h1>
          {saved && <span className="text-xs text-primary shrink-0">Saved ✓</span>}
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={handlePreview}
              disabled={isPreviewing}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150 cursor-pointer"
            >
              {isPreviewing ? (
                <>
                  <span className="h-3.5 w-3.5 rounded-full border-2 border-foreground/30 border-t-foreground animate-spin" />
                  Loading…
                </>
              ) : '👁 Preview'}
            </button>
            <button
              onClick={handleApproveAndSend}
              disabled={isSending}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity duration-150 cursor-pointer shadow-sm"
            >
              {isSending ? (
                <>
                  <span className="h-3.5 w-3.5 rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground animate-spin" />
                  Sending…
                </>
              ) : '✉ Approve & Send'}
            </button>
          </div>
        </div>
      </header>

      {/* THREE-COLUMN MAIN AREA */}
      <div className="flex-1 min-h-0 flex overflow-hidden">
        <DraftEditor
          email={email}
          draft={draft}
          onSave={handleSave}
          onRegenerate={handleRegenerate}
          onDiscard={handleDiscard}
          onHtmlChange={setCurrentHtml}
          onSavedChange={setSaved}
          isSaving={updateDraft.isPending}
          isRegenerating={generateDraft.isPending}
        />
      </div>

      {/* FOOTER — destructive action only */}
      <footer className="sticky bottom-0 border-t border-border bg-background shrink-0 px-6 py-2 flex items-center gap-2">
        {discardConfirm ? (
          <>
            <button
              onClick={() => setDiscardConfirm(false)}
              className="rounded-lg border border-border px-4 py-1.5 text-sm font-medium text-muted-foreground hover:bg-muted active:scale-95 transition-colors duration-150 cursor-pointer"
            >
              Cancel
            </button>
            <button
              onClick={() => { setDiscardConfirm(false); handleDiscard() }}
              className="rounded-lg border border-destructive bg-destructive/5 px-4 py-1.5 text-sm font-medium text-destructive hover:bg-destructive hover:text-white active:scale-95 transition-colors duration-150 cursor-pointer"
            >
              Confirm discard
            </button>
          </>
        ) : (
          <button
            onClick={() => setDiscardConfirm(true)}
            className="rounded-lg border border-border px-4 py-1.5 text-sm font-medium text-muted-foreground hover:border-destructive hover:text-destructive active:scale-95 transition-colors duration-150 cursor-pointer"
          >
            Discard
          </button>
        )}
      </footer>

      {previewHtml && (
        <PreviewModal html={previewHtml} onClose={() => setPreviewHtml(null)} />
      )}
    </div>
  )
}
