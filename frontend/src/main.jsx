import { Component } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import App from './App.jsx'

// Never show a blank page: surface render errors instead.
class Boundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(error) { return { error } }
  render() {
    if (this.state.error) {
      return (
        <div className="app"><div className="error">
          Something went wrong while drawing the page: {String(this.state.error.message || this.state.error)}
          <br />Try reloading. If it persists, check the browser console.
        </div></div>
      )
    }
    return this.props.children
  }
}

createRoot(document.getElementById('root')).render(<Boundary><App /></Boundary>)
