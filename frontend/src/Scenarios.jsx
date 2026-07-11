import { useState, useEffect } from 'react'
import './App.css'

function Scenarios() {
  const [scenarios, setScenarios] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  
  // Form state
  const [name, setName] = useState('')
  const [currentAge, setCurrentAge] = useState('')
  const [retirementAge, setRetirementAge] = useState('')
  const [endAge, setEndAge] = useState('')
  const [expenses, setExpenses] = useState('')
  const [withdrawalSplit, setWithdrawalSplit] = useState('')
  const [inflationRate, setInflationRate] = useState('')
  const [returnMode, setReturnMode] = useState('mean_stdev')
  const [returnStartYear, setReturnStartYear] = useState('')
  const [returnEndYear, setReturnEndYear] = useState('')
  const [replayStartYear, setReplayStartYear] = useState('')
  
  // Edit state
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')
  const [editCurrentAge, setEditCurrentAge] = useState('')
  const [editRetirementAge, setEditRetirementAge] = useState('')
  const [editEndAge, setEditEndAge] = useState('')
  const [editExpenses, setEditExpenses] = useState('')
  const [editWithdrawalSplit, setEditWithdrawalSplit] = useState('')
  const [editInflationRate, setEditInflationRate] = useState('')
  const [editReturnMode, setEditReturnMode] = useState('mean_stdev')
  const [editReturnStartYear, setEditReturnStartYear] = useState('')
  const [editReturnEndYear, setEditReturnEndYear] = useState('')
  const [editReplayStartYear, setEditReplayStartYear] = useState('')

  const fetchScenarios = async () => {
    try {
      const res = await fetch('/api/scenarios')
      if (!res.ok) throw new Error('Failed to fetch scenarios')
      const data = await res.json()
      setScenarios(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchScenarios()
  }, [])

  const resetForm = () => {
    setName('')
    setCurrentAge('')
    setRetirementAge('')
    setEndAge('')
    setExpenses('')
    setWithdrawalSplit('')
    setInflationRate('')
    setReturnMode('mean_stdev')
    setReturnStartYear('')
    setReturnEndYear('')
    setReplayStartYear('')
    setEditingId(null)
    setEditName('')
    setEditCurrentAge('')
    setEditRetirementAge('')
    setEditEndAge('')
    setEditExpenses('')
    setEditWithdrawalSplit('')
    setEditInflationRate('')
    setEditReturnMode('mean_stdev')
    setEditReturnStartYear('')
    setEditReturnEndYear('')
    setEditReplayStartYear('')
    setSuccess('')
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    
    const payload = {
      name: name.trim(),
      current_age: parseFloat(currentAge),
      retirement_age: parseFloat(retirementAge),
      end_age: parseFloat(endAge),
      expected_expenses_in_retirement: parseFloat(expenses),
      withdrawal_split_pretax_pct: parseFloat(withdrawalSplit),
      inflation_rate_pct: parseFloat(inflationRate),
      return_mode: returnMode,
      return_start_year: returnMode === 'mean_stdev' ? parseFloat(returnStartYear) : null,
      return_end_year: returnMode === 'mean_stdev' ? parseFloat(returnEndYear) : null,
      replay_start_year: returnMode === 'historical_replay' ? parseFloat(replayStartYear) : null
    }

    try {
      const res = await fetch('/api/scenarios', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed to create scenario')
      setSuccess('Scenario created successfully')
      resetForm()
      fetchScenarios()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleEdit = (scenario) => {
    setEditingId(scenario.id)
    setEditName(scenario.name)
    setEditCurrentAge(scenario.current_age)
    setEditRetirementAge(scenario.retirement_age)
    setEditEndAge(scenario.end_age)
    setEditExpenses(scenario.expected_expenses_in_retirement)
    setEditWithdrawalSplit(scenario.withdrawal_split_pretax_pct)
    setEditInflationRate(scenario.inflation_rate_pct)
    setEditReturnMode(scenario.return_mode)
    setEditReturnStartYear(scenario.return_start_year)
    setEditReturnEndYear(scenario.return_end_year)
    setEditReplayStartYear(scenario.replay_start_year)
    setError('')
    setSuccess('')
  }

  const handleUpdate = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    const payload = {
      name: editName.trim(),
      current_age: parseFloat(editCurrentAge),
      retirement_age: parseFloat(editRetirementAge),
      end_age: parseFloat(editEndAge),
      expected_expenses_in_retirement: parseFloat(editExpenses),
      withdrawal_split_pretax_pct: parseFloat(editWithdrawalSplit),
      inflation_rate_pct: parseFloat(editInflationRate),
      return_mode: editReturnMode,
      return_start_year: editReturnMode === 'mean_stdev' ? parseFloat(editReturnStartYear) : null,
      return_end_year: editReturnMode === 'mean_stdev' ? parseFloat(editReturnEndYear) : null,
      replay_start_year: editReturnMode === 'historical_replay' ? parseFloat(editReplayStartYear) : null
    }

    try {
      const res = await fetch(`/api/scenarios/${editingId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed to update scenario')
      setSuccess('Scenario updated successfully')
      resetForm()
      fetchScenarios()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this scenario?')) return
    try {
      const res = await fetch(`/api/scenarios/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to delete scenario')
      fetchScenarios()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) return <div className="scenarios-container"><p>Loading scenarios...</p></div>

  return (
    <div className="scenarios-container">
      <h2>Scenarios</h2>
      
      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{success}</div>}

      <form onSubmit={editingId ? handleUpdate : handleSubmit} className="scenario-form">
        <h3>{editingId ? 'Edit Scenario' : 'Add New Scenario'}</h3>
        <div className="form-group">
          <label>Name:</label>
          <input 
            type="text" 
            value={editingId ? editName : name} 
            onChange={(e) => editingId ? setEditName(e.target.value) : setName(e.target.value)} 
            required 
          />
        </div>
        <div className="form-group">
          <label>Current Age:</label>
          <input 
            type="number" 
            value={editingId ? editCurrentAge : currentAge} 
            onChange={(e) => editingId ? setEditCurrentAge(e.target.value) : setCurrentAge(e.target.value)} 
            required 
          />
        </div>
        <div className="form-group">
          <label>Retirement Age:</label>
          <input 
            type="number" 
            value={editingId ? editRetirementAge : retirementAge} 
            onChange={(e) => editingId ? setEditRetirementAge(e.target.value) : setRetirementAge(e.target.value)} 
            required 
          />
        </div>
        <div className="form-group">
          <label>End Age:</label>
          <input 
            type="number" 
            value={editingId ? editEndAge : endAge} 
            onChange={(e) => editingId ? setEditEndAge(e.target.value) : setEndAge(e.target.value)} 
            required 
          />
        </div>
        <div className="form-group">
          <label>Expected Expenses (Annual):</label>
          <input 
            type="number" 
            step="0.01" 
            value={editingId ? editExpenses : expenses} 
            onChange={(e) => editingId ? setEditExpenses(e.target.value) : setExpenses(e.target.value)} 
            required 
          />
        </div>
        <div className="form-group">
          <label>Withdrawal Split (Pre-Tax %):</label>
          <input 
            type="number" 
            step="0.01" 
            min="0" 
            max="100"
            value={editingId ? editWithdrawalSplit : withdrawalSplit} 
            onChange={(e) => editingId ? setEditWithdrawalSplit(e.target.value) : setWithdrawalSplit(e.target.value)} 
            required 
          />
        </div>
        <div className="form-group">
          <label>Inflation Rate (%):</label>
          <input 
            type="number" 
            step="0.01" 
            value={editingId ? editInflationRate : inflationRate} 
            onChange={(e) => editingId ? setEditInflationRate(e.target.value) : setInflationRate(e.target.value)} 
            required 
          />
        </div>
        <div className="form-group">
          <label>Return Mode:</label>
          <select 
            value={editingId ? editReturnMode : returnMode} 
            onChange={(e) => editingId ? setEditReturnMode(e.target.value) : setReturnMode(e.target.value)}
          >
            <option value="mean_stdev">Mean / StDev</option>
            <option value="historical_replay">Historical Replay</option>
          </select>
        </div>
        
        {(!editingId ? returnMode : editReturnMode) === 'mean_stdev' && (
          <>
            <div className="form-group">
              <label>Return Start Year:</label>
              <input 
                type="number" 
                value={editingId ? editReturnStartYear : returnStartYear} 
                onChange={(e) => editingId ? setEditReturnStartYear(e.target.value) : setReturnStartYear(e.target.value)} 
                required 
              />
            </div>
            <div className="form-group">
              <label>Return End Year:</label>
              <input 
                type="number" 
                value={editingId ? editReturnEndYear : returnEndYear} 
                onChange={(e) => editingId ? setEditReturnEndYear(e.target.value) : setReturnEndYear(e.target.value)} 
                required 
              />
            </div>
          </>
        )}

        {(!editingId ? returnMode : editReturnMode) === 'historical_replay' && (
          <div className="form-group">
            <label>Replay Start Year:</label>
            <input 
              type="number" 
              value={editingId ? editReplayStartYear : replayStartYear} 
              onChange={(e) => editingId ? setEditReplayStartYear(e.target.value) : setReplayStartYear(e.target.value)} 
              required 
            />
          </div>
        )}

        <button type="submit">{editingId ? 'Update Scenario' : 'Add Scenario'}</button>
        {editingId && <button type="button" onClick={resetForm} className="cancel-btn">Cancel</button>}
      </form>

      <div className="scenarios-list">
        <h3>Existing Scenarios</h3>
        {scenarios.length === 0 ? (
          <p>No scenarios created yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Current Age</th>
                <th>Retirement Age</th>
                <th>End Age</th>
                <th>Expenses</th>
                <th>Split (%)</th>
                <th>Inflation (%)</th>
                <th>Return Mode</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {scenarios.map(scen => (
                <tr key={scen.id}>
                  <td>{scen.name}</td>
                  <td>{scen.current_age}</td>
                  <td>{scen.retirement_age}</td>
                  <td>{scen.end_age}</td>
                  <td>${scen.expected_expenses_in_retirement.toLocaleString()}</td>
                  <td>{scen.withdrawal_split_pretax_pct}</td>
                  <td>{scen.inflation_rate_pct}</td>
                  <td>{scen.return_mode}</td>
                  <td>
                    <button onClick={() => handleEdit(scen)}>Edit</button>
                    <button onClick={() => handleDelete(scen.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export default Scenarios
