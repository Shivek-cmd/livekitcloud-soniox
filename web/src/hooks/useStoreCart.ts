import { useCallback, useMemo, useState } from 'react'
import {
  addToStoreCart,
  removeStoreCartLine,
  setStoreCartQty,
  storeCartItemCount,
  storeCartSubtotal,
  type AddToStoreCartInput,
  type StoreCartLine,
} from '../lib/storeCart'

export function useStoreCart() {
  const [lines, setLines] = useState<StoreCartLine[]>([])

  const addItem = useCallback((input: AddToStoreCartInput) => {
    setLines((prev) => addToStoreCart(prev, input))
  }, [])

  const setQty = useCallback((key: string, qty: number) => {
    setLines((prev) => setStoreCartQty(prev, key, qty))
  }, [])

  const removeItem = useCallback((key: string) => {
    setLines((prev) => removeStoreCartLine(prev, key))
  }, [])

  const clear = useCallback(() => setLines([]), [])

  const subtotal = useMemo(() => storeCartSubtotal(lines), [lines])
  const itemCount = useMemo(() => storeCartItemCount(lines), [lines])

  return {
    lines,
    addItem,
    setQty,
    removeItem,
    clear,
    subtotal,
    itemCount,
  }
}
