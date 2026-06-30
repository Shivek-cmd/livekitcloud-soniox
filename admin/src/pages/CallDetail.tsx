import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import type { CallSession, CallTurn } from '../types'

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString('en-CA', { timeZone: 'America/Edmonton' })
}

export default function CallDetail() {
  const { id } = useParams<{ id: string }>()
  const [session, setSession] = useState<CallSession | null>(null)
  const [turns, setTurns] = useState<CallTurn[]>([])

  useEffect(() => {
    if (!id) return
    async function load() {
      const [{ data: s }, { data: t }] = await Promise.all([
        supabase.from('call_sessions').select('*').eq('id', id).single(),
        supabase.from('call_turns').select('*').eq('session_id', id).order('turn_number'),
      ])
      setSession(s as CallSession)
      setTurns((t ?? []) as CallTurn[])
    }
    load()
  }, [id])

  if (!session) return <p>Loading…</p>

  return (
    <>
      <p><Link to="/calls">← Calls</Link></p>
      <h2 style={{ marginTop: 0 }}>Call {session.room_name}</h2>
      <p style={{ color: '#888' }}>
        {fmtTime(session.started_at)} · {session.channel} · {session.outcome ?? '—'}
        {session.duration_seconds != null && ` · ${session.duration_seconds}s`}
        {session.avg_latency_ms != null && ` · ${session.avg_latency_ms}ms avg`}
      </p>

      <h3>Transcript ({turns.length} turns)</h3>
      <div className="turn-list">
        {turns.map((t) => (
          <div key={t.id} className={`turn ${t.was_filtered ? 'filtered' : ''}`}>
            <div className="turn-meta">
              Turn {t.turn_number}
              {t.intent && ` · ${t.intent}`}
              {t.phase && ` · ${t.phase}`}
              {t.was_filtered && ` · filtered (${t.filter_reason})`}
              {t.auto_add && ' · auto-add'}
            </div>
            {t.user_stt && <div className="turn-user"><strong>Caller:</strong> {t.user_stt}</div>}
            {t.sierra_spoken && <div className="turn-sierra"><strong>Sierra:</strong> {t.sierra_spoken}</div>}
            {!!t.tools_called?.length && (
              <div style={{ fontSize: '0.8rem', color: '#666', marginTop: '0.35rem' }}>
                Tools: {(t.tools_called as { name: string }[]).map((x) => x.name).join(', ')}
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  )
}
