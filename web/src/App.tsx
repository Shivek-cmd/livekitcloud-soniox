import { useState, useRef, useCallback } from 'react'
import { Room, RoomEvent, Track, ConnectionState } from 'livekit-client'
import './App.css'

const TOKEN_URL = '/token'

type CallState = 'idle' | 'connecting' | 'connected' | 'error'

export default function App() {
  const [callState, setCallState] = useState<CallState>('idle')
  const [agentSpeaking, setAgentSpeaking] = useState(false)
  const [micEnabled, setMicEnabled] = useState(true)
  const [errorMsg, setErrorMsg] = useState('')
  const roomRef = useRef<Room | null>(null)
  const audioEls = useRef<HTMLAudioElement[]>([])

  const startCall = useCallback(async () => {
    setCallState('connecting')
    setErrorMsg('')

    try {
      const resp = await fetch(TOKEN_URL)
      if (!resp.ok) throw new Error('Failed to get token')
      const { token, url } = await resp.json()

      const room = new Room({ adaptiveStream: true, dynacast: true })
      roomRef.current = room

      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) {
          const el = track.attach()
          el.autoplay = true
          document.body.appendChild(el)
          // Explicit play() because autoplay alone is blocked in many browsers
          el.play().catch(() => {})
          audioEls.current.push(el)
        }
      })

      room.on(RoomEvent.TrackUnsubscribed, (track) => {
        track.detach().forEach(el => el.remove())
      })

      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        const localIdentity = room.localParticipant.identity
        setAgentSpeaking(speakers.some(s => s.identity !== localIdentity))
      })

      room.on(RoomEvent.ConnectionStateChanged, (state) => {
        if (state === ConnectionState.Disconnected) {
          audioEls.current.forEach(el => el.remove())
          audioEls.current = []
          roomRef.current = null
          setCallState('idle')
          setAgentSpeaking(false)
          setMicEnabled(true)
        }
      })

      await room.connect(url, token)
      // Resume AudioContext — must be called in response to a user gesture
      await room.startAudio()
      await room.localParticipant.setMicrophoneEnabled(true, {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      })
      setCallState('connected')
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Connection failed')
      setCallState('error')
    }
  }, [])

  const endCall = useCallback(async () => {
    if (roomRef.current) {
      await roomRef.current.disconnect()
    }
  }, [])

  const toggleMic = useCallback(async () => {
    if (!roomRef.current) return
    const next = !micEnabled
    await roomRef.current.localParticipant.setMicrophoneEnabled(next)
    setMicEnabled(next)
  }, [micEnabled])

  return (
    <div className="app">
      <header className="header">
        <div className="restaurant-name">
          <h1>Bizbull Restaurant</h1>
          <p>ਪੰਜਾਬੀ ਖਾਣਾ · Punjabi Cuisine</p>
        </div>
      </header>

      <main className="main">
        <div className="card">
          <div className="tagline">
            <p>ਆਰਡਰ ਕਰੋ · ਟੇਬਲ ਬੁੱਕ ਕਰੋ · ਮੇਨੂ ਜਾਣੋ</p>
            <p className="tagline-en">Order · Reserve · Enquire</p>
          </div>

          {callState === 'idle' && (
            <button className="btn-call" onClick={startCall}>
              <span className="btn-icon">📞</span>
              <span>ਕਾਲ ਕਰੋ / Start Call</span>
            </button>
          )}

          {callState === 'connecting' && (
            <div className="status-box connecting">
              <div className="pulse-ring" />
              <span>ਜੋੜ ਰਹੇ ਹਾਂ...</span>
            </div>
          )}

          {callState === 'connected' && (
            <div className="connected-ui">
              <div className={`agent-indicator ${agentSpeaking ? 'speaking' : 'listening'}`}>
                <div className="waves">
                  <span /><span /><span /><span /><span />
                </div>
                <p>{agentSpeaking ? 'ਬੋਲ ਰਹੇ ਹਾਂ...' : 'ਸੁਣ ਰਹੇ ਹਾਂ...'}</p>
              </div>

              <div className="call-controls">
                <button
                  className={`btn-mic ${micEnabled ? 'on' : 'off'}`}
                  onClick={toggleMic}
                  title={micEnabled ? 'Mute' : 'Unmute'}
                >
                  {micEnabled ? '🎙️' : '🔇'}
                </button>
                <button className="btn-end" onClick={endCall}>
                  📵 ਕਾਲ ਖਤਮ ਕਰੋ
                </button>
              </div>
            </div>
          )}

          {callState === 'error' && (
            <div className="error-box">
              <p>⚠️ {errorMsg || 'ਕੁਝ ਗਲਤ ਹੋ ਗਿਆ।'}</p>
              <button className="btn-retry" onClick={() => setCallState('idle')}>
                ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ
              </button>
            </div>
          )}
        </div>

        <div className="hours">
          ਸੋਮਵਾਰ ਤੋਂ ਐਤਵਾਰ · ਸਵੇਰੇ 11 ਵਜੇ ਤੋਂ ਰਾਤ 11 ਵਜੇ ਤੱਕ
        </div>
      </main>
    </div>
  )
}
