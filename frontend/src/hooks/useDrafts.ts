import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { draftsApi } from '@/lib/api'

export function useDraft(id: string) {
  return useQuery({
    queryKey: ['drafts', id],
    queryFn: () => draftsApi.get(id),
    enabled: !!id,
  })
}

export function useDraftByEmail(emailId: string) {
  return useQuery({
    queryKey: ['drafts', 'by-email', emailId],
    queryFn: () => draftsApi.getByEmailId(emailId),
    enabled: !!emailId,
  })
}

export function useUpdateDraft() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, editedBody }: { id: string; editedBody: string }) =>
      draftsApi.update(id, editedBody),
    onSuccess: (data) => {
      qc.setQueryData(['drafts', data.id], data)
    },
  })
}

export function useApproveDraft() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => draftsApi.approve(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['drafts'] })
    },
  })
}

export function useSendDraft() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => draftsApi.send(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['drafts'] })
    },
  })
}

export function useDiscardDraft() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => draftsApi.discard(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['drafts'] })
    },
  })
}
