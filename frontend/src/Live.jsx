import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

function Live() {
  const [scenarios, setScenarios] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [formData, setFormData] = useState({})
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [earlyAccessWarning, setEarlyAccessWarning] = useState('')
  const [saving, setSaving] = useState(false)
  const [expenditures, setExpenditures] = useState([])
  const [originalExpenditureIds, setOriginalExpenditureIds] = useState([])

  useEffect(() => {
    fetch('/api/scenarios')
      .then(res => res.json())
      .then(data => setScenarios(data))
      .catch(err => setError('Failed to load scenarios'))
  }, [])

  const handleScenarioChange = (e) => {
    const id = Number(e.target.value)
    setSelectedId(id)
    const scenario = scenarios.find(s => s.id === id)
    if (scenario) {
      setFormData({
        name: scenario.name,
        current_age: scenario.current_age,
        retirement_age: scenario.retirement_age,
        end_age: scenario.end_age,
        expected_expenses_in_retirement: scenario.expected_expenses_in_retirement,
        withdrawal_split_pretax_pct: scenario.withdrawal_split_pretax_pct,
        inflation_rate_pct: scenario.inflation_rate_pct,
        return_mode: scenario.return_mode,
        return_start_year: scenario.return_start_year,
        return_end_year: scenario.return_end_year,
        replay_start_year: scenario.replay_start_year,
        block_length_years: scenario.block_length_years
      })
      const exps = (scenario.expenditures || []).map(e => ({
        id: e.id,
        amount: e.amount,
        age: e.age,
        inflationAdjusted: !!e.inflation_adjusted
      }))
      setExpenditures(exps)
      setOriginalExpenditureIds(exps.map(e => e.id))
      setResults([])
      setError('')
      setWarning('')
      setEarlyAccessWarning('')
    }
  }

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value === '' ? '' : (name === 'end_age' ? parseInt(value, 10) : parseFloat(value))
    }))
  }

  const isValidMonthlyPrecision = (val) => {
    const num = parseFloat(val)
    if (isNaN(num)) return false
    return Math.abs((num * 12) - Math.round(num * 12)) < 1e-9
  }

  const handleUpdate = async () => {
    if (!selectedId) return
    setError('')
    setWarning('')
    setEarlyAccessWarning('')
    setResults([])
    
    if (!isValidMonthlyPrecision(formData.current_age)) {
      setError('Current age must correspond to a whole number of months (e.g., 46.25)')
      return
    }
    if (!isValidMonthlyPrecision(formData.retirement_age)) {
      setError('Retirement age must correspond to a whole number of months (e.g., 46.25)')
      return
    }

    setLoading(true)
    
    try {
      // Filter out incomplete expenditures and format for backend
      const validExpenditures = expenditures
        .filter(exp => exp.age !== '' && exp.age !== null && exp.amount !== '' && exp.amount !== null)
        .map(exp => ({
          amount: parseFloat(exp.amount) || 0,
          age: parseFloat(exp.age),
          inflation_adjusted: exp.inflationAdjusted ? 1 : 0
        }))
        
      const payload = { ...formData, expenditures: validExpenditures }
      const res = await fetch('/api/projection/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
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

  const handleSave = async () => {
    if (!selectedId) return
    setError('')
    
    if (!isValidMonthlyPrecision(formData.current_age)) {
      setError('Current age must correspond to a whole number of months (e.g., 46.25)')
      return
    }
    if (!isValidMonthlyPrecision(formData.retirement_age)) {
      setError('Retirement age must correspond to a whole number of months (e.g., 46.25)')
      return
    }

    setSaving(true)
    try {
      // Sync expenditures first
      const currentIds = expenditures.map(e => e.id).filter(Boolean)
      const deletedIds = originalExpenditureIds.filter(id => !currentIds.includes(id))
      
      for (const id of deletedIds) {
        await fetch(`/api/scenarios/${selectedId}/expenditures/${id}`, { method: 'DELETE' })
      }
      
      for (const exp of expenditures) {
        const body = {
          amount: parseFloat(exp.amount) || 0,
          age: parseFloat(exp.age),
          inflation_adjusted: exp.inflationAdjusted ? 1 : 0
        }
        
        if (exp.id) {
          await fetch(`/api/scenarios/${selectedId}/expenditures/${exp.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
          })
        } else {
          await fetch(`/api/scenarios/${selectedId}/expenditures`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
          })
        }
      }

      const res = await fetch(`/api/scenarios/${selectedId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      })
      const data = await res.json()
      if (data.error) {
        setError(data.error)
      } else {
        setError('')
        setScenarios(prev => prev.map(s => s.id === selectedId ? { ...s, ...formData } : s))
      }
    } catch (err) {
      setError('Failed to save scenario')
    } finally {
      setSaving(false)
    }
  }

  const addExpenditure = () => {
    if (expenditures.length >= 10) return
    setExpenditures([...expenditures, { id: null, amount: 0, age: '', inflationAdjusted: false }])
  }

  const updateExpenditure = (index, field, value) => {
    const updated = [...expenditures]
    updated[index] = { ...updated[index], [field]: value }
    setExpenditures(updated)
  }

  const removeExpenditure = (index) => {
    setExpenditures(expenditures.filter((_, i) => i !== index))
  }

  const formatCurrency = (val) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val)
  }

  const currentReturnMode = formData.return_mode

  return (
    <div style={{ padding: '20px' }}>
      <h2>Live Tweaking</h2>
      
      <div style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <label htmlFor="live-scenario-select" style={{ fontWeight: 'bold' }}>Select Scenario to Edit:</label>
        <select 
          id="live-scenario-select" 
          value={selectedId} 
          onChange={handleScenarioChange}
          style={{ padding: '8px', fontSize: '14px' }}
        >
          <option value="">-- Choose a scenario --</option>
          {scenarios.map(s => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </div>

      {selectedId && (
        <div className="scenario-form" style={{ marginBottom: '20px' }}>
          <div className="form-group">
            <label>Name:</label>
            <input name="name" value={formData.name || ''} onChange={handleInputChange} />
          </div>
          <div className="form-group">
            <label>Current Age:</label>
            <input type="number" step="0.01" name="current_age" value={formData.current_age || ''} onChange={handleInputChange} />
          </div>
          <div className="form-group">
            <label>Retirement Age:</label>
            <input type="number" step="0.01" name="retirement_age" value={formData.retirement_age || ''} onChange={handleInputChange} />
          </div>
          <div className="form-group">
            <label>End Age:</label>
            <input type="number" step="1" name="end_age" value={formData.end_age || ''} onChange={handleInputChange} />
          </div>
          <div className="form-group">
            <label>Retirement Expenses:</label>
            <input type="number" step="0.01" name="expected_expenses_in_retirement" value={formData.expected_expenses_in_retirement || ''} onChange={handleInputChange} />
          </div>
          <div className="form-group">
            <label>Pre-Tax Withdrawal %:</label>
            <input type="number" step="0.01" name="withdrawal_split_pretax_pct" value={formData.withdrawal_split_pretax_pct || ''} onChange={handleInputChange} />
          </div>
          <div className="form-group">
            <label>Inflation Rate %:</label>
            <input type="number" step="0.01" name="inflation_rate_pct" value={formData.inflation_rate_pct || ''} onChange={handleInputChange} />
          </div>
          <div className="form-group">
            <label>Return Mode:</label>
            <select name="return_mode" value={formData.return_mode || ''} onChange={handleInputChange}>
              <option value="mean_stdev">Mean/Stdev</option>
              <option value="historical_replay">Historical Replay</option>
              <option value="monte_carlo">Monte Carlo</option>
            </select>
          </div>
          
          {currentReturnMode === 'mean_stdev' && (
            <>
              <div className="form-group">
                <label>Return Start Year:</label>
                <input type="number" name="return_start_year" value={formData.return_start_year || ''} onChange={handleInputChange} />
              </div>
              <div className="form-group">
                <label>Return End Year:</label>
                <input type="number" name="return_end_year" value={formData.return_end_year || ''} onChange={handleInputChange} />
              </div>
            </>
          )}
          
          {currentReturnMode === 'historical_replay' && (
            <div className="form-group">
              <label>Replay Start Year:</label>
              <input type="number" name="replay_start_year" value={formData.replay_start_year || ''} onChange={handleInputChange} />
            </div>
          )}

          {currentReturnMode === 'monte_carlo' && (
            <>
              <div className="form-group">
                <label>Return Start Year:</label>
                <input type="number" name="return_start_year" value={formData.return_start_year || ''} onChange={handleInputChange} />
              </div>
              <div className="form-group">
                <label>Return End Year:</label>
                <input type="number" name="return_end_year" value={formData.return_end_year || ''} onChange={handleInputChange} />
              </div>
              <div className="form-group">
                <label>Block Length (Years):</label>
                <input type="number" name="block_length_years" value={formData.block_length_years || ''} onChange={handleInputChange} />
              </div>
            </>
          )}

          <div className="expenditures-section">
            <h3>Planned Large Expenditures</h3>
            {expenditures.map((exp, index) => (
              <div key={index} className="expenditure-row">
                <input
                  type="number"
                  step="0.01"
                  value={exp.amount}
                  onChange={(e) => updateExpenditure(index, 'amount', parseFloat(e.target.value) || 0)}
                  placeholder="Amount"
                  className="exp-input"
                />
                <input
                  type="number"
                  step="0.01"
                  value={exp.age}
                  onChange={(e) => updateExpenditure(index, 'age', e.target.value)}
                  placeholder="Age"
                  className="exp-input"
                />
                <label className="exp-checkbox">
                  <input
                    type="checkbox"
                    checked={exp.inflationAdjusted}
                    onChange={(e) => updateExpenditure(index, 'inflationAdjusted', e.target.checked)}
                  />
                  Inflation Adjusted
                </label>
                <button type="button" onClick={() => removeExpenditure(index)} className="delete-exp-btn" title="Delete">×</button>
              </div>
            ))}
            <button
              type="button"
              onClick={addExpenditure}
              disabled={expenditures.length >= 10}
              className="add-exp-btn"
            >
              + Add Expenditure
            </button>
          </div>

          <div style={{ marginTop: '15px' }}>
            <button onClick={handleUpdate} disabled={loading}>
              {loading ? 'Calculating...' : 'Update Projection'}
            </button>
            <button onClick={handleSave} disabled={saving} style={{ marginLeft: '10px' }}>
              {saving ? 'Saving...' : 'Save Changes to Scenario'}
            </button>
          </div>
        </div>
      )}

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

export default Live
