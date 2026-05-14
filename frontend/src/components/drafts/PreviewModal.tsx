import { useEffect, useRef } from 'react'

interface Props {
  html: string
  onClose: () => void
}

export function PreviewModal({ html, onClose }: Props) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      ref={overlayRef}
      onClick={e => { if (e.target === overlayRef.current) onClose() }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
    >
      <div className="relative flex flex-col bg-background rounded-xl shadow-2xl w-[96vw] h-[96vh] overflow-hidden border border-border">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-primary" />
            <p className="text-sm font-semibold text-foreground">Email Preview</p>
          </div>
          <p className="text-xs text-muted-foreground flex-1 text-center">
            This is how the customer will see the email
          </p>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer p-1 rounded-md hover:bg-muted"
            aria-label="Close preview"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* iframe */}
        <iframe
          srcDoc={html}
          title="Email preview"
          sandbox="allow-same-origin"
          className="flex-1 w-full border-none bg-[#f4f4f2]"
        />
      </div>
    </div>
  )
}
