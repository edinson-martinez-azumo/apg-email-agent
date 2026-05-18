import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react'
import { pollApi } from '@/lib/api'
import { useEmails } from './useEmails'
import type { PollStatus } from '@/types/api'

interface PollingContextValue {
  lastResult: PollStatus & { new_emails: number; processed_count: number } | null
  lastPollAt: Date | null
  error: Error | null
  isPolling: boolean
  manualPoll: () => Promise<void>
}

const PollingContext = createContext<PollingContextValue | null>(null)

export function usePollingContext() {
  const ctx = useContext(PollingContext)
  if (!ctx) {
    throw new Error('usePollingContext must be used within <PollingProvider>')
  }
  return ctx
}

/**
 * usePolling - Background polling hook for automated email processing.
 *
 * When automatedMode is true, polls the backend every intervalMs milliseconds.
 * Automatically refreshes the email list after each poll.
 *
 * @param automatedMode - Whether automated mode is enabled
 * @param intervalMs - Polling interval in milliseconds
 */
export function usePolling(
  automatedMode: boolean,
  intervalMs: number,
) {
  const { refetch: refetchEmails } = useEmails()
  const lastResultRef = useRef<PollStatus & { new_emails: number; processed_count: number } | null>(null)
  const lastPollAtRef = useRef<Date | null>(null)
  const errorRef = useRef<Error | null>(null)
  const isFetchingRef = useRef(false)

  const poll = useCallback(async () => {
    if (isFetchingRef.current) return
    isFetchingRef.current = true

    try {
      const result = await pollApi.trigger()
      lastResultRef.current = result
      lastPollAtRef.current = new Date()
      errorRef.current = null

      // Refresh email list after successful poll
      await refetchEmails()
    } catch (err) {
      errorRef.current = err instanceof Error ? err : new Error(String(err))
      lastPollAtRef.current = new Date()
      console.error('Poll failed:', err)
    } finally {
      isFetchingRef.current = false
    }
  }, [refetchEmails])

  // Poll once on mount if automated mode is on
  useEffect(() => {
    if (!automatedMode) return
    poll()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Set up interval - recreated when automatedMode or intervalMs changes
  useEffect(() => {
    if (!automatedMode) return

    const intervalId = setInterval(poll, intervalMs)
    return () => clearInterval(intervalId)
  }, [automatedMode, intervalMs, poll])

  return {
    lastPollAt: lastPollAtRef.current,
    lastResult: lastResultRef.current,
    error: errorRef.current,
  }
}

export function PollingProvider({ children }: { children: React.ReactNode }) {
  const [lastResult, setLastResult] = useState<PollStatus & { new_emails: number; processed_count: number } | null>(null)
  const [lastPollAt, setLastPollAt] = useState<Date | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [isPolling, setIsPolling] = useState(false)

  const { refetch: refetchEmails } = useEmails()
  const isFetchingRef = useRef(false)

  const manualPoll = useCallback(async () => {
    if (isFetchingRef.current) return
    setIsPolling(true)
    isFetchingRef.current = true

    try {
      const result = await pollApi.trigger()
      setLastResult(result)
      setLastPollAt(new Date())
      setError(null)
      await refetchEmails()
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
      setLastPollAt(new Date())
    } finally {
      setIsPolling(false)
      isFetchingRef.current = false
    }
  }, [refetchEmails])

  return (
    <PollingContext.Provider value={{ lastResult, lastPollAt, error, isPolling, manualPoll }}>
      {children}
    </PollingContext.Provider>
  )
}
