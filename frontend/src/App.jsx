import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [status, setStatus] = useState('Checking backend...')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setStatus(data.message))
      .catch(() => setStatus('Backend is not running'))
  }, [])

  return (
    <div className="app">
      <h1>Personal Retirement Assistant</h1>
      <p>Backend Status: {status}</p>
    </div>
  )
}

export default App
