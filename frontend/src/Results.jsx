import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

function Results() {
  const [scenarios, setScenarios] = useState([])
  const [selectedScenarioId, setSelectedScenarioId] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [earlyAccessWarning, setEarlyAccessWarning] = useState('')
  const [refresh, setRefresh] = useState(0)

  // Fetch available scenarios on mount
  useEffect(() => {
    fetch('/api/scenarios')
      .then(res => res.json())
      .then(data => setScenarios(data))
      .catch(err => setError('Failed to load scenarios'))
  }, [])

  const fetchProjection = async () => {
    if (!selectedScenarioId) {
      setResults([])
      setError('')
      setWarning('')
      setEarlyAccessWarning('')
      return
    }
    
    setLoading(true)
    setError('')
    setWarning('')
    setEarlyAccessWarning('')
    setResults([])
    
    try {
      const res = await fetch(`/api/projection/${selectedScenarioId}`)
      const data = await res.json()
      if (data.error) {
        setError(data.error)
      } else {
        setResults(data.results || [])
        if (data.warning) setWarning(data.warning)
        if (data.early_access_warning) setEarlyAccessWarning(data.early_access_warning)
      }
    } catch (err) {
      setError('Failed to fetch projection')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProjection()
  }, [selectedScenarioId, refresh])

  const formatCurrency = (val) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val)
  }

  // Determine the return mode of the currently selected scenario
  const selectedScenario = scenarios.find(s => s.id === Number(selectedScenarioId))
  const currentReturnMode = selectedScenario ? selectedScenario.return_mode : null

  return (
    <div className="results-container" style={{ padding: '20px' }}>
      <h2>Projection Results</h2>
      
      <div style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <label htmlFor="scenario-select" style={{ fontWeight: 'bold' }}>Select Scenario:</label>
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
        <button 
          onClick={() => setRefresh(r => r + 1)} 
          disabled={loading || !selectedScenarioId}
          style={{ padding: '8px 12px', fontSize: '14px', cursor: loading ? 'not-allowed' : 'pointer' }}
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {error && <div style={{ color: '#721c24', backgroundColor: '#f8d7da', padding: '10px', borderRadius: '4px', marginBottom: '15px' }}>{error}</div>}
      {warning && <div style={{ color: '#856404', backgroundColor: '#fff3cd', border: '1px solid #ffeeba', padding: '10px', borderRadius: '4px', marginBottom: '15px' }}>{warning}</div>}
      {earlyAccessWarning && <div style={{ color: '#856404', backgroundColor: '#fff3cd', border: '1px solid #ffeeba', padding: '10px', borderRadius: '4px', marginBottom: '15px' }}>{earlyAccessWarning}</div>}

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
                
                {/* Confidence Intervals & Mean */}
                {(currentReturnMode === 'mean_stdev' || currentReturnMode === 'monte_carlo') && (
                  <>
                    <Line type="monotone" dataKey="ci95_low" stroke="#5b5ea6" strokeDasharray="4 4" name="95% CI Low" dot={false} />
                    <Line type="monotone" dataKey="ci70_low" stroke="#8884d8" strokeDasharray="4 4" name="70% CI Low" dot={false} />
                    <Line type="monotone" dataKey="ci50_low" stroke="#b3cde3" strokeDasharray="4 4" name="50% CI Low" dot={false} />
                    <Line type="monotone" dataKey="ci50_high" stroke="#b3cde3" strokeDasharray="4 4" name="50% CI High" dot={false} />
                    <Line type="monotone" dataKey="ci70_high" stroke="#8884d8" strokeDasharray="4 4" name="70% CI High" dot={false} />
                    <Line type="monotone" dataKey="ci95_high" stroke="#5b5ea6" strokeDasharray="4 4" name="95% CI High" dot={false} />
                  </>
                )}
                <Line type="monotone" dataKey="mean_balance" stroke="#333" name="Mean Balance" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #ddd' }}>
                  <th style={{ padding: '8px', textAlign: 'left' }}>Age</th>
                  {(currentReturnMode === 'mean_stdev' || currentReturnMode === 'monte_carlo') && (
                    <>
                      <th style={{ padding: '8px', textAlign: 'right' }}>95% CI Low</th>
                      <th style={{ padding: '8px', textAlign: 'right' }}>70% CI Low</th>
                      <th style={{ padding: '8px', textAlign: 'right' }}>50% CI Low</th>
                    </>
                  )}
                  <th style={{ padding: '8px', textAlign: 'right' }}>Mean Balance</th>
                  {(currentReturnMode === 'mean_stdev' || currentReturnMode === 'monte_carlo') && (
                    <>
                      <th style={{ padding: '8px', textAlign: 'right' }}>50% CI High</th>
                      <th style={{ padding: '8px', textAlign: 'right' }}>70% CI High</th>
                      <th style={{ padding: '8px', textAlign: 'right' }}>95% CI High</th>
                    </>
                  )}
                  <th style={{ padding: '8px', textAlign: 'right' }}>Mean Post-Tax</th>
                  <th style={{ padding: '8px', textAlign: 'right' }}>Mean Pre-Tax</th>
                </tr>
              </thead>
              <tbody>
                {results.map((row, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #eee' }}>
                    <td style={{ padding: '8px' }}>{row.age}</td>
                    {(currentReturnMode === 'mean_stdev' || currentReturnMode === 'monte_carlo') && (
                      <>
                        <td style={{ padding: '8px', textAlign: 'right' }}>{formatCurrency(row.ci95_low)}</td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>{formatCurrency(row.ci70_low)}</td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>{formatCurrency(row.ci50_low)}</td>
                      </>
                    )}
                    <td style={{ padding: '8px', textAlign: 'right' }}>{formatCurrency(row.mean_balance)}</td>
                    {(currentReturnMode === 'mean_stdev' || currentReturnMode === 'monte_carlo') && (
                      <>
                        <td style={{ padding: '8px', textAlign: 'right' }}>{formatCurrency(row.ci50_high)}</td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>{formatCurrency(row.ci70_high)}</td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>{formatCurrency(row.ci95_high)}</td>
                      </>
                    )}
                    <td style={{ padding: '8px', textAlign: 'right' }}>{formatCurrency(row.mean_post_tax)}</td>
                    <td style={{ padding: '8px', textAlign: 'right' }}>{formatCurrency(row.mean_pretax)}</td>
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
