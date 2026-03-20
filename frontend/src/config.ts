/**
 * Central config — resolves API and WebSocket base URLs from env vars.
 * Set VITE_API_URL in Render environment variables to your backend service URL.
 * e.g. VITE_API_URL=https://your-backend.onrender.com
 */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

// Convert http(s) -> ws(s) for WebSocket connections
const WS_BASE = API_BASE.replace("https://", "wss://").replace("http://", "ws://")

export const API_URL = API_BASE
export const WS_URL = WS_BASE
