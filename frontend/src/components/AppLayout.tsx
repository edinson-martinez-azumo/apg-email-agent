import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { pollApi } from '@/lib/api'
import { useSettings } from '@/hooks/useSettings'

export function AppLayout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { data: settings, isLoading: settingsLoading } = useSettings()
  const queryClient = useQueryClient()
  const [lastPollAt, setLastPollAt] = useState<Date | null>(null)
  const [isPolling, setIsPolling] = useState(false)

  const isAutomationActive = settings && (settings.auto_sync || settings.auto_generate || settings.auto_send)
  const intervalMs = (settings?.polling_interval_seconds ?? 60) * 1000
  const intervalRef = useRef<number | null>(null)
  const isFetchingRef = useRef(false)

  const doPoll = useCallback(async (force = false) => {
    if (isFetchingRef.current) return
    if (!force && !isAutomationActive) return
    isFetchingRef.current = true
    if (force) setIsPolling(true)

    try {
      await pollApi.trigger(force)
      setLastPollAt(new Date())
      await queryClient.invalidateQueries({ queryKey: ['emails'] })
    } catch (err) {
      setLastPollAt(new Date())
      console.error('Poll failed:', err)
    } finally {
      isFetchingRef.current = false
      if (force) setIsPolling(false)
    }
  }, [isAutomationActive, queryClient])

  // Poll once on mount if automation is active
  useEffect(() => {
    if (!isAutomationActive) return
    doPoll()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Set up polling interval
  useEffect(() => {
    if (!isAutomationActive) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      return
    }

    intervalRef.current = window.setInterval(doPoll, intervalMs)
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [isAutomationActive, intervalMs, doPoll])

  const handleManualPoll = useCallback(async () => {
    await doPoll(true)
  }, [doPoll])

  const secondsSinceLastPoll = lastPollAt
    ? Math.floor((Date.now() - lastPollAt.getTime()) / 1000)
    : null

  return (
    <div className="min-h-screen bg-background">
      {/* Header with nav */}
      <header className="sticky top-0 z-10 border-b border-border" style={{ backgroundColor: 'rgb(18, 118, 189)' }}>
        <div className="mx-auto max-w-5xl px-4 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/APG-logo.svg" alt="APG Logo" className="h-8 w-auto" />
            <nav className="flex items-center gap-1 ml-4">
              {['/inbox', '/dashboard', '/demo', '/settings'].map(path => {
                const labels: Record<string, string> = { '/inbox': 'Inbox', '/dashboard': 'Dashboard', '/demo': 'Demo', '/settings': 'Settings' }
                return (
                  <button
                    key={path}
                    onClick={() => navigate(path)}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors duration-150 cursor-pointer ${
                      location.pathname === path
                        ? 'bg-white/20 text-white'
                        : 'text-white/70 hover:text-white hover:bg-white/10'
                    }`}
                  >
                    {labels[path]}
                  </button>
                )
              })}
            </nav>
          </div>

          {/* Polling status + manual refresh */}
          <div className="flex items-center gap-3">
            {isAutomationActive && !settingsLoading && settings && (
              <div className="flex items-center gap-2">
                <div className="h-2.5 w-2.5 rounded-full bg-green-500 animate-pulse" />
                <span className="text-xs text-white/80">
                  {settings.auto_sync && settings.auto_generate && settings.auto_send
                    ? 'Auto'
                    : [
                        settings.auto_sync && 'sync',
                        settings.auto_generate && 'generate',
                        settings.auto_send && 'send',
                      ].filter(Boolean).join(' + ')}
                  {' '}polling{' '}
                  {secondsSinceLastPoll !== null && `(${secondsSinceLastPoll}s ago)`}
                </span>
              </div>
            )}
            <button
              onClick={handleManualPoll}
              disabled={isPolling}
              className="text-white/80 hover:text-white transition-colors duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              title="Sync emails"
            >
              {isPolling
                ? <span className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin block" />
                : (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                )
              }
            </button>
          </div>
        </div>
      </header>

      <main>{children}</main>
    </div>
  )
}
