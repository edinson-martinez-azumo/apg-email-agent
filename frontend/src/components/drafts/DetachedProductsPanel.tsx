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
  status: 'confirmed' | 'rejected' | null
  isUserAdded: boolean
}

// Unused but may be needed later for HTML export
// @ts-expect-error unused but kept for future use
const _isValid = (val: string | null | undefined): boolean =>
  Boolean(val && val !== '' && val.toLowerCase() !== 'false')

// Unused but may be needed later for HTML export
// @ts-expect-error unused but kept for future use
const _buildProductCardHtml = (_p: Product): string => ''

function ProductCard({
  sku,
  title,
  score,
  status,
  isUserAdded,
  onConfirm,
  onReject,
}: {
  sku: string
  title: string | null
  score: number | null
  status: 'confirmed' | 'rejected' | null
  isUserAdded: boolean
  onConfirm: () => void
  onReject: () => void
}) {
  const specs = score !== null && score !== undefined ? `Score: ${(score * 100).toFixed(0)}%` : ''

  return (
    <div className={`rounded-md border bg-card p-2.5 flex gap-2.5 transition-all duration-150 ${
      status === 'confirmed' ? 'border-primary/30 bg-primary/5' :
      status === 'rejected' ? 'border-destructive/30 bg-destructive/5 opacity-60' :
      'border-border'
    }`}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <p className="text-xs font-semibold text-foreground leading-tight truncate">{title || sku}</p>
          {isUserAdded && (
            <span className="text-xs font-medium px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 shrink-0">
              Added
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground font-mono">{sku}</p>
        {specs && (
          <p className="text-xs text-muted-foreground mt-0.5">{specs}</p>
        )}
        <div className="mt-1.5 flex items-center gap-1.5">
          {status === 'confirmed' ? (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-primary/10 text-primary">
              ✓ Confirmed
            </span>
          ) : status === 'rejected' ? (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-destructive/10 text-destructive">
              ✗ Rejected
            </span>
          ) : (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
              Suggested
            </span>
          )}
        </div>
      </div>

      {status !== 'confirmed' && (
        <button
          onClick={onConfirm}
          className="text-primary hover:bg-primary/10 rounded-md p-1.5 transition-colors shrink-0 cursor-pointer"
          title="Confirm this product"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </button>
      )}
      {status !== 'rejected' && !isUserAdded && (
        <button
          onClick={onReject}
          className="text-destructive hover:bg-destructive/10 rounded-md p-1.5 transition-colors shrink-0 cursor-pointer"
          title="Reject this product"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
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

  // Merge all products into unified list
  const allProducts = useMemo(() => {
    const map = new Map<string, ValidatedProduct>()

    // Add detected products
    for (const p of detectedProducts?.products ?? []) {
      const localStatus = localState[p.sku]
      map.set(p.sku, {
        sku: p.sku,
        title: p.title,
        score: p.score,
        status: localStatus ?? null,
        isUserAdded: false,
      })
    }

    return Array.from(map.values())
  }, [detectedProducts, localState])

  const confirmedProducts = useMemo(
    () => allProducts.filter(p => p.status === 'confirmed'),
    [allProducts]
  )

  const handleConfirm = async (sku: string) => {
    setLocalState(prev => ({ ...prev, [sku]: 'confirmed' }))
    try {
      await emailsApi.validateProducts(emailId, {
        confirmed: [...(confirmedProducts.map(p => p.sku)), sku],
        rejected: allProducts.filter(p => p.status === 'rejected').map(p => p.sku),
      })
      refetchDetected()
    } catch {
      toast.error('Failed to confirm product')
      setLocalState(prev => { const n = { ...prev }; delete n[sku]; return n })
    }
  }

  const handleReject = async (sku: string) => {
    setLocalState(prev => ({ ...prev, [sku]: 'rejected' }))
    try {
      await emailsApi.validateProducts(emailId, {
        confirmed: confirmedProducts.map(p => p.sku),
        rejected: [...(allProducts.filter(p => p.status === 'rejected').map(p => p.sku)), sku],
      })
      refetchDetected()
    } catch {
      toast.error('Failed to reject product')
      setLocalState(prev => { const n = { ...prev }; delete n[sku]; return n })
    }
  }

  const handleAddProduct = async (product: Product) => {
    if (confirmedProducts.some(p => p.sku === product.sku)) {
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

  // Group products by intent bullets
  const productsByIntent = useMemo(() => {
    const groups: { intent: string; products: ValidatedProduct[] }[] = []
    const intentBullets = detectedProducts?.intent ?? []

    // Assign each product to an intent bullet based on matching
    const assigned = new Set<string>()

    for (const bullet of intentBullets) {
      const matchingProducts: ValidatedProduct[] = []
      const bulletText = typeof bullet === 'string' ? bullet : (bullet as { text: string }).text

      for (const product of allProducts) {
        if (assigned.has(product.sku)) continue

        // Simple heuristic: check if the product title/sku contains keywords from the bullet
        const bulletKeywords = bulletText.toLowerCase().split(/\s+/).filter((w: string) => w.length > 3)
        const productText = `${product.title || ''} ${product.sku}`.toLowerCase()

        const matchCount = bulletKeywords.filter((kw: string) => productText.includes(kw)).length
        if (matchCount >= Math.ceil(bulletKeywords.length / 2) && bulletKeywords.length > 0) {
          matchingProducts.push(product)
          assigned.add(product.sku)
        }
      }

      if (matchingProducts.length > 0) {
        groups.push({ intent: bulletText, products: matchingProducts })
      }
    }

    // Add unassigned products to "Other"
    const unassigned = allProducts.filter(p => !assigned.has(p.sku))
    if (unassigned.length > 0) {
      groups.push({ intent: `Other (${unassigned.length} products)`, products: unassigned })
    }

    return groups
  }, [detectedProducts?.intent, allProducts])

  if (!detectedProducts) {
    return (
      <div className="rounded-xl border border-border overflow-hidden">
        <div className="px-4 py-2.5 bg-muted/50 border-b border-border flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-amber-400" />
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Detected Products
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
          Detected Products
        </p>
        <span className="ml-auto rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs font-medium">
          {confirmedProducts.length} confirmed
        </span>
      </div>

      <div className="px-4 py-3 max-h-64 overflow-y-auto space-y-3">
        {allProducts.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">
            No products detected for this email yet.
          </p>
        )}

        {/* Products grouped by intent */}
        {productsByIntent.map((group, i) => (
          <div key={i}>
            <div className="flex items-center gap-1.5 mb-1.5">
              <div className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              <p className="text-xs font-medium text-foreground/80 italic">
                {group.intent}
              </p>
            </div>
            <div className="space-y-1.5">
              {group.products.map(product => (
                <ProductCard
                  key={product.sku}
                  sku={product.sku}
                  title={product.title}
                  score={product.score}
                  status={product.status}
                  isUserAdded={product.isUserAdded}
                  onConfirm={() => handleConfirm(product.sku)}
                  onReject={() => handleReject(product.sku)}
                />
              ))}
            </div>
          </div>
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
                const alreadyAdded = confirmedProducts.some(p => p.sku === product.sku)
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
