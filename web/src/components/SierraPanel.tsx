import {
  BarVisualizer,
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

interface Props {
  started: boolean
  connecting: boolean
  onStart: () => void
  error: string | null
}

export function SierraPanel({ started, connecting, onStart, error }: Props) {
  const { state, audioTrack, videoTrack, agentTranscriptions } = useVoiceAssistant()
  const captions = (agentTranscriptions ?? []).slice(-2)

  return (
    <section className="panel sierra-panel" aria-label="Sierra">
      <div className="panel-title">Sierra</div>

      <div className="sierra-stage">
        {videoTrack ? (
          <VideoTrack trackRef={videoTrack} className="sierra-video" />
        ) : (
          <div className={`sierra-orb state-${state}`}>
            <BarVisualizer
              state={state}
              trackRef={audioTrack}
              barCount={5}
              className="sierra-viz"
            />
          </div>
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
            <span>{connecting ? 'ਜੋੜ ਰਹੇ ਹਾਂ…' : 'ਕਾਲ ਕਰੋ / Start Call'}</span>
          </button>
        ) : (
          <VoiceAssistantControlBar />
        )}
        {error && <p className="sierra-error">⚠️ {error}</p>}
      </div>
    </section>
  )
}
