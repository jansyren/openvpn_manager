import { useToast } from 'primevue/usetoast'

/**
 * Shared toast helpers for API interactions. `error()` unwraps the normalized
 * error shape produced by the axios client ({ status, detail }) so views no
 * longer repeat `(e as { detail?: string }).detail ?? '...'` everywhere.
 */
export function useApiToast() {
  const toast = useToast()

  function error(e: unknown, fallback = 'Something went wrong'): void {
    const detail = (e as { detail?: string } | null)?.detail ?? fallback
    toast.add({ severity: 'error', summary: 'Error', detail, life: 4000 })
  }

  function success(detail: string, summary = 'Success'): void {
    toast.add({ severity: 'success', summary, detail, life: 3000 })
  }

  return { toast, error, success }
}
