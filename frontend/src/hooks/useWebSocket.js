import { useEffect, useRef, useState, useCallback } from 'react'
import { WS_URL } from '../services/api'

/**
 * Connects to the IBVAP WebSocket and dispatches incoming messages by type.
 * Auto-reconnects on disconnect. Returns current connection status and
 * a registration function for message-type listeners.
 */
export function useWebSocket() {
  const [status, setStatus] = useState('CONNECTING') // CONNECTING | CONNECTED | DISCONNECTED
  const wsRef = useRef(null)
  const listenersRef = useRef({})
  const reconnectTimer = useRef(null)

  const on = useCallback((type, callback) => {
    if (!listenersRef.current[type]) listenersRef.current[type] = new Set()
    listenersRef.current[type].add(callback)
    return () => listenersRef.current[type]?.delete(callback)
  }, [])

  useEffect(() => {
    let closedByEffect = false

    let retryDelay = 1000

    function connect() {
      const token = localStorage.getItem('ibvap_token')
      if (!token) {
        setStatus('DISCONNECTED')
        return
      }
      const ws = new WebSocket(`${WS_URL}?token=${token}`)
      wsRef.current = ws

      ws.onopen = () => {
        setStatus('CONNECTED')
        retryDelay = 1000
      }
      ws.onclose = (event) => {
        setStatus('DISCONNECTED')
        if (event.code === 4401) {
          // Token is rejected or expired; do not flood server with reconnects
          return
        }
        if (!closedByEffect) {
          reconnectTimer.current = setTimeout(connect, retryDelay)
          retryDelay = Math.min(15000, retryDelay * 1.5)
        }
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          const callbacks = listenersRef.current[msg.type]
          if (callbacks) callbacks.forEach((cb) => cb(msg.data))
          const allCallbacks = listenersRef.current['*']
          if (allCallbacks) allCallbacks.forEach((cb) => cb(msg))
        } catch (e) { /* ignore malformed message */ }
      }
    }

    connect()

    return () => {
      closedByEffect = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [])

  return { status, on }
}
