import { useState, useEffect } from 'react'
import MDEditor, { commands } from '@uiw/react-md-editor'
import '@uiw/react-md-editor/markdown-editor.css'
import type { Email, Draft } from '@/types/api'

interface DraftEditorProps {
  email: Email
  draft: Draft
  onSave: (body: string) => void
  onApproveAndSend: () => void
  onRegenerate: () => void
  onDiscard: () => void
  isSaving: boolean
  isSending: boolean
  isRegenerating: boolean
}

export function DraftEditor({
  email,
  draft,
  onSave,
  onApproveAndSend,
  onRegenerate,
  onDiscard,
  isSaving,
  isSending,
  isRegenerating,
}: DraftEditorProps) {
  const [body, setBody] = useState(draft.edited_body ?? draft.body)
  const [saved, setSaved] = useState(false)
  const [discardConfirm, setDiscardConfirm] = useState(false)

  useEffect(() => {
    setBody(draft.edited_body ?? draft.body)
  }, [draft.id, draft.edited_body, draft.body])

  const handleBlur = () => {
    if (body !== (draft.edited_body ?? draft.body)) {
      onSave(body)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    }
  }

  return (
    <div className="flex flex-col h-full gap-4">

        {/* Customer email — top */}
        <div className="flex flex-col rounded-xl border border-border overflow-hidden shrink-0">
          <div className="px-4 py-2.5 bg-muted/50 border-b border-border flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-muted-foreground/40" />
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Customer Email
            </p>
          </div>
          <div className="px-5 py-4 bg-card max-h-48 overflow-y-auto">
            <div className="mb-3 pb-3 border-b border-border flex flex-wrap gap-x-6 gap-y-1">
              <p className="text-sm">
                <span className="font-medium text-muted-foreground">From: </span>
                <span className="text-foreground">
                  {email.from_name ? `${email.from_name} <${email.from_email}>` : email.from_email}
                </span>
              </p>
              <p className="text-sm">
                <span className="font-medium text-muted-foreground">Subject: </span>
                <span className="text-foreground">{email.subject ?? '(no subject)'}</span>
              </p>
            </div>
            <pre className="text-sm whitespace-pre-wrap font-sans text-foreground/90 leading-relaxed">
              {email.body_text ?? '(no body)'}
            </pre>
          </div>
        </div>

        {/* MD Editor — below, takes remaining space */}
        <div className="flex flex-col rounded-xl border border-primary/40 overflow-hidden flex-1 min-h-0">

          {/* Header */}
          <div className="px-4 py-2.5 bg-primary/5 border-b border-primary/20 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-primary" />
              <p className="text-xs font-semibold text-primary uppercase tracking-wider">AI Draft Reply</p>
            </div>
            <div className="flex items-center gap-3">
              {isSaving && (
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <span className="h-2.5 w-2.5 rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground animate-spin" />
                  Saving…
                </span>
              )}
              {saved && !isSaving && <span className="text-xs text-primary">Saved ✓</span>}
            </div>
          </div>

          {/* Editor */}
          <div className="flex-1 min-h-0" onBlur={handleBlur} data-color-mode="light">
            <MDEditor
              value={body}
              onChange={(v) => setBody(v ?? '')}
              preview="live"
              height="100%"
              style={{ height: '100%' }}
              visibleDragbar={false}
              commands={[
                commands.bold,
                commands.italic,
                commands.divider,
                commands.unorderedListCommand,
                commands.orderedListCommand,
                commands.divider,
                commands.hr,
                commands.link,
              ]}
              extraCommands={[
                commands.fullscreen,
              ]}
            />
          </div>
        </div>

      {/* Action bar */}
      <div className="sticky bottom-0 mt-4 flex items-center justify-between border-t border-border bg-background pt-4 pb-2">
        <div className="flex gap-2">
          {discardConfirm ? (
            <>
              <button
                onClick={() => setDiscardConfirm(false)}
                className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted active:scale-95 transition-colors duration-150 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => { setDiscardConfirm(false); onDiscard() }}
                className="rounded-lg border border-destructive bg-destructive/5 px-4 py-2 text-sm font-medium text-destructive hover:bg-destructive hover:text-white active:scale-95 transition-colors duration-150 cursor-pointer"
              >
                Confirm discard
              </button>
            </>
          ) : (
            <button
              onClick={() => setDiscardConfirm(true)}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:border-destructive hover:text-destructive active:scale-95 transition-colors duration-150 cursor-pointer"
            >
              Discard
            </button>
          )}
          <button
            onClick={onRegenerate}
            disabled={isRegenerating}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150 cursor-pointer"
          >
            {isRegenerating ? (
              <>
                <span className="h-3.5 w-3.5 rounded-full border-2 border-foreground/30 border-t-foreground animate-spin" />
                Regenerating…
              </>
            ) : '↺ Regenerate'}
          </button>
        </div>
        <button
          onClick={onApproveAndSend}
          disabled={isSending}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-6 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity duration-150 cursor-pointer shadow-sm"
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
  )
}
