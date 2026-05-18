import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { emailsApi } from '@/lib/api'
import type { ProductValidation } from '@/types/api'

export function useProductValidation(emailId: string) {
  return useQuery({
    queryKey: ['productValidation', emailId],
    queryFn: () => emailsApi.getValidation(emailId),
    enabled: !!emailId,
  })
}

export function useValidateProducts() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ emailId, body }: { emailId: string; body: { confirmed: string[]; rejected: string[] } }) =>
      emailsApi.validateProducts(emailId, body),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['productValidation', variables.emailId] })
    },
  })
}

export function useAddProduct() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ emailId, sku }: { emailId: string; sku: string }) =>
      emailsApi.addProduct(emailId, sku),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['productValidation', variables.emailId] })
    },
  })
}

export function useGenerateWithProducts() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ emailId, products }: { emailId: string; products: string[] }) =>
      emailsApi.generateWithProducts(emailId, { products }),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['productValidation', variables.emailId] })
      queryClient.invalidateQueries({ queryKey: ['emails'] })
    },
  })
}
