import { useEffect, useState } from 'react'
import {
  VideoTrack,
  VoiceAssistantControlBar,
  useVoiceAssistant,
  type AgentState,
} from '@livekit/components-react'

function stateLabel(state: AgentState, started: boolean): string {
  if (!started) return 'Tap to talk to Sierra'
  switch (state) {
    case 'connecting':
    case 'initializing':
      return 'Connecting…'
    case 'listening':
      return 'Listening…'
    case 'thinking':
      return 'Thinking…'
    case 'speaking':
      return 'Sierra is speaking'
    case 'disconnected':
      return started ? 'Connecting…' : 'Tap to talk to Sierra'
    default:
      return 'Ready'
  }
}

/** Soniox-demo style SVG face — mouth animates while speaking. */
function SierraFace({ isSpeaking }: { isSpeaking: boolean }) {
  const [mouthOpen, setMouthOpen] = useState(false)
  const [blinking, setBlinking] = useState(false)

  useEffect(() => {
    if (!isSpeaking) {
      setMouthOpen(false)
      return
    }
    const id = setInterval(() => setMouthOpen((o) => !o), 180)
    return () => clearInterval(id)
  }, [isSpeaking])

  useEffect(() => {
    const blink = () => {
      setBlinking(true)
      setTimeout(() => setBlinking(false), 120)
    }
    const id = setInterval(blink, 3800 + Math.random() * 1200)
    return () => clearInterval(id)
  }, [])

  const eyeHeight = blinking ? 1 : 7

  return (
    <svg viewBox="0 0 120 130" width="100%" height="100%" style={{ display: 'block' }}>
      <ellipse cx="60" cy="36" rx="38" ry="30" fill="#1C0A00" />
      <ellipse cx="60" cy="76" rx="34" ry="38" fill="#C88B5A" />
      <rect x="22" y="40" width="9" height="36" rx="5" fill="#1C0A00" />
      <rect x="89" y="40" width="9" height="36" rx="5" fill="#1C0A00" />
      <rect x="50" y="108" width="20" height="14" rx="5" fill="#C88B5A" />
      <path
        d="M 38 58 Q 46 53 54 57"
        stroke="#2D1000"
        strokeWidth="2.5"
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M 66 57 Q 74 53 82 58"
        stroke="#2D1000"
        strokeWidth="2.5"
        fill="none"
        strokeLinecap="round"
      />
      <ellipse cx="46" cy="68" rx="8" ry={eyeHeight} fill="white" />
      <ellipse cx="74" cy="68" rx="8" ry={eyeHeight} fill="white" />
      {!blinking && (
        <>
          <circle cx="47" cy="69" r="4.5" fill="#2D1000" />
          <circle cx="75" cy="69" r="4.5" fill="#2D1000" />
          <circle cx="48.5" cy="67" r="1.5" fill="white" />
          <circle cx="76.5" cy="67" r="1.5" fill="white" />
        </>
      )}
      <ellipse cx="60" cy="83" rx="5" ry="3" fill="#B87545" />
      {mouthOpen ? (
        <>
          <ellipse cx="60" cy="96" rx="10" ry="6.5" fill="#7A1A1A" />
          <rect x="52" y="91" width="16" height="5" rx="2.5" fill="#F5F0E8" />
        </>
      ) : (
        <path
          d="M 50 93 Q 60 101 70 93"
          stroke="#7A1A1A"
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
        />
      )}
      <circle cx="27" cy="79" r="3.5" fill="#F59E0B" />
      <circle cx="93" cy="79" r="3.5" fill="#F59E0B" />
      <path
        d="M 28 122 Q 60 116 92 122"
        stroke="#F59E0B"
        strokeWidth="3.5"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  )
}

function SierraAvatar({ state, started }: { state: AgentState; started: boolean }) {
  const isSpeaking = state === 'speaking'
  const isListening = state === 'listening'
  const isThinking = state === 'thinking'
  const isConnecting =
    state === 'connecting' || state === 'initializing' || (started && state === 'disconnected')
  const isActive = started && !isConnecting

  return (
    <div className={`sierra-avatar state-${state}${started ? ' started' : ''}`}>
      {isSpeaking && <div className="sierra-avatar-pulse" aria-hidden />}
      <div className={`sierra-avatar-ring ring-outer${isActive ? ' active' : ''}`} />
      <div className={`sierra-avatar-ring ring-inner${isActive ? ' active' : ''}`} />

      <div className={`sierra-avatar-face${isActive ? ' active' : ''}`}>
        <SierraFace isSpeaking={isSpeaking} />
      </div>

      {isListening && (
        <div className="sierra-wave" aria-hidden>
          {[0, 1, 2, 3, 4].map((i) => (
            <span key={i} style={{ animationDelay: `${i * 0.1}s`, height: `${4 + i * 3}px` }} />
          ))}
        </div>
      )}

      {(isThinking || isConnecting) && <div className="sierra-avatar-spin" aria-hidden />}
    </div>
  )
}

interface Props {
  started: boolean
  connecting: boolean
  onStart: () => void
  error: string | null
}

export function SierraPanel({ started, connecting, onStart, error }: Props) {
  const { state, videoTrack, agentTranscriptions } = useVoiceAssistant()
  const captions = (agentTranscriptions ?? []).slice(-2)

  return (
    <section className="panel sierra-panel" aria-label="Sierra">
      <div className="panel-title">Sierra</div>

      <div className="sierra-stage">
        {videoTrack ? (
          <VideoTrack trackRef={videoTrack} className="sierra-video" />
        ) : (
          <SierraAvatar state={state} started={started} />
        )}
        <div className={`sierra-state state-${state}`}>
          {connecting && !started ? 'Connecting…' : stateLabel(state, started)}
        </div>
      </div>

      <div className="sierra-captions" aria-live="polite">
        {captions.map((c) => (
          <p key={c.id} className="caption-line">
            {c.text}
          </p>
        ))}
      </div>

      <div className="sierra-controls">
        {!started ? (
          <button className="btn-call" onClick={onStart} disabled={connecting}>
            <span className="btn-icon" aria-hidden>
              🎙️
            </span>
            <span>{connecting ? 'Connecting…' : 'Start Call'}</span>
          </button>
        ) : (
          <VoiceAssistantControlBar />
        )}
        {error && <p className="sierra-error">⚠️ {error}</p>}
      </div>
    </section>
  )
}
