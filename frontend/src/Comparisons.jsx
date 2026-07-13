import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const COLORS = ['#333', '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22']

function Comparisons() {
  const [scenarios, setScenarios] = useState([])
  const [selectedIds, setSelectedIds] = useState([])
  const [projections, setProjections] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/scenarios')
      .then(res => res.json())
      .then(data => setScenarios(data))
      .catch(err => setError('Failed to load scenarios'))
  }, [])

  useEffect(() => {
    if (selectedIds.length === 0) {
      setProjections([])
      return
    }

    setLoading(true)
    setError('')
    const fetchAll = selectedIds.map(async (id) => {
      try {
        const res = await fetch(`/api/projection/${id}`)
        const data = await res.json()
        if (data.error) throw new Error(data.error)
        const scenario = scenarios.find(s => s.id === id)
        return {
          ...data,
          scenario_id: id,
          scenario_name: scenario ? scenario.name : `Scenario ${id}`
        }
      } catch (err) {
        setError(err.message)
        return null
      }
    })

    Promise.all(fetchAll).then(results => {
      setProjections(results.filter(Boolean))
      setLoading(false)
    })
  }, [selectedIds, scenarios])

  const handleSelectChange = (e) => {
    const values = [...e.target.selectedOptions].map(opt => Number(opt.value))
    setSelectedIds(values)
  }

  const formatCurrency = (val) => {
    if (val === undefined || val === null) return null
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val)
  }

  const chartData = []
  const allAges = new Set()
  projections.forEach(p => {
    p.results.forEach(r => allAges.add(r.age))
  })
  
  const sortedAges = Array.from(allAges).sort((a, b) => a - b)
  
  sortedAges.forEach(age => {
    const row = { age }
    projections.forEach(p => {
      const res = p.results.find(r => r.age === age)
      row[p.scenario_name] = res ? res.mean_balance : null
    })
    chartData.push(row)
  })

  // Build depletion chart data for Monte Carlo scenarios
  const depletionChartData = []
  const hasDepletionData = projections.some(p => p.results.length > 0 && p.results[0].depletion_probability_pct !== undefined)
  
  if (hasDepletionData) {
    const allDepletionAges = new Set()
    projections.forEach(p => {
      if (p.results[0]?.depletion_probability_pct === undefined) return
      p.results.forEach(r => allDepletionAges.add(r.age))
    })
    const sortedDepletionAges = Array.from(allDepletionAges).sort((a, b) => a - b)
    sortedDepletionAges.forEach(age => {
      const row = { age }
      projections.forEach(p => {
        if (p.results[0]?.depletion_probability_pct === undefined) return
        const res = p.results.find(r => r.age === age)
        row[p.scenario_name] = res ? res.depletion_probability_pct : null
      })
      depletionChartData.push(row)
    })
  }

  return (
    <div style={{ padding: '20px' }}>
      <h2>Scenario Comparisons</h2>
      
      <div style={{ marginBottom: '20px' }}>
        <label htmlFor="compare-select" style={{ fontWeight: 'bold', display: 'block', marginBottom: '5px' }}>
          Select Scenarios to Compare:
        </label>
        <div style={{ fontSize: '12px', color: '#666', marginBottom: '5px' }}>(Hold Ctrl/Cmd to select multiple)</div>
        <select
          id="compare-select"
          multiple
          value={selectedIds}
          onChange={handleSelectChange}
          style={{ padding: '8px', fontSize: '14px', width: '500px', height: '150px' }}
        >
          {scenarios.map(s => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </div>

      {error && <div style={{ color: '#721c24', backgroundColor: '#f8d7da', padding: '10px', borderRadius: '4px', marginBottom: '15px' }}>{error}</div>}
      {loading && <p>Loading projections...</p>}

      {!loading && projections.length > 0 && (
        <>
          <div style={{ width: '100%', height: 400, marginBottom: '20px' }}>
            <ResponsiveContainer>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="age" label={{ value: 'Age', position: 'insideBottomRight', offset: -5 }} />
                <YAxis tickFormatter={(val) => `$${(val / 1000000).toFixed(1)}M`} />
                <Tooltip formatter={(val) => formatCurrency(val)} />
                <Legend />
                {projections.map((p, idx) => (
                  <Line
                    key={p.scenario_id}
                    type="monotone"
                    dataKey={p.scenario_name}
                    stroke={COLORS[idx % COLORS.length]}
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {hasDepletionData && (
            <div style={{ width: '100%', height: 250, marginBottom: '20px' }}>
              <h4>Probability of Depletion by Age (Monte Carlo Scenarios)</h4>
              <ResponsiveContainer>
                <LineChart data={depletionChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="age" label={{ value: 'Age', position: 'insideBottomRight', offset: -5 }} />
                  <YAxis domain={[0, 100]} tickFormatter={(val) => `${val}%`} />
                  <Tooltip formatter={(val) => val !== null ? `${val.toFixed(1)}%` : 'N/A'} />
                  <Legend />
                  {projections.map((p, idx) => {
                    if (p.results[0]?.depletion_probability_pct === undefined) return null;
                    return (
                      <Line
                        key={`depletion-${p.scenario_id}`}
                        type="monotone"
                        dataKey={p.scenario_name}
                        stroke={COLORS[idx % COLORS.length]}
                        strokeWidth={2}
                        dot={false}
                        connectNulls={false}
                      />
                    );
                  })}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          <div style={{ marginTop: '20px' }}>
            <h3>Scenario Warnings</h3>
            {projections.map(p => (
              <div key={p.scenario_id} style={{ marginBottom: '10px', padding: '10px', backgroundColor: '#f9f9f9', borderRadius: '4px' }}>
                <strong>{p.scenario_name}:</strong>
                {p.warning && <div style={{ color: '#856404', marginTop: '5px' }}>{p.warning}</div>}
                {p.early_access_warning && <div style={{ color: '#856404', marginTop: '5px' }}>{p.early_access_warning}</div>}
                {!p.warning && !p.early_access_warning && <div style={{ color: '#28a745', marginTop: '5px' }}>No warnings</div>}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export default Comparisons
