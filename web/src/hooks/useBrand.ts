// The displayed name and colour, from the server's brand config (never written in the web).
import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { appConfig } from '../config/app.ts'
import { api } from '../services/api/client.ts'


export function useBrand() {
  const query = useQuery({
    queryKey: ['meta', 'brand'],
    queryFn: ({ signal }) => api('get', 'meta/brand', { signal }),
    staleTime: appConfig.staleTime.static,
  })
  const brand = query.data
  useEffect(() => {
    if (!brand) return
    const root = document.documentElement.style
    root.setProperty('--brand', brand.primary_color)
    root.setProperty('--brand-dark', brand.primary_color_dark)
  }, [brand])
  return brand
}

/** Sets the tab title as "<page> · <brand>". */
export function useDocumentTitle(page: string): void {
  const brand = useBrand()
  useEffect(() => {
    document.title = brand ? (page ? `${page} · ${brand.name}` : brand.name) : page
  }, [brand, page])
}
