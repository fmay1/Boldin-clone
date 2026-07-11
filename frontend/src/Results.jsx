import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, Area, ResponsiveContainer } from 'recharts'

function Results() {
  const [scenarios, setScenarios] = useState([])
  const [selectedScenarioId, setSelectedScenarioId] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')

  // Fetch available scenarios on mount
  useEffect(() => {
    fetch('/api/scenarios')
      .then(res => res.json())
      .then(data => setScenarios(data))
      .catch(err => setError('Failed to load scenarios'))
  }, [])

  // Fetch projection when a scenario is selected
  useEffect(() => {
    if (!selectedScenarioId) {
      setResults([])
      setError('')
      setWarning('')
      return
    }
    
    setLoading(true)
    setError('')
    setWarning('')
    setResults([])
    
    fetch(`/api/projection/${selectedScenarioId}`)
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          setError(data.error)
        } else {
          setResults(data.results || [])
          if (data.warning) setWarning(data.warning)
        }
      })
      .catch(err => setError('Failed to fetch projection'))
      .finally(() => setLoading(false))
  }, [selectedScenarioId])

  const formatCurrency = (val) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val)
  }

  return (
    <div className="results-container" style={{ padding: '20px' }}>
      <h2>Projection Results</h2>
      
      <div style={{ marginBottom: '20px' }}>
        <label htmlFor="scenario-select" style={{ marginRight: '10px', fontWeight: 'bold' }}>Select Scenario:</label>
        <select 
          id="scenario-select" 
          value={selectedScenarioId} 
          onChange={(e) => setSelectedScenarioId(e.target.value)}
          style={{ padding: '8px', fontSize: '14px' }}
        >
          <option value="">-- Choose a scenario --</option>
          {scenarios.map(s => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </div>

      {error && <div style={{ color: '#721c24', backgroundColor: '#f8d7da', padding: '10px', borderRadius: '4px', marginBottom: '15px' }}>{error}</div>}
      {warning && <div style={{ color: '#856404', backgroundColor: '#fff3cd', border: '1px solid #ffeeba', padding: '10px', borderRadius: '4px', marginBottom: '15px' }}>{warning}</div>}

      {loading && <p>Loading projection...</p>}

      {!loading && results.length > 0 && (
        <>
          <div style={{ width: '100%', height: 400, marginBottom: '20px' }}>
            <ResponsiveContainer>
              <LineChart data={results}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="age" label={{ value: 'Age', position: 'insideBottomRight', offset: -5 }} />
                <YAxis tickFormatter={(val) => `$${(val / 1000000).toFixed(1)}M`} />
                <Tooltip formatter={(val) => formatCurrency(val)} />
                <Legend />
                {/* Confidence band: overlapping areas create a shaded region */}
                <Area type="monotone" dataKey="ci95_high" stroke="none" fill="#8884d8" fillOpacity={0.15} name="95% CI Upper" />
                <Area type="monotone" dataKey="ci95_low" stroke="none" fill="#8884d8" fillOpacity={0.15} name="95% CI Lower" />
                <Line type="monotone" dataKey="mean_balance" stroke="#8884d8" name="Mean Balance" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #ddd' }}>
                  <th style={{ padding: '8px', textAlign: 'left' }}>Age</th>
                  <th style={{ padding: '8px', textAlign: 'right' }}>Mean Balance</th>
                  <th style={{ padding: '8px', textAlign: 'right' }}>95% CI Low</th>
                  <th style={{ padding: '8px', textAlign: 'right' }}>95% CI High</th>
                </tr>
              </thead>
              <tbody>
                {results.map((row, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #eee' }}>
                    <td style={{ padding: '8px' }}>{row.age}</td>
                    <td style={{ padding: '8px', textAlign: 'right' }}>{formatCurrency(row.mean_balance)}</td>
                    <td style={{ padding: '8px', textAlign: 'right' }}>{formatCurrency(row.ci95_low)}</td>
                    <td style={{ padding: '8px', textAlign: 'right' }}>{formatCurrency(row.ci95_high)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

export default Results
