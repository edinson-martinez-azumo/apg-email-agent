import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { emailsApi } from '@/lib/api'

export function useEmails(status?: string, page = 1) {
  return useQuery({
    queryKey: ['emails', status, page],
    queryFn: () => emailsApi.list(status, page),
  })
}

export function useEmail(id: string) {
  return useQuery({
    queryKey: ['emails', id],
    queryFn: () => emailsApi.get(id),
    enabled: !!id,
  })
}

export function useSyncEmails() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => emailsApi.sync(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['emails'] })
    },
  })
}

export function useGenerateDraft() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (emailId: string) => emailsApi.generate(emailId),
    onSuccess: (_, emailId) => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['drafts', 'by-email', emailId] })
    },
  })
}

export function useDiscardEmail() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (emailId: string) => emailsApi.discard(emailId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['emails'] })
    },
  })
}
