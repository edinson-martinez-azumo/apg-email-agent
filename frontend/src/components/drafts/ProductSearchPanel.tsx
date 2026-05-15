import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { productsApi } from '@/lib/api'
import { useDebounce } from '@/hooks/useDebounce'
import type { Product } from '@/types/api'

interface Props {
  onInsert: (html: string) => void
  editorReady: boolean
  insertedSkus: Set<string>
}

function isValid(val: string | null | undefined): boolean {
  return Boolean(val && val !== '' && val.toLowerCase() !== 'false')
}

function buildProductHtml(p: Product): string {
  const specs = [
    isValid(p.materials)  && p.materials,
    isValid(p.capacities) && p.capacities,
    isValid(p.dimensions) && p.dimensions,
  ].filter(Boolean).join(', ')

  const label = specs ? `${p.sku} — ${specs}` : p.sku
  const imgHtml = p.image_url
    ? `<img src="${p.image_url}" alt="${p.sku}" style="display:block;max-width:160px;height:auto;border-radius:6px;margin:6px 0;">`
    : ''

  return [`<ul><li>${label}</li></ul>`, imgHtml, '<p></p>'].join('')
}


function ProductCard({ product, onInsert, editorReady, alreadyAdded }: { product: Product; onInsert: (html: string) => void; editorReady: boolean; alreadyAdded: boolean }) {
  const hasImage = Boolean(product.image_url)

  const prices = [
    product.price_base && `$${product.price_base}`,
    product.price_10k  && `$${product.price_10k} @10k`,
    product.price_25k  && `$${product.price_25k} @25k`,
  ].filter(Boolean).join(' · ')

  return (
    <div className="rounded-lg border border-border bg-card p-3 flex gap-3">
      {hasImage && (
        <img
          src={product.image_url!}
          alt={product.title}
          className="w-16 h-16 object-contain rounded shrink-0 bg-muted"
        />
      )}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-foreground leading-tight truncate">{product.title}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{product.sku}</p>

        <div className="mt-1.5 space-y-0.5">
          {product.type && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground/70">Type:</span> {product.type}
            </p>
          )}
          {product.materials && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground/70">Materials:</span> {product.materials}
            </p>
          )}
          {product.capacities && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground/70">Capacities:</span> {product.capacities}
            </p>
          )}
          {product.moq && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground/70">MOQ:</span> {product.moq}
            </p>
          )}
          {prices && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground/70">Price:</span> {prices}
            </p>
          )}
        </div>

        <div className="mt-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span
              className={`text-xs font-medium px-1.5 py-0.5 rounded-full ${
                product.in_stock
                  ? 'bg-primary/10 text-primary'
                  : 'bg-muted text-muted-foreground'
              }`}
            >
              {product.in_stock ? '✓ In Stock' : 'Out of Stock'}
            </span>
            {alreadyAdded && (
              <span className="text-xs font-medium px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700">
                Already added
              </span>
            )}
          </div>
          <button
            onClick={() => onInsert(buildProductHtml(product))}
            disabled={!editorReady || alreadyAdded}
            title={!editorReady ? 'Click in the draft first to place your cursor' : alreadyAdded ? 'Already in the draft' : undefined}
            className="text-xs font-medium px-2.5 py-1 rounded-md bg-primary text-primary-foreground hover:opacity-90 active:scale-95 transition-all cursor-pointer shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Insert
          </button>
        </div>
      </div>
    </div>
  )
}

export function ProductSearchPanel({ onInsert, editorReady, insertedSkus }: Props) {
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebounce(query.trim(), 350)

  const { data, isFetching, isError } = useQuery({
    queryKey: ['products', 'search', debouncedQuery],
    queryFn: () => productsApi.search(debouncedQuery),
    enabled: debouncedQuery.length >= 2,
    staleTime: 60_000,
  })

  return (
    <div className="flex flex-col h-full rounded-xl border border-border overflow-hidden">
      <div className="px-4 py-2.5 bg-muted/50 border-b border-border shrink-0 flex items-center gap-2">
        <div className="h-2 w-2 rounded-full bg-muted-foreground/40" />
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Product Search
        </p>
        {isFetching && (
          <span className="ml-auto h-3 w-3 rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground animate-spin" />
        )}
      </div>

      <div className="px-3 py-2.5 border-b border-border shrink-0">
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search by name, type, material…"
          className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
        />
      </div>


      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {debouncedQuery.length < 2 && (
          <p className="text-xs text-muted-foreground text-center mt-8">
            Type at least 2 characters to search
          </p>
        )}

        {isError && (
          <p className="text-xs text-destructive text-center mt-8">Search failed. Try again.</p>
        )}

        {data?.length === 0 && debouncedQuery.length >= 2 && !isFetching && (
          <p className="text-xs text-muted-foreground text-center mt-8">
            No products found for "{debouncedQuery}"
          </p>
        )}

        {!editorReady && debouncedQuery.length >= 2 && data && data.length > 0 && (
          <p className="text-xs text-muted-foreground text-center bg-muted/60 rounded-md py-2 px-3">
            Click in the draft to place your cursor, then insert
          </p>
        )}

        {data?.map(product => (
          <ProductCard
            key={product.sku}
            product={product}
            onInsert={onInsert}
            editorReady={editorReady}
            alreadyAdded={insertedSkus.has(product.sku.toUpperCase())}
          />
        ))}
      </div>
    </div>
  )
}
