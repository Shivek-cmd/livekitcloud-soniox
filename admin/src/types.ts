export type CallSession = {
  id: string
  room_name: string
  channel: 'phone' | 'web'
  caller_phone: string | null
  started_at: string
  ended_at: string | null
  duration_seconds: number | null
  outcome: string | null
  turn_count: number
  order_total: number | null
  items_count: number
  avg_latency_ms: number | null
  customer_name: string | null
}

export type CallTurn = {
  id: string
  session_id: string
  turn_number: number
  user_stt: string | null
  sierra_spoken: string | null
  intent: string | null
  phase: string | null
  was_filtered: boolean
  filter_reason: string | null
  auto_add: boolean
  tools_called: unknown[]
  cart_snapshot: unknown
  latency: Record<string, unknown> | null
}

export type Order = {
  id: string
  session_id: string | null
  channel: string
  placed_at: string
  status: string
  order_type: string | null
  total: number | null
  customer_name: string | null
  customer_phone: string | null
  items: unknown[]
}
