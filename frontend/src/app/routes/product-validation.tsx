import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useQuery } from '@tanstack/react-query'
import { useEmail } from '@/hooks/useEmails'
import { useProductValidation, useValidateProducts, useAddProduct, useGenerateWithProducts } from '@/hooks/useProductValidation'
import { productsApi } from '@/lib/api'
import { useDebounce } from '@/hooks/useDebounce'
import type { Product } from '@/types/api'

interface ValidatedProduct {
  sku: string
  title: string | null
  score: number | null
  status: 'confirmed' | 'rejected' | null
  isUserAdded: boolean
}

function isValid(val: string | null | undefined): boolean {
  return Boolean(val && val !== '' && val.toLowerCase() !== 'false')
}

function buildProductCardHtml(p: Product): string {
  const specs = [
    isValid(p.materials) && p.materials,
    isValid(p.capacities) && p.capacities,
    isValid(p.dimensions) && p.dimensions,
  ].filter(Boolean).join(', ')

  const label = specs ? `${p.sku} — ${specs}` : p.sku
  const imgHtml = p.image_url
    ? `<img src="${p.image_url}" alt="${p.sku}" style="display:block;max-width:160px;height:auto;border-radius:6px;margin:6px 0;">`
    : ''

  return [`<ul><li>${label}</li></ul>`, imgHtml, '<p></p>'].join('')
}

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
    <div className={`rounded-lg border bg-card p-3 flex gap-3 transition-all duration-150 ${
      status === 'confirmed' ? 'border-primary/30 bg-primary/5' :
      status === 'rejected' ? 'border-destructive/30 bg-destructive/5 opacity-60' :
      'border-border'
    }`}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <p className="text-sm font-semibold text-foreground leading-tight truncate">{title || sku}</p>
          {isUserAdded && (
            <span className="text-xs font-medium px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 shrink-0">
              Added by you
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground font-mono">{sku}</p>
        {specs && (
          <p className="text-xs text-muted-foreground mt-1">{specs}</p>
        )}
        <div className="mt-2 flex items-center gap-1.5">
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

export function ProductValidationPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [searchQuery, setSearchQuery] = useState('')
  const debouncedSearchQuery = useDebounce(searchQuery.trim(), 350)

  const { data: email, isLoading: emailLoading } = useEmail(id!)
  const { data: validation, isLoading: validationLoading } = useProductValidation(id!)
  const validateProducts = useValidateProducts()
  const addProduct = useAddProduct()
  const generateWithProducts = useGenerateWithProducts()

  const [localState, setLocalState] = useState<Record<string, 'confirmed' | 'rejected'>>({})

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

    // Add suggested products
    for (const p of validation?.suggested ?? []) {
      const localStatus = localState[p.sku]
      map.set(p.sku, {
        sku: p.sku,
        title: p.title,
        score: p.score,
        status: localStatus ?? null,
        isUserAdded: false,
      })
    }

    // Add confirmed products
    for (const p of validation?.confirmed ?? []) {
      if (!map.has(p.sku)) {
        map.set(p.sku, {
          sku: p.sku,
          title: p.title,
          score: p.score,
          status: 'confirmed',
          isUserAdded: false,
        })
      }
    }

    // Add rejected products (show them faded)
    for (const p of validation?.rejected ?? []) {
      if (!map.has(p.sku)) {
        map.set(p.sku, {
          sku: p.sku,
          title: p.title,
          score: p.score,
          status: 'rejected',
          isUserAdded: false,
        })
      }
    }

    return Array.from(map.values())
  }, [validation, localState])

  const confirmedProducts = useMemo(
    () => allProducts.filter(p => p.status === 'confirmed'),
    [allProducts]
  )

  const handleConfirm = (sku: string) => {
    setLocalState(prev => ({ ...prev, [sku]: 'confirmed' }))
    validateProducts.mutate({
      emailId: id!,
      body: {
        confirmed: [...(validation?.confirmed.map(p => p.sku) ?? []), sku],
        rejected: validation?.rejected.map(p => p.sku) ?? [],
      },
    })
  }

  const handleReject = (sku: string) => {
    setLocalState(prev => ({ ...prev, [sku]: 'rejected' }))
    validateProducts.mutate({
      emailId: id!,
      body: {
        confirmed: validation?.confirmed.map(p => p.sku) ?? [],
        rejected: [...(validation?.rejected.map(p => p.sku) ?? []), sku],
      },
    })
  }

  const handleAddProduct = async (product: Product) => {
    if (confirmedProducts.some(p => p.sku === product.sku)) {
      toast.info('Product already added')
      return
    }

    const t = toast.loading('Adding product…')
    try {
      await addProduct.mutateAsync({ emailId: id!, sku: product.sku })
      toast.success(`Added ${product.sku}`, { id: t })
      setSearchQuery('')
    } catch {
      toast.error('Failed to add product', { id: t })
    }
  }

  const handleContinue = async () => {
    if (confirmedProducts.length === 0) {
      toast.error('Please confirm at least one product')
      return
    }

    const t = toast.loading('Generating draft…')
    try {
      await generateWithProducts.mutateAsync({
        emailId: id!,
        products: confirmedProducts.map(p => p.sku),
      })
      toast.success('Draft generated', { id: t })
      navigate(`/draft/${id}`)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? 'Failed to generate draft', { id: t })
    }
  }

  const handleSkip = () => {
    navigate(`/draft/${id}`)
  }

  if (emailLoading || validationLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="h-6 w-6 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
      </div>
    )
  }

  if (!email) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-sm text-destructive">Email not found.</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
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
            Validate Products — {email.subject ?? '(no subject)'}
          </h1>
          <span className="text-xs text-muted-foreground hidden sm:inline shrink-0">
            {email.from_name ?? email.from_email}
          </span>
        </div>
      </header>

      {/* Main content */}
      <div className="mx-auto max-w-7xl w-full px-4 py-4 flex-1 flex flex-col gap-4">
        {/* Product list */}
        <div className="flex-1 min-h-0 flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-primary" />
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Products ({confirmedProducts.length} confirmed)
            </p>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            {allProducts.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">
                No products detected for this email yet.
              </p>
            )}

            {allProducts.map(product => (
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

        {/* Add new products */}
        <div className="flex flex-col gap-2 border-t border-border pt-4">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-muted-foreground/40" />
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
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 max-h-48 overflow-y-auto">
              {searchResults.map(product => {
                const alreadyAdded = confirmedProducts.some(p => p.sku === product.sku)
                return (
                  <button
                    key={product.sku}
                    onClick={() => handleAddProduct(product)}
                    disabled={alreadyAdded}
                    className={`text-left rounded-lg border bg-card p-2.5 flex gap-2.5 transition-all cursor-pointer ${
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

      {/* Bottom bar */}
      <div className="border-t border-border bg-card px-4 py-3 shrink-0">
        <div className="mx-auto max-w-7xl flex items-center justify-between gap-3">
          <button
            onClick={() => navigate('/inbox')}
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted active:scale-95 transition-colors duration-150 cursor-pointer"
          >
            ← Back to Inbox
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={handleSkip}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:border-foreground/25 active:scale-95 transition-colors duration-150 cursor-pointer"
            >
              Skip →
            </button>
            <button
              onClick={handleContinue}
              disabled={confirmedProducts.length === 0}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-6 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity duration-150 cursor-pointer shadow-sm"
            >
              Continue to Draft →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
