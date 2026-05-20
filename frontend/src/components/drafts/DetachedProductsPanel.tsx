import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { emailsApi, productsApi } from '@/lib/api'
import { useDebounce } from '@/hooks/useDebounce'
import type { Product } from '@/types/api'

interface Props {
  emailId: string
}

interface ValidatedProduct {
  sku: string
  title: string | null
  score: number | null
  image_url: string | null
  status: 'confirmed' | 'rejected' | null
  isUserAdded: boolean
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return null
  const pct = (score * 100).toFixed(0)
  const color = score >= 0.7 ? 'text-emerald-700 bg-emerald-50' :
                score >= 0.4 ? 'text-amber-700 bg-amber-50' :
                'text-red-700 bg-red-50'
  return (
    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${color}`}>
      {pct}%
    </span>
  )
}

function ProductCard({
  sku, title, score, image_url, isUserAdded, onRemove, onRestore,
}: {
  sku: string
  title: string | null
  score: number | null
  image_url: string | null
  isUserAdded: boolean
  onRemove?: () => void
  onRestore?: () => void
}) {
  return (
    <div className={`rounded-md border bg-card p-2 flex gap-2 transition-all duration-150 ${
      onRestore ? 'opacity-50 border-border' : 'border-border'
    }`}>
      {image_url && (
        <div className="w-10 h-10 shrink-0 rounded overflow-hidden bg-muted">
          <img src={image_url} alt={title || sku} className="w-full h-full object-cover" loading="lazy" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <p className="text-xs font-semibold text-foreground leading-tight truncate">{title || sku}</p>
          {isUserAdded && (
            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 shrink-0">
              Added
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <p className="text-xs text-muted-foreground font-mono">{sku}</p>
          <ScoreBadge score={score} />
        </div>
      </div>

      {onRestore && (
        <button
          onClick={onRestore}
          className="text-muted-foreground hover:text-foreground hover:bg-muted rounded-md p-1.5 transition-colors shrink-0 cursor-pointer"
          title="Restore product"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      )}
      {onRemove && (
        <button
          onClick={onRemove}
          className="text-destructive hover:bg-destructive/10 rounded-md p-1.5 transition-colors shrink-0 cursor-pointer"
          title="Remove product"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  )
}

function SectionHeader({ label, count }: { label: string; count: number }) {
  return (
    <div className="flex items-center gap-2 pt-1">
      <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{label}</span>
      <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded-full">{count}</span>
    </div>
  )
}

export function DetachedProductsPanel({ emailId }: Props) {
  const [searchQuery, setSearchQuery] = useState('')
  const debouncedSearchQuery = useDebounce(searchQuery.trim(), 350)
  const [localState, setLocalState] = useState<Record<string, 'confirmed' | 'rejected'>>({})
  const [showRejected, setShowRejected] = useState(false)

  const { data: detectedProducts, refetch: refetchDetected } = useQuery({
    queryKey: ['detectedProducts', emailId],
    queryFn: () => emailsApi.getDetectedProducts(emailId),
    enabled: !!emailId,
  })

  const { data: searchResults, isFetching: isSearching } = useQuery({
    queryKey: ['products', 'search', debouncedSearchQuery],
    queryFn: () => productsApi.search(debouncedSearchQuery),
    enabled: debouncedSearchQuery.length >= 2,
    staleTime: 60_000,
  })

  const allProducts = useMemo(() => {
    const map = new Map<string, ValidatedProduct>()
    const detected = detectedProducts?.products ?? []
    for (const p of detected) {
      const localStatus = localState[p.sku]
      map.set(p.sku, {
        sku: p.sku,
        title: p.title,
        score: p.score,
        image_url: p.image_url,
        status: localStatus ?? (p.status as ValidatedProduct['status']) ?? null,
        isUserAdded: p.score == null,
      })
    }
    return Array.from(map.values())
  }, [detectedProducts, localState])

  const aiProducts = useMemo(
    () => allProducts.filter(p => p.status !== 'rejected' && p.score != null),
    [allProducts]
  )
  const manualProducts = useMemo(
    () => allProducts.filter(p => p.status !== 'rejected' && p.score == null),
    [allProducts]
  )
  const rejectedProducts = useMemo(
    () => allProducts.filter(p => p.status === 'rejected'),
    [allProducts]
  )
  const confirmedCount = aiProducts.length + manualProducts.length

  const handleRemove = async (sku: string) => {
    setLocalState(prev => ({ ...prev, [sku]: 'rejected' }))
    const currentConfirmed = allProducts
      .filter(p => p.sku !== sku && p.status !== 'rejected')
      .map(p => p.sku)
    const currentRejected = allProducts
      .filter(p => p.status === 'rejected')
      .map(p => p.sku)
    try {
      await emailsApi.validateProducts(emailId, {
        confirmed: currentConfirmed,
        rejected: [...currentRejected, sku],
      })
      refetchDetected()
    } catch {
      toast.error('Failed to remove product')
      setLocalState(prev => { const n = { ...prev }; delete n[sku]; return n })
    }
  }

  const handleRestore = async (sku: string) => {
    setLocalState(prev => { const n = { ...prev }; delete n[sku]; return n })
    const currentConfirmed = allProducts
      .filter(p => p.status !== 'rejected')
      .map(p => p.sku)
    const currentRejected = allProducts
      .filter(p => p.status === 'rejected' && p.sku !== sku)
      .map(p => p.sku)
    try {
      await emailsApi.validateProducts(emailId, {
        confirmed: [...currentConfirmed, sku],
        rejected: currentRejected,
      })
      refetchDetected()
    } catch {
      toast.error('Failed to restore product')
      setLocalState(prev => ({ ...prev, [sku]: 'rejected' }))
    }
  }

  const handleAddProduct = async (product: Product) => {
    if (allProducts.some(p => p.sku === product.sku && p.status !== 'rejected')) {
      toast.info('Product already added')
      return
    }
    const t = toast.loading('Adding product…')
    try {
      await emailsApi.addProduct(emailId, product.sku)
      toast.success(`Added ${product.sku}`, { id: t })
      setSearchQuery('')
      refetchDetected()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? 'Failed to add product', { id: t })
    }
  }

  return (
    <div className="rounded-xl border border-border overflow-hidden flex flex-col">
      {/* Header */}
      <div className="px-4 py-2.5 bg-muted/50 border-b border-border flex items-center gap-2 shrink-0">
        <div className="h-2 w-2 rounded-full bg-amber-400" />
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Products</p>
        <span className="ml-auto rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs font-medium">
          {confirmedCount} selected
        </span>
      </div>

      <div className="px-4 py-3 pb-5 flex flex-col gap-3 overflow-y-auto">

        {/* Search — always visible at top */}
        <div>
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search products to add…"
              className="w-full rounded-md border border-input bg-background px-3 py-2 pl-9 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
            />
            <svg className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            {isSearching && (
              <div className="absolute right-2.5 top-2.5">
                <div className="h-3 w-3 rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground animate-spin" />
              </div>
            )}
          </div>

          {debouncedSearchQuery.length >= 2 && searchResults && searchResults.length > 0 && (
            <div className="flex flex-col gap-1.5 mt-2 max-h-48 overflow-y-auto">
              {searchResults.map(product => {
                const alreadyAdded = allProducts.some(p => p.sku === product.sku && p.status !== 'rejected')
                return (
                  <button
                    key={product.sku}
                    onClick={() => handleAddProduct(product)}
                    disabled={alreadyAdded}
                    className={`text-left rounded-md border bg-card p-2 flex gap-2 transition-all cursor-pointer ${
                      alreadyAdded
                        ? 'opacity-50 border-border cursor-not-allowed'
                        : 'border-border hover:border-primary/30 hover:bg-primary/5'
                    }`}
                  >
                    {product.image_url && (
                      <div className="w-9 h-9 shrink-0 rounded overflow-hidden bg-muted">
                        <img src={product.image_url} alt={product.title} className="w-full h-full object-cover" loading="lazy" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-foreground leading-tight truncate">{product.title}</p>
                      <p className="text-xs text-muted-foreground font-mono mt-0.5">{product.sku}</p>
                    </div>
                    {!alreadyAdded && (
                      <span className="text-xs font-medium px-2 py-0.5 rounded-md bg-primary text-primary-foreground shrink-0 self-center">
                        + Add
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          )}

          {debouncedSearchQuery.length >= 2 && searchResults && searchResults.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-2 mt-1">
              No products found for "{debouncedSearchQuery}"
            </p>
          )}
        </div>

        {/* AI Detected products */}
        {aiProducts.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <SectionHeader label="AI Detected" count={aiProducts.length} />
            {aiProducts.map(p => (
              <ProductCard
                key={p.sku}
                sku={p.sku}
                title={p.title}
                score={p.score}
                image_url={p.image_url}
                isUserAdded={false}
                onRemove={() => handleRemove(p.sku)}
              />
            ))}
          </div>
        )}

        {/* Manually added products */}
        {manualProducts.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <SectionHeader label="Manually Added" count={manualProducts.length} />
            {manualProducts.map(p => (
              <ProductCard
                key={p.sku}
                sku={p.sku}
                title={p.title}
                score={p.score}
                image_url={p.image_url}
                isUserAdded={true}
                onRemove={() => handleRemove(p.sku)}
              />
            ))}
          </div>
        )}

        {confirmedCount === 0 && !detectedProducts && (
          <p className="text-xs text-muted-foreground text-center py-4">Loading products…</p>
        )}
        {confirmedCount === 0 && detectedProducts && rejectedProducts.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">No products detected. Use search to add manually.</p>
        )}

        {/* Rejected products — collapsed */}
        {rejectedProducts.length > 0 && (
          <div className="border-t border-border pt-2">
            <button
              onClick={() => setShowRejected(v => !v)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            >
              <svg className={`h-3 w-3 transition-transform ${showRejected ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              {rejectedProducts.length} rejected
            </button>
            {showRejected && (
              <div className="flex flex-col gap-1.5 mt-2">
                {rejectedProducts.map(p => (
                  <ProductCard
                    key={p.sku}
                    sku={p.sku}
                    title={p.title}
                    score={p.score}
                    image_url={p.image_url}
                    isUserAdded={p.isUserAdded}
                    onRestore={() => handleRestore(p.sku)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
