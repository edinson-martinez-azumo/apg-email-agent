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

export function useEmailIntent(emailId: string) {
  return useQuery({
    queryKey: ['emails', emailId, 'intent'],
    queryFn: () => emailsApi.intent(emailId),
    enabled: !!emailId,
    staleTime: Infinity,
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

export function useAnalyzeEmail() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (emailId: string) => emailsApi.analyze(emailId),
    onSuccess: (_, emailId) => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['emails', emailId, 'detected-products'] })
    },
  })
}

export function useReAnalyzeEmail() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (emailId: string) => emailsApi.reAnalyze(emailId),
    onSuccess: (_, emailId) => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['emails', emailId, 'detected-products'] })
    },
  })
}

export function useBackToReviewed() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (emailId: string) => emailsApi.backToReviewed(emailId),
    onSuccess: (_, emailId) => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['drafts', 'by-email', emailId] })
    },
  })
}
