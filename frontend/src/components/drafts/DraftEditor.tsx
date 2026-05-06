import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
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
  const [mobileTab, setMobileTab] = useState<'edit' | 'preview'>('edit')

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
    <div className="flex flex-col h-full">
      <div className="flex flex-col lg:flex-row gap-4 flex-1 min-h-0">

        {/* Customer email — left */}
        <div className="lg:w-[32%] flex flex-col rounded-xl border border-border overflow-hidden">
          <div className="px-4 py-2.5 bg-muted/50 border-b border-border flex items-center gap-2 shrink-0">
            <div className="h-2 w-2 rounded-full bg-muted-foreground/40" />
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Customer Email
            </p>
          </div>
          <div className="flex-1 p-5 overflow-y-auto bg-card">
            <div className="mb-4 pb-4 border-b border-border space-y-1">
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

        {/* Draft split: edit + preview — right 68% */}
        <div className="lg:w-[68%] flex flex-col rounded-xl border border-primary/40 overflow-hidden">

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
              {/* Mobile tabs */}
              <div className="flex lg:hidden rounded-lg border border-border overflow-hidden text-xs">
                <button
                  onClick={() => setMobileTab('edit')}
                  className={`px-3 py-1 font-medium transition-colors cursor-pointer ${mobileTab === 'edit' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                >
                  Edit
                </button>
                <button
                  onClick={() => setMobileTab('preview')}
                  className={`px-3 py-1 font-medium transition-colors cursor-pointer ${mobileTab === 'preview' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                >
                  Preview
                </button>
              </div>
            </div>
          </div>

          {/* Split panels */}
          <div className="flex flex-1 min-h-0 divide-x divide-border">

            {/* Markdown textarea */}
            <div className={`flex flex-col min-h-0 ${mobileTab === 'preview' ? 'hidden lg:flex' : 'flex'} lg:w-1/2 w-full`}>
              <div className="px-3 py-1.5 bg-muted/30 border-b border-border shrink-0">
                <span className="text-xs text-muted-foreground font-medium">Markdown</span>
              </div>
              <label htmlFor="draft-reply" className="sr-only">Edit draft</label>
              <textarea
                id="draft-reply"
                className="flex-1 p-4 text-sm font-mono resize-none focus:outline-none bg-card text-foreground/90 leading-relaxed placeholder:text-muted-foreground"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                onBlur={handleBlur}
                placeholder="AI-generated draft will appear here…"
              />
            </div>

            {/* Rendered preview */}
            <div className={`flex flex-col min-h-0 ${mobileTab === 'edit' ? 'hidden lg:flex' : 'flex'} lg:w-1/2 w-full`}>
              <div className="px-3 py-1.5 bg-muted/30 border-b border-border shrink-0">
                <span className="text-xs text-muted-foreground font-medium">Preview</span>
              </div>
              <div className="flex-1 p-4 overflow-y-auto bg-card">
                <div className="prose prose-sm max-w-none text-foreground/90 leading-relaxed
                  [&_p]:mb-3 [&_p:last-child]:mb-0
                  [&_strong]:text-foreground [&_strong]:font-semibold
                  [&_ul]:my-2 [&_ul]:pl-5 [&_li]:my-0.5
                  [&_ol]:my-2 [&_ol]:pl-5
                  [&_h1]:text-base [&_h1]:font-semibold [&_h1]:mb-2 [&_h1]:text-foreground
                  [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:mb-1.5 [&_h2]:text-foreground
                  [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mb-1 [&_h3]:text-foreground
                  [&_hr]:border-border [&_hr]:my-3
                  [&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground
                ">
                  <ReactMarkdown>{body || '*No content yet*'}</ReactMarkdown>
                </div>
              </div>
            </div>
          </div>
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
