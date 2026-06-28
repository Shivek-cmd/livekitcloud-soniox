import { useCallback, useState } from 'react'
import { LiveKitRoom, RoomAudioRenderer } from '@livekit/components-react'
import { fetchToken } from '../lib/api'
import { SierraPanel } from './SierraPanel'
import { LiveMenu } from './LiveMenu'
import { OrderPanel } from './OrderPanel'

interface Connection {
  token: string
  url: string
}

export function OrderWithSierra() {
  const [conn, setConn] = useState<Connection | null>(null)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startCall = useCallback(async () => {
    setStarting(true)
    setError(null)
    try {
      const { token, url } = await fetchToken()
      setConn({ token, url })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the call')
      setStarting(false)
    }
  }, [])

  const handleDisconnected = useCallback(() => {
    setConn(null)
    setStarting(false)
  }, [])

  return (
    <LiveKitRoom
      serverUrl={conn?.url ?? ''}
      token={conn?.token ?? ''}
      connect={!!conn}
      audio={true}
      video={false}
      onDisconnected={handleDisconnected}
      onError={(e) => setError(e.message)}
      className="ows"
    >
      <RoomAudioRenderer />
      <div className="ows-grid">
        <SierraPanel started={!!conn} connecting={starting} onStart={startCall} error={error} />
        <LiveMenu />
        <OrderPanel connected={!!conn} />
      </div>
    </LiveKitRoom>
  )
}
