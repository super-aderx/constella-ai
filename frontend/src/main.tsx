import { Component, StrictMode, Suspense, type ReactNode } from "react"
import { createRoot } from "react-dom/client"
import "./index.css"
import App from "./App"

/** Shows why the page could not load (usually: the backend is not running) instead of a blank screen. */
class ErrorPanel extends Component<{ children: ReactNode }, { error?: Error }> {
  state: { error?: Error } = {}
  static getDerivedStateFromError = (error: Error) => ({ error })
  render() {
    if (!this.state.error) return this.props.children
    return <p className="p-8 text-ink-muted">{this.state.error.message}</p>
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorPanel>
      <Suspense fallback={<p className="p-8 text-ink-muted">Loading the network…</p>}>
        <App />
      </Suspense>
    </ErrorPanel>
  </StrictMode>,
)
