import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import type { Order } from '../types'

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString('en-CA', { timeZone: 'America/Edmonton' })
}

export default function Orders() {
  const [orders, setOrders] = useState<Order[]>([])

  useEffect(() => {
    async function load() {
      const { data } = await supabase
        .from('orders')
        .select('*')
        .order('placed_at', { ascending: false })
        .limit(100)
      setOrders((data ?? []) as Order[])
    }
    load()
  }, [])

  return (
    <>
      <h2 style={{ marginTop: 0 }}>Orders</h2>
      <table>
        <thead>
          <tr>
            <th>Placed</th>
            <th>Channel</th>
            <th>Customer</th>
            <th>Type</th>
            <th>Total</th>
            <th>Status</th>
            <th>Session</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id}>
              <td>{fmtTime(o.placed_at)}</td>
              <td>{o.channel}</td>
              <td>{o.customer_name ?? '—'}</td>
              <td>{o.order_type ?? '—'}</td>
              <td>{o.total != null ? `$${o.total}` : '—'}</td>
              <td>{o.status}</td>
              <td>{o.session_id ? <Link to={`/calls/${o.session_id}`}>View call</Link> : '—'}</td>
            </tr>
          ))}
          {!orders.length && (
            <tr><td colSpan={7} style={{ color: '#888' }}>No orders logged yet.</td></tr>
          )}
        </tbody>
      </table>
    </>
  )
}
