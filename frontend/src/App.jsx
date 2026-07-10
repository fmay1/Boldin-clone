import { useState } from 'react'
import Accounts from './Accounts.jsx'
import HistoricalReturns from './HistoricalReturns.jsx'
import './App.css'

function App() {
  const [activePage, setActivePage] = useState('accounts')

  return (
    <div className="app">
      <h1>Personal Retirement Assistant</h1>
      <nav className="nav">
        <button className={activePage === 'accounts' ? 'active' : ''} onClick={() => setActivePage('accounts')}>Accounts</button>
        <button className={activePage === 'returns' ? 'active' : ''} onClick={() => setActivePage('returns')}>Historical Returns</button>
      </nav>
      <div className="page-content">
        {activePage === 'accounts' && <Accounts />}
        {activePage === 'returns' && <HistoricalReturns />}
      </div>
    </div>
  )
}

export default App
