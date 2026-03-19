/**
 * WebSocket manager — auto-reconnect with exponential backoff.
 * Provides a single subscription API for React components.
 */

const defaultWsBase = (() => {
  if (typeof window === 'undefined') return 'ws://127.0.0.1:8000'
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${window.location.host}`
})()

const WS_BASE = import.meta.env.VITE_WS_BASE_URL || defaultWsBase

export const WS_URLS = {
  stream: `${WS_BASE}/ws/stream`,
  alerts: `${WS_BASE}/ws/alerts`,
}

export function createWSConnection(url, { onMessage, onStatus }) {
  let ws = null
  let reconnectTimer = null
  let attempt = 0
  let closed = false

  function connect() {
    if (closed) return
    ws = new WebSocket(url)

    ws.onopen = () => {
      attempt = 0
      onStatus?.('connected')
      ws.send('ping')
    }

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)
        onMessage?.(data)
      } catch { /* ignore non-JSON */ }
    }

    ws.onerror = () => onStatus?.('error')

    ws.onclose = () => {
      onStatus?.('disconnected')
      if (!closed) {
        const delay = Math.min(1000 * 2 ** attempt, 10000)
        attempt++
        reconnectTimer = setTimeout(connect, delay)
      }
    }
  }

  connect()

  return {
    close() {
      closed = true
      clearTimeout(reconnectTimer)
      ws?.close()
    },
    send(data) {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(typeof data === 'string' ? data : JSON.stringify(data))
      }
    },
  }
}
