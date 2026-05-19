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
  sku,
  title,
  score,
  image_url,
  status,
  isUserAdded,
  onRemove,
}: {
  sku: string
  title: string | null
  score: number | null
  image_url: string | null
  status: 'confirmed' | 'rejected' | null
  isUserAdded: boolean
  onRemove: () => void
}) {
  return (
    <div className={`rounded-md border bg-card p-2 flex gap-2 transition-all duration-150 ${
      status === 'rejected' ? 'opacity-50 border-border' :
      score !== null && score < 0.4 ? 'border-amber-200 bg-amber-50/50' :
      'border-border'
    }`}>
      {image_url && (
        <div className="w-12 h-12 shrink-0 rounded overflow-hidden bg-muted">
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

      <button
        onClick={onRemove}
        className="text-destructive hover:bg-destructive/10 rounded-md p-1.5 transition-colors shrink-0 cursor-pointer"
        title="Remove this product"
      >
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}

function SearchBar({
  query,
  setQuery,
  isSearching,
}: {
  query: string
  setQuery: (q: string) => void
  isSearching: boolean
}) {
  return (
    <div className="relative">
      <input
        type="text"
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Search products by name, type, material…"
        className="w-full rounded-md border border-input bg-background px-3 py-2 pl-9 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
      />
      <svg
        className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      {isSearching && (
        <div className="absolute right-2.5 top-2.5">
          <div className="h-3 w-3 rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground animate-spin" />
        </div>
      )}
    </div>
  )
}

export function DetachedProductsPanel({ emailId }: Props) {
  const [searchQuery, setSearchQuery] = useState('')
  const debouncedSearchQuery = useDebounce(searchQuery.trim(), 350)

  const [localState, setLocalState] = useState<Record<string, 'confirmed' | 'rejected'>>({})

  // Fetch detected products
  const { data: detectedProducts, refetch: refetchDetected } = useQuery({
    queryKey: ['detectedProducts', emailId],
    queryFn: () => emailsApi.getDetectedProducts(emailId),
    enabled: !!emailId,
  })

  // Search products for adding
  const { data: searchResults, isFetching: isSearching } = useQuery({
    queryKey: ['products', 'search', debouncedSearchQuery],
    queryFn: () => productsApi.search(debouncedSearchQuery),
    enabled: debouncedSearchQuery.length >= 2,
    staleTime: 60_000,
  })

  // Merge all products into unified list, sorted by score desc
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
        status: localStatus ?? null,
        isUserAdded: false,
      })
    }

    return Array.from(map.values())
      .sort((a, b) => {
        // Put rejected at bottom
        if (a.status === 'rejected' && b.status !== 'rejected') return 1
        if (a.status !== 'rejected' && b.status === 'rejected') return -1
        // Sort by score desc (null scores last)
        if (a.score == null && b.score == null) return 0
        if (a.score == null) return 1
        if (b.score == null) return -1
        return b.score - a.score
      })
  }, [detectedProducts, localState])

  const confirmedProducts = useMemo(
    () => allProducts.filter(p => p.status !== 'rejected'),
    [allProducts]
  )

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

  const handleAddProduct = async (product: Product) => {
    if (allProducts.some(p => p.sku === product.sku)) {
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

  if (!detectedProducts) {
    return (
      <div className="rounded-xl border border-border overflow-hidden">
        <div className="px-4 py-2.5 bg-muted/50 border-b border-border flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-amber-400" />
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Products
          </p>
          <div className="ml-auto h-3 w-3 rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground animate-spin" />
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <div className="px-4 py-2.5 bg-muted/50 border-b border-border flex items-center gap-2">
        <div className="h-2 w-2 rounded-full bg-amber-400" />
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Products
        </p>
        <span className="ml-auto rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs font-medium">
          {confirmedProducts.length} selected
        </span>
      </div>

      <div className="px-4 py-3 space-y-1.5">
        {allProducts.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">
            No products detected for this email yet.
          </p>
        )}

        {allProducts.map(product => (
          <ProductCard
            key={product.sku}
            sku={product.sku}
            title={product.title}
            score={product.score}
            image_url={product.image_url}
            status={product.status ?? 'confirmed'}
            isUserAdded={product.isUserAdded}
            onRemove={() => handleRemove(product.sku)}
          />
        ))}

        {/* Add new products */}
        <div className="pt-2 border-t border-border">
          <div className="flex items-center gap-1.5 mb-2">
            <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40" />
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Add New Products
            </p>
          </div>

          <SearchBar
            query={searchQuery}
            setQuery={setSearchQuery}
            isSearching={isSearching}
          />

          {debouncedSearchQuery.length >= 2 && searchResults && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-48 overflow-y-auto mt-2">
              {searchResults.map(product => {
                const alreadyAdded = allProducts.some(p => p.sku === product.sku)
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
                      <div className="w-10 h-10 shrink-0 rounded overflow-hidden bg-muted">
                        <img src={product.image_url} alt={product.title} className="w-full h-full object-cover" loading="lazy" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-foreground leading-tight truncate">
                        {product.title}
                      </p>
                      <p className="text-xs text-muted-foreground font-mono mt-0.5">{product.sku}</p>
                      {product.type && (
                        <p className="text-xs text-muted-foreground mt-0.5">{product.type}</p>
                      )}
                    </div>
                    {!alreadyAdded && (
                      <span className="text-xs font-medium px-2 py-0.5 rounded-md bg-primary text-primary-foreground shrink-0">
                        Add
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          )}

          {debouncedSearchQuery.length >= 2 && searchResults && searchResults.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-2">
              No products found for "{debouncedSearchQuery}"
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
