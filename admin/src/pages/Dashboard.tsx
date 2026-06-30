import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import type { CallSession } from '../types'

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString('en-CA', { timeZone: 'America/Edmonton' })
}

export default function Dashboard() {
  const [stats, setStats] = useState({ calls: 0, placed: 0, avgLatency: 0, phone: 0, web: 0 })
  const [recent, setRecent] = useState<CallSession[]>([])

  useEffect(() => {
    async function load() {
      const since = new Date()
      since.setDate(since.getDate() - 7)

      const { data: sessions } = await supabase
        .from('call_sessions')
        .select('*')
        .gte('started_at', since.toISOString())
        .order('started_at', { ascending: false })

      const rows = (sessions ?? []) as CallSession[]
      const placed = rows.filter((r) => r.outcome === 'placed').length
      const latencies = rows.map((r) => r.avg_latency_ms).filter((n): n is number => n != null)
      const avgLatency = latencies.length
        ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)
        : 0

      setStats({
        calls: rows.length,
        placed,
        avgLatency,
        phone: rows.filter((r) => r.channel === 'phone').length,
        web: rows.filter((r) => r.channel === 'web').length,
      })
      setRecent(rows.slice(0, 8))
    }
    load()
  }, [])

  const completion = stats.calls ? Math.round((stats.placed / stats.calls) * 100) : 0

  return (
    <>
      <h2 style={{ marginTop: 0 }}>Overview — last 7 days</h2>
      <div className="stats">
        <div className="stat"><div className="label">Total calls</div><div className="value">{stats.calls}</div></div>
        <div className="stat"><div className="label">Orders placed</div><div className="value">{stats.placed}</div></div>
        <div className="stat"><div className="label">Completion</div><div className="value">{completion}%</div></div>
        <div className="stat"><div className="label">Avg latency</div><div className="value">{stats.avgLatency || '—'}<small style={{ fontSize: '0.9rem' }}> ms</small></div></div>
        <div className="stat"><div className="label">Phone / Web</div><div className="value">{stats.phone} / {stats.web}</div></div>
      </div>

      <h3>Recent calls</h3>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Channel</th>
            <th>Outcome</th>
            <th>Turns</th>
            <th>Duration</th>
          </tr>
        </thead>
        <tbody>
          {recent.map((c) => (
            <tr key={c.id}>
              <td><Link to={`/calls/${c.id}`}>{fmtTime(c.started_at)}</Link></td>
              <td><span className={`badge ${c.channel}`}>{c.channel}</span></td>
              <td><span className={`badge ${c.outcome ?? ''}`}>{c.outcome ?? '—'}</span></td>
              <td>{c.turn_count}</td>
              <td>{c.duration_seconds != null ? `${c.duration_seconds}s` : '—'}</td>
            </tr>
          ))}
          {!recent.length && (
            <tr><td colSpan={5} style={{ color: '#888' }}>No calls yet — make a test call after deploying the agent.</td></tr>
          )}
        </tbody>
      </table>
    </>
  )
}
