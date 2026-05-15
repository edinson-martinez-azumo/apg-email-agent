import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import { marked } from 'marked'
import type { Email, Draft, ThreadEmail } from '@/types/api'
import { ProductSearchPanel } from './ProductSearchPanel'
import { PreviewModal } from './PreviewModal'
import { CustomerIntent } from './CustomerIntent'
import { useDebounce } from '@/hooks/useDebounce'
import { draftsApi } from '@/lib/api'

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

function toHtml(content: string): string {
  if (content.trim().startsWith('<')) return content
  return marked(content) as string
}

type ToolbarProps = { editor: ReturnType<typeof useEditor> }
function Toolbar({ editor }: ToolbarProps) {
  if (!editor) return null

  const btn = (active: boolean, onClick: () => void, label: string) => (
    <button
      key={label}
      onMouseDown={e => { e.preventDefault(); onClick() }}
      className={`px-2 py-1 rounded text-xs font-medium transition-colors cursor-pointer ${
        active
          ? 'bg-primary/15 text-primary'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      }`}
      title={label}
    >
      {label}
    </button>
  )

  return (
    <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-primary/20 bg-primary/5 flex-wrap shrink-0">
      {btn(editor.isActive('bold'),      () => editor.chain().focus().toggleBold().run(),      'B')}
      {btn(editor.isActive('italic'),    () => editor.chain().focus().toggleItalic().run(),    'I')}
      <span className="w-px h-4 bg-border mx-1" />
      {btn(editor.isActive('heading', { level: 1 }), () => editor.chain().focus().toggleHeading({ level: 1 }).run(), 'H1')}
      {btn(editor.isActive('heading', { level: 2 }), () => editor.chain().focus().toggleHeading({ level: 2 }).run(), 'H2')}
      {btn(editor.isActive('heading', { level: 3 }), () => editor.chain().focus().toggleHeading({ level: 3 }).run(), 'H3')}
      <span className="w-px h-4 bg-border mx-1" />
      {btn(editor.isActive('bulletList'),  () => editor.chain().focus().toggleBulletList().run(),  '• List')}
      {btn(editor.isActive('orderedList'), () => editor.chain().focus().toggleOrderedList().run(), '1. List')}
      <span className="w-px h-4 bg-border mx-1" />
      {btn(false, () => editor.chain().focus().setHorizontalRule().run(), '—')}
    </div>
  )
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
  const [saved, setSaved] = useState(false)
  const [discardConfirm, setDiscardConfirm] = useState(false)
  const [html, setHtml] = useState(() => toHtml(draft.edited_body ?? draft.body))
  const [editorReady, setEditorReady] = useState(false)
  const [previewHtml, setPreviewHtml] = useState<string | null>(null)
  const [isPreviewing, setIsPreviewing] = useState(false)
  const lastSavedRef = useRef(html)
  const debouncedHtml = useDebounce(html, 1200)

  const editor = useEditor({
    extensions: [
      StarterKit,
      Image.configure({
        inline: false,
        allowBase64: false,
        HTMLAttributes: {
          style: 'max-width:160px;height:auto;border-radius:6px;margin:6px 0;display:block;',
        },
      }),

    ],
    content: html,
    editorProps: {
      attributes: { class: 'tiptap-editor' },
    },
    onFocus: () => setEditorReady(true),
    onUpdate: ({ editor }) => {
      setHtml(editor.getHTML())
    },
  })

  // reset editor when draft changes (regenerate)
  useEffect(() => {
    if (!editor) return
    const newHtml = toHtml(draft.edited_body ?? draft.body)
    editor.commands.setContent(newHtml)
    setHtml(newHtml)
    lastSavedRef.current = newHtml
  }, [draft.id, draft.body, draft.edited_body]) // eslint-disable-line react-hooks/exhaustive-deps

  // auto-save after debounce
  useEffect(() => {
    if (debouncedHtml && debouncedHtml !== lastSavedRef.current) {
      onSave(debouncedHtml)
      lastSavedRef.current = debouncedHtml
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    }
  }, [debouncedHtml]) // eslint-disable-line react-hooks/exhaustive-deps

  const insertedSkus = useMemo(() => {
    const skus = new Set<string>()
    const liBlocks = html.match(/<li[\s>][\s\S]*?<\/li>/gi) ?? []
    for (const li of liBlocks) {
      const text = li.replace(/<[^>]+>/g, ' ')
      const matches = text.match(/\bAPG-[\w/\-]+/gi) ?? []
      matches.forEach(s => skus.add(s.toUpperCase()))
    }
    return skus
  }, [html])

  const handlePreview = useCallback(async () => {
    setIsPreviewing(true)
    try {
      const result = await draftsApi.preview(draft.id, html)
      setPreviewHtml(result)
    } finally {
      setIsPreviewing(false)
    }
  }, [draft.id, html])

  const handleInsertProduct = useCallback((productHtml: string) => {
    if (!editor) return
    editor.chain().focus().insertContent(productHtml).run()
  }, [editor])

  const handleRemoveProduct = useCallback((sku: string) => {
    if (!editor) return
    const escaped = sku.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const exact = new RegExp(`${escaped}(?![\\w/\\-])`, 'i')
    const json = editor.getJSON()

    const newContent = (json.content ?? []).flatMap((node) => {
      // Remove standalone images whose alt matches the SKU
      if (node.type === 'image' && exact.test(node.attrs?.alt ?? '')) return []

      // For bullet lists: remove only the matching listItem(s)
      if (node.type === 'bulletList') {
        const remaining = (node.content ?? []).filter(
          item => !exact.test(JSON.stringify(item))
        )
        if (remaining.length === 0) return []
        return [{ ...node, content: remaining }]
      }

      return [node]
    })

    editor.commands.setContent({ ...json, content: newContent })
  }, [editor])

  return (
    <>
    <div className="flex gap-4 h-full">

      {/* Left column */}
      <div className="w-80 xl:w-96 shrink-0 flex flex-col gap-3" style={{ height: '100%' }}>

        {/* In Draft panel */}
        {insertedSkus.size > 0 && (
          <div className="rounded-xl border border-border overflow-hidden shrink-0">
            <div className="px-4 py-2.5 bg-muted/50 border-b border-border flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-primary" />
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">In Draft</p>
              <span className="ml-auto rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs font-medium">
                {insertedSkus.size}
              </span>
            </div>
            <div className="px-3 py-2.5 flex flex-col gap-1 max-h-48 overflow-y-auto">
              {[...insertedSkus].map(sku => (
                <div key={sku} className="flex items-center justify-between gap-2 rounded-md bg-muted/50 px-2.5 py-1.5">
                  <span className="text-xs font-mono text-foreground/80 truncate">{sku}</span>
                  <button
                    onClick={() => handleRemoveProduct(sku)}
                    className="text-muted-foreground hover:text-destructive transition-colors shrink-0 cursor-pointer"
                    title={`Remove ${sku}`}
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Product search panel */}
        <div className="flex-1 min-h-0">
          <ProductSearchPanel onInsert={handleInsertProduct} editorReady={editorReady} insertedSkus={insertedSkus} />
        </div>

      </div>

      {/* Right column */}
      <div className="flex flex-col flex-1 min-w-0 gap-4">

        {/* Customer email */}
        <div className="flex flex-col rounded-xl border border-border overflow-hidden shrink-0">
          <div className="px-4 py-2.5 bg-muted/50 border-b border-border flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-muted-foreground/40" />
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Customer Email
            </p>
            {email.thread?.length > 0 && (
              <span className="ml-auto text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                {email.thread.length + 1} emails in thread
              </span>
            )}
          </div>
          <div className="px-5 py-4 bg-card max-h-52 overflow-y-auto space-y-4">
            {email.thread?.map((msg: ThreadEmail) => (
              <div key={msg.id} className="pb-4 border-b border-border/50">
                <div className="flex flex-wrap gap-x-6 gap-y-0.5 mb-2">
                  <p className="text-xs text-muted-foreground">
                    <span className="font-medium">From: </span>
                    {msg.from_name ? `${msg.from_name} <${msg.from_email}>` : msg.from_email}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(msg.received_at).toLocaleDateString()}
                  </p>
                </div>
                <pre className="text-xs whitespace-pre-wrap font-sans text-muted-foreground leading-relaxed line-clamp-4">
                  {msg.body_text ?? '(no body)'}
                </pre>
              </div>
            ))}
            <div>
              <div className="mb-2 flex flex-wrap gap-x-6 gap-y-1">
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
        </div>

        <CustomerIntent emailId={email.id} confidenceScore={draft.confidence_score} />

        {/* TipTap editor */}
        <div className="flex flex-col rounded-xl border border-primary/40 overflow-hidden flex-1 min-h-0">
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

          <Toolbar editor={editor} />

          <div className="flex-1 min-h-0 overflow-y-auto tiptap-editor">
            <EditorContent editor={editor} className="h-full" />
          </div>
        </div>

        {/* Action bar */}
        <div className="flex items-center justify-between border-t border-border bg-background pt-4 pb-2 shrink-0">
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
          <div className="flex items-center gap-2">
            <button
              onClick={handlePreview}
              disabled={isPreviewing}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150 cursor-pointer"
            >
              {isPreviewing ? (
                <>
                  <span className="h-3.5 w-3.5 rounded-full border-2 border-foreground/30 border-t-foreground animate-spin" />
                  Loading…
                </>
              ) : '👁 Preview'}
            </button>
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
      </div>

    </div>

    {previewHtml && (
      <PreviewModal html={previewHtml} onClose={() => setPreviewHtml(null)} />
    )}
    </>
  )
}
