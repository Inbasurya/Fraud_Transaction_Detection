import { Component, ReactNode } from 'react'

interface Props {
  children: ReactNode
  pageName: string
}

interface State {
  hasError: boolean
  error: string
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: '' }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error: error.message }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '40px', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', height: '60vh',
          gap: '12px'
        }}>
          <div style={{ fontSize: '14px', fontWeight: 700, color: '#CF222E' }}>
            {this.props.pageName} failed to render
          </div>
          <div style={{
            fontSize: '12px', color: '#57606A',
            fontFamily: 'monospace', background: '#F6F8FA',
            padding: '12px', borderRadius: '8px', maxWidth: '600px',
            wordBreak: 'break-all' as const
          }}>
            {this.state.error}
          </div>
          <button
            onClick={() => this.setState({ hasError: false, error: '' })}
            style={{
              padding: '8px 16px', borderRadius: '6px',
              background: '#0969DA', color: 'white',
              border: 'none', cursor: 'pointer', fontSize: '12px',
              fontWeight: 600
            }}
          >
            Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
