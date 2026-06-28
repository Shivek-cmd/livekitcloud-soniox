import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import {
  useDataChannel,
  useRoomContext,
  useVoiceAssistant,
} from '@livekit/components-react'
import type { CartRpcResult, OrderState } from '../lib/api'

interface CartApi {
  /** Latest order state from the agent, or null before the first sync. */
  state: OrderState | null
  /** True once the agent participant is present (RPCs/tap-to-add usable). */
  ready: boolean
  addItem: (id: string, qty?: number, modifiers?: string[]) => Promise<CartRpcResult>
  setQty: (id: string, qty: number) => Promise<CartRpcResult>
  removeItem: (id: string) => Promise<CartRpcResult>
}

const CartContext = createContext<CartApi | null>(null)
const decoder = new TextDecoder()

export function CartProvider({ children }: { children: ReactNode }) {
  const room = useRoomContext()
  const { agent } = useVoiceAssistant()
  const [state, setState] = useState<OrderState | null>(null)

  // Live push: agent broadcasts full order state on every cart change.
  useDataChannel('order.state', (msg) => {
    try {
      setState(JSON.parse(decoder.decode(msg.payload)) as OrderState)
    } catch {
      // ignore malformed packets
    }
  })

  // Resync on (re)connect: pull current state once the agent is present.
  useEffect(() => {
    if (!agent) {
      setState(null)
      return
    }
    let active = true
    room.localParticipant
      .performRpc({
        destinationIdentity: agent.identity,
        method: 'get_order_state',
        payload: '',
      })
      .then((res) => {
        if (active) setState(JSON.parse(res) as OrderState)
      })
      .catch(() => {
        /* agent not ready yet; live push will fill in */
      })
    return () => {
      active = false
    }
  }, [agent, room])

  const call = useCallback(
    async (method: string, payload: object): Promise<CartRpcResult> => {
      if (!agent) return { ok: false, error: 'not_connected' }
      try {
        const res = await room.localParticipant.performRpc({
          destinationIdentity: agent.identity,
          method,
          payload: JSON.stringify(payload),
        })
        const parsed = JSON.parse(res) as CartRpcResult
        if (parsed.state) setState(parsed.state)
        return parsed
      } catch (e) {
        return { ok: false, error: e instanceof Error ? e.message : 'rpc_failed' }
      }
    },
    [agent, room],
  )

  const api: CartApi = {
    state,
    ready: !!agent,
    addItem: (id, qty = 1, modifiers = []) =>
      call('cart_add', { item_id: id, qty, modifiers }),
    setQty: (id, qty) => call('cart_set_qty', { item_id: id, qty }),
    removeItem: (id) => call('cart_remove', { item_id: id }),
  }

  return <CartContext.Provider value={api}>{children}</CartContext.Provider>
}

export function useCart(): CartApi {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('useCart must be used within a CartProvider')
  return ctx
}
