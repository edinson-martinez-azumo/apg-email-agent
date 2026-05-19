import { toast } from 'sonner'
import { useSettings, useUpdateSettings } from '@/hooks/useSettings'
import type { Settings } from '@/hooks/useSettings'

const INTERVAL_OPTIONS = [
  { value: 30, label: '30 seconds' },
  { value: 60, label: '1 minute' },
  { value: 120, label: '2 minutes' },
  { value: 300, label: '5 minutes' },
  { value: 600, label: '10 minutes' },
] as const

const TOGGLE_OPTIONS = [
  { key: 'auto_sync' as const, label: 'Auto-sync', description: 'Automatically pull new emails from Gmail' },
  { key: 'auto_generate' as const, label: 'Auto-draft', description: 'Automatically generate AI drafts for new emails' },
  { key: 'auto_send' as const, label: 'Auto-send', description: 'Automatically send generated drafts without manual review' },
] as const

export function SettingsPage() {
  const { data: settings, isLoading } = useSettings()
  const { mutateAsync: updateSettings } = useUpdateSettings()

  const handleToggle = async (key: keyof Settings, checked: boolean) => {
    if (!settings) return
    try {
      const { draft_count: _, ...updateData } = settings
      await updateSettings({ ...updateData, [key]: checked })
      toast.success(`${TOGGLE_OPTIONS.find(o => o.key === key)?.label} ${checked ? 'enabled' : 'disabled'}`)
    } catch {
      toast.error('Failed to update settings')
    }
  }

  const handleIntervalChange = async (value: number) => {
    if (!settings) return
    try {
      const { draft_count: _, ...updateData } = settings
      await updateSettings({ ...updateData, polling_interval_seconds: value })
      toast.success('Polling interval updated')
    } catch {
      toast.error('Failed to update interval')
    }
  }

  const handleResetAll = async () => {
    if (!settings) return
    try {
      const { draft_count: _, ...updateData } = settings
      await updateSettings({ ...updateData, auto_sync: true, auto_generate: false, auto_send: false })
      toast.success('Settings reset to defaults')
    } catch {
      toast.error('Failed to reset settings')
    }
  }

  if (isLoading || !settings) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-48 bg-muted rounded" />
          <div className="h-32 bg-muted rounded-xl" />
          <div className="h-32 bg-muted rounded-xl" />
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 space-y-6">
      {/* Automated Mode Toggles */}
      <div className="rounded-xl border border-border bg-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Automated Mode</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Configure which steps run automatically. Toggle each step independently.
            </p>
          </div>
          <button
            onClick={handleResetAll}
            disabled={isLoading}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors duration-150 cursor-pointer disabled:opacity-50"
          >
            Reset to defaults
          </button>
        </div>

        <div className="space-y-3">
          {TOGGLE_OPTIONS.map((option) => {
            const checked = settings?.[option.key] ?? false
            const hasCounter = settings && option.key === 'auto_generate' && settings.draft_count > 0
            return (
              <div key={option.key} className="flex items-center justify-between rounded-lg border border-border p-3">
                <div>
                  <p className="text-sm font-medium">
                    {option.label}
                    {hasCounter && (
                      <span className="ml-2 text-xs font-normal text-primary">({settings.draft_count} pending)</span>
                    )}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">{option.description}</p>
                </div>
                <button
                  onClick={() => handleToggle(option.key, !checked)}
                  disabled={isLoading}
                  className={`relative inline-flex h-7 w-12 min-h-[28px] min-w-[48px] items-center rounded-full transition-colors duration-200 cursor-pointer ${
                    checked ? 'bg-primary' : 'bg-muted'
                  } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                  aria-pressed={checked}
                >
                  <span
                    className={`inline-block h-5 w-5 min-h-[20px] min-w-[20px] rounded-full bg-white shadow-sm transition-transform duration-200 ${
                      checked ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            )
          })}
        </div>

        {/* Active status indicator */}
        {settings && (settings.auto_sync || settings.auto_generate || settings.auto_send) && (
          <div className="rounded-lg bg-primary/5 border border-primary/20 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <div className="h-2.5 w-2.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-sm font-medium text-green-700">
                Automation active — {TOGGLE_OPTIONS.filter(o => settings[o.key]).map(o => o.label).join(' + ')}
              </span>
            </div>
            <p className="text-xs text-green-600/70">
              {settings.auto_sync && settings.auto_generate && settings.auto_send
                ? 'Fully automatic — emails will be synced, drafted, and sent without any manual intervention.'
                : settings.auto_send && settings.auto_generate
                  ? 'Drafts will be generated and sent automatically, but you need to trigger a sync first.'
                  : settings.auto_generate
                    ? 'Drafts will be generated automatically, but you need to trigger a sync first.'
                    : settings.auto_send
                      ? 'Drafts will be sent automatically when they are approved, but you need to trigger a sync and generate first.'
                      : ''}
            </p>
          </div>
        )}
      </div>

      {/* Polling Interval */}
      <div className="rounded-xl border border-border bg-card p-6 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Polling Interval</h2>
          <p className="text-sm text-muted-foreground mt-1">
            How often the system checks for new emails. Shorter intervals mean faster responses but more API calls.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {INTERVAL_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => handleIntervalChange(option.value)}
              disabled={isLoading}
              className={`px-3 py-2.5 text-sm font-medium rounded-lg border transition-colors duration-150 cursor-pointer ${
                settings?.polling_interval_seconds === option.value
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-card text-foreground border-border hover:bg-muted'
              } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {option.label}
            </button>
          ))}
        </div>

        <p className="text-xs text-muted-foreground">
          Note: Automated polling only works while the browser tab is open. Closing the tab stops the polling.
        </p>
      </div>

      {/* Info */}
      <div className="rounded-xl border border-border bg-muted/30 p-4 space-y-2">
        <h3 className="text-sm font-medium">How it works</h3>
        <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
          <li>The browser polls the backend every {settings?.polling_interval_seconds || 60} seconds</li>
          <li><strong>Auto-sync:</strong> pulls new emails from Gmail automatically</li>
          <li><strong>Auto-generate:</strong> creates AI drafts for pending emails automatically</li>
          <li><strong>Auto-send:</strong> sends approved drafts without manual review</li>
          <li>Any combination works — enable only the steps you need</li>
        </ul>
      </div>
    </div>
  )
}
