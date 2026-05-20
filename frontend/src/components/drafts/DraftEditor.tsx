import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import { marked } from 'marked'
import type { Email, Draft, ThreadEmail } from '@/types/api'
import { ProductSearchPanel } from './ProductSearchPanel'
import { CustomerIntent } from './CustomerIntent'
import { useDebounce } from '@/hooks/useDebounce'

export function toHtml(content: string): string {
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

interface ContextPanelProps { email: Email; draft: Draft }
function ContextPanel({ email, draft }: ContextPanelProps) {
  const [emailExpanded, setEmailExpanded] = useState(false)
  const [threadExpanded, setThreadExpanded] = useState(false)
  const bodyLines = (email.body_text ?? '').split('\n').length

  return (
    <div className="min-h-0 overflow-y-auto flex flex-col bg-muted/20">
      <div className="px-4 py-2.5 bg-muted/50 border-b border-border shrink-0 flex items-center gap-2">
        <div className="h-2 w-2 rounded-full bg-amber-400" />
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Context</p>
      </div>

      <div className="px-4 py-3 border-b border-border/60">
        <CustomerIntent emailId={email.id} confidenceScore={draft.confidence_score} variant="full" />
      </div>

      <div className="px-4 py-3 flex flex-col gap-2">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Email</p>
        <div className="space-y-0.5">
          <p className="text-xs text-muted-foreground">
            <span className="font-medium">From: </span>
            {email.from_name ? `${email.from_name} <${email.from_email}>` : email.from_email}
          </p>
          <p className="text-xs text-muted-foreground">
            <span className="font-medium">Subject: </span>{email.subject ?? '(no subject)'}
          </p>
        </div>

        <pre className={`text-xs whitespace-pre-wrap font-sans text-foreground/80 leading-relaxed ${emailExpanded ? '' : 'line-clamp-5'}`}>
          {email.body_text ?? '(no body)'}
        </pre>
        {bodyLines > 5 && (
          <button
            onClick={() => setEmailExpanded(v => !v)}
            className="text-xs text-primary hover:opacity-80 cursor-pointer transition-opacity self-start"
          >
            {emailExpanded ? 'Show less' : 'Show more'}
          </button>
        )}

        {email.thread && email.thread.length > 0 && (
          <div className="border-t border-border/40 pt-2">
            <button
              onClick={() => setThreadExpanded(v => !v)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            >
              <svg
                className={`h-3 w-3 transition-transform duration-150 ${threadExpanded ? 'rotate-90' : ''}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              {email.thread.length} earlier {email.thread.length === 1 ? 'message' : 'messages'}
            </button>
            {threadExpanded && (
              <div className="mt-2 space-y-3">
                {email.thread.map((msg: ThreadEmail) => (
                  <div key={msg.id} className="pb-3 border-b border-border/40">
                    <p className="text-xs text-muted-foreground mb-1">
                      <span className="font-medium">From: </span>
                      {msg.from_name ? `${msg.from_name} <${msg.from_email}>` : msg.from_email}
                      <span className="ml-2 text-muted-foreground/60">
                        {new Date(msg.received_at).toLocaleDateString()}
                      </span>
                    </p>
                    <pre className="text-xs whitespace-pre-wrap font-sans text-muted-foreground leading-relaxed line-clamp-4">
                      {msg.body_text ?? '(no body)'}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

interface DraftEditorProps {
  email: Email
  draft: Draft
  onSave: (body: string) => void
  onDiscard: () => void
  onRegenerate: () => void
  onHtmlChange: (html: string) => void
  onSavedChange: (saved: boolean) => void
  isSaving: boolean
  isRegenerating: boolean
}

export function DraftEditor({
  email,
  draft,
  onSave,
  onHtmlChange,
  onSavedChange,
  isSaving,
}: DraftEditorProps) {
  const [html, setHtml] = useState(() => toHtml(draft.edited_body ?? draft.body))
  const [editorReady, setEditorReady] = useState(false)
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
      const newHtml = editor.getHTML()
      setHtml(newHtml)
      onHtmlChange(newHtml)
    },
  })

  // reset editor when draft changes (regenerate)
  useEffect(() => {
    if (!editor) return
    const newHtml = toHtml(draft.edited_body ?? draft.body)
    editor.commands.setContent(newHtml)
    setHtml(newHtml)
    onHtmlChange(newHtml)
    lastSavedRef.current = newHtml
  }, [draft.id, draft.body, draft.edited_body]) // eslint-disable-line react-hooks/exhaustive-deps

  // auto-save after debounce
  useEffect(() => {
    if (debouncedHtml && debouncedHtml !== lastSavedRef.current) {
      onSave(debouncedHtml)
      lastSavedRef.current = debouncedHtml
      onSavedChange(true)
      setTimeout(() => onSavedChange(false), 2000)
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
      if (node.type === 'image' && exact.test(node.attrs?.alt ?? '')) return []

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
    <div className="flex-1 grid grid-cols-[280px_1fr_300px] grid-rows-[1fr]">

      {/* LEFT: Context */}
      <ContextPanel email={email} draft={draft} />

      {/* CENTER: Editor */}
      <div className="flex flex-col border-l border-r border-border min-w-0 min-h-0 overflow-hidden">
        <div className="px-4 py-2.5 bg-primary/5 border-b border-primary/20 flex items-center gap-2 shrink-0">
          <div className="h-2 w-2 rounded-full bg-primary" />
          <p className="text-xs font-semibold text-primary uppercase tracking-wider">AI Draft Reply</p>
          {isSaving && (
            <span className="ml-auto text-xs text-muted-foreground flex items-center gap-1">
              <span className="h-2.5 w-2.5 rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground animate-spin" />
              Saving…
            </span>
          )}
        </div>
        <Toolbar editor={editor} />
        <div className="flex-1 min-h-0 overflow-y-auto tiptap-editor">
          <EditorContent editor={editor} />
        </div>
      </div>

      {/* RIGHT: Products */}
      <ProductSearchPanel
        onInsert={handleInsertProduct}
        editorReady={editorReady}
        insertedSkus={insertedSkus}
        onRemoveSku={handleRemoveProduct}
      />

    </div>
  )
}
