import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import type { CallSession } from '../types'

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString('en-CA', { timeZone: 'America/Edmonton' })
}

export default function CallsList() {
  const [calls, setCalls] = useState<CallSession[]>([])
  const [filter, setFilter] = useState<'all' | 'phone' | 'web'>('all')

  useEffect(() => {
    async function load() {
      let q = supabase.from('call_sessions').select('*').order('started_at', { ascending: false }).limit(100)
      if (filter !== 'all') q = q.eq('channel', filter)
      const { data } = await q
      setCalls((data ?? []) as CallSession[])
    }
    load()
  }, [filter])

  return (
    <>
      <h2 style={{ marginTop: 0 }}>Calls</h2>
      <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem' }}>
        {(['all', 'phone', 'web'] as const).map((f) => (
          <button key={f} type="button" className={filter === f ? '' : 'secondary'} onClick={() => setFilter(f)}>
            {f === 'all' ? 'All' : f}
          </button>
        ))}
      </div>
      <table>
        <thead>
          <tr>
            <th>Started</th>
            <th>Channel</th>
            <th>Outcome</th>
            <th>Customer</th>
            <th>Turns</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {calls.map((c) => (
            <tr key={c.id}>
              <td><Link to={`/calls/${c.id}`}>{fmtTime(c.started_at)}</Link></td>
              <td><span className={`badge ${c.channel}`}>{c.channel}</span></td>
              <td>{c.outcome ?? '—'}</td>
              <td>{c.customer_name ?? c.caller_phone ?? '—'}</td>
              <td>{c.turn_count}</td>
              <td>{c.order_total != null ? `$${c.order_total}` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}
