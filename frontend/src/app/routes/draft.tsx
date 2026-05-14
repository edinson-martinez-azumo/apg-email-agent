import { useParams, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useEmail, useGenerateDraft } from '@/hooks/useEmails'
import { useDraftByEmail, useUpdateDraft, useApproveDraft, useSendDraft, useDiscardDraft } from '@/hooks/useDrafts'
import { DraftEditor } from '@/components/drafts/DraftEditor'

function LoadingSkeleton() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card">
        <div className="mx-auto max-w-7xl px-4 py-3.5 flex items-center gap-3">
          <div className="h-4 w-16 bg-muted rounded animate-pulse" />
          <div className="h-4 w-px bg-border" />
          <div className="h-4 w-48 bg-muted rounded animate-pulse" />
        </div>
      </header>
      <div className="mx-auto max-w-7xl px-4 py-4">
        <div className="flex gap-4 h-[600px]">
          <div className="flex-1 rounded-xl border border-border bg-muted/30 animate-pulse" />
          <div className="flex-1 rounded-xl border border-border bg-muted/30 animate-pulse" />
        </div>
      </div>
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

  if (emailLoading || draftLoading) return <LoadingSkeleton />

  if (!email) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-sm text-destructive">Email not found.</p>
      </div>
    )
  }

  if (!draft) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3">
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

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="sticky top-0 z-10 border-b border-border bg-card/95 backdrop-blur-sm shrink-0">
        <div className="mx-auto max-w-7xl px-4 py-3.5 flex items-center gap-3">
          <button
            onClick={() => navigate('/inbox')}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-150 cursor-pointer"
          >
            ← Inbox
          </button>
          <span className="text-border select-none">|</span>
          <h1 className="text-sm font-medium text-foreground truncate flex-1">
            {email.subject ?? '(no subject)'}
          </h1>
          <span className="text-xs text-muted-foreground hidden sm:inline shrink-0">
            {email.from_name ?? email.from_email}
          </span>
        </div>
      </header>

      <div className="mx-auto max-w-7xl w-full px-4 py-4 flex-1 flex flex-col">
        <DraftEditor
          email={email}
          draft={draft}
          onSave={handleSave}
          onApproveAndSend={handleApproveAndSend}
          onRegenerate={handleRegenerate}
          onDiscard={handleDiscard}
          isSaving={updateDraft.isPending}
          isSending={approveDraft.isPending || sendDraft.isPending}
          isRegenerating={generateDraft.isPending}
        />
      </div>
    </div>
  )
}
