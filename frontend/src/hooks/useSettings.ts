import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsApi } from '@/lib/api'

export interface Settings {
  auto_sync: boolean
  auto_generate: boolean
  auto_send: boolean
  polling_interval_seconds: number
  draft_count: number
}

export interface SettingsUpdatePayload {
  auto_sync: boolean
  auto_generate: boolean
  auto_send: boolean
  polling_interval_seconds: number
}

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.get(),
  })
}

export function useUpdateSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: SettingsUpdatePayload) =>
      settingsApi.update(payload),
    onSuccess: (data) => {
      qc.setQueryData(['settings'], data)
    },
  })
}
