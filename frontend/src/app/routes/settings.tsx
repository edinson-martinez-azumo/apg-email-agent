import { toast } from 'sonner'
import { useSettings, useUpdateSettings } from '@/hooks/useSettings'

const INTERVAL_OPTIONS = [
  { value: 30, label: '30 seconds' },
  { value: 60, label: '1 minute' },
  { value: 120, label: '2 minutes' },
  { value: 300, label: '5 minutes' },
  { value: 600, label: '10 minutes' },
] as const

export function SettingsPage() {
  const { data: settings, isLoading } = useSettings()
  const { mutateAsync: updateSettings } = useUpdateSettings()

  const handleToggle = async (checked: boolean) => {
    if (!settings) return
    try {
      await updateSettings({ ...settings, automated_mode: checked })
      toast.success(checked ? 'Automated mode enabled' : 'Automated mode disabled')
    } catch {
      toast.error('Failed to update settings')
    }
  }

  const handleIntervalChange = async (value: number) => {
    if (!settings) return
    try {
      await updateSettings({ ...settings, polling_interval_seconds: value })
      toast.success('Polling interval updated')
    } catch {
      toast.error('Failed to update interval')
    }
  }

  if (isLoading) {
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
      {/* Automated Mode */}
      <div className="rounded-xl border border-border bg-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Automated Mode</h2>
            <p className="text-sm text-muted-foreground mt-1">
              When enabled, the system automatically polls for new emails, generates AI drafts, and sends replies without manual intervention.
            </p>
          </div>
          <button
            onClick={() => handleToggle(!settings?.automated_mode)}
            disabled={isLoading}
            className={`relative inline-flex h-7 w-12 min-h-[28px] min-w-[48px] items-center rounded-full transition-colors duration-200 cursor-pointer ${
              settings?.automated_mode ? 'bg-primary' : 'bg-muted'
            } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
            aria-pressed={settings?.automated_mode}
          >
            <span
              className={`inline-block h-5 w-5 min-h-[20px] min-w-[20px] rounded-full bg-white shadow-sm transition-transform duration-200 ${
                settings?.automated_mode ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {settings?.automated_mode && (
          <div className="rounded-lg bg-primary/5 border border-primary/20 p-4 space-y-3">
            <div className="flex items-center gap-2">
              <div className="h-2.5 w-2.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-sm font-medium text-green-700">Active — polling every {settings.polling_interval_seconds}s</span>
            </div>
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
              disabled={isLoading || !settings?.automated_mode}
              className={`px-3 py-2.5 text-sm font-medium rounded-lg border transition-colors duration-150 cursor-pointer ${
                settings?.polling_interval_seconds === option.value
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-card text-foreground border-border hover:bg-muted'
              } ${isLoading || !settings?.automated_mode ? 'opacity-50 cursor-not-allowed' : ''}`}
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
          <li>When automated mode is ON, new pending emails are auto-processed (generate draft + send)</li>
          <li>When automated mode is OFF, emails stay pending for manual review</li>
          <li>The polling stops when you close the browser tab</li>
        </ul>
      </div>
    </div>
  )
}
