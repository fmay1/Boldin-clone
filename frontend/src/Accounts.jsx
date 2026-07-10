import { useState, useEffect } from 'react'
import './App.css'

function Accounts() {
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  
  // Form state
  const [name, setName] = useState('')
  const [type, setType] = useState('post-tax')
  const [currentBalance, setCurrentBalance] = useState('')
  const [annualContribution, setAnnualContribution] = useState('')
  
  // Edit state
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')
  const [editType, setEditType] = useState('post-tax')
  const [editBalance, setEditBalance] = useState('')
  const [editContribution, setEditContribution] = useState('')

  const fetchAccounts = async () => {
    try {
      const res = await fetch('/api/accounts')
      if (!res.ok) throw new Error('Failed to fetch accounts')
      const data = await res.json()
      setAccounts(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAccounts()
  }, [])

  const resetForm = () => {
    setName('')
    setType('post-tax')
    setCurrentBalance('')
    setAnnualContribution('')
    setEditingId(null)
    setEditName('')
    setEditType('post-tax')
    setEditBalance('')
    setEditContribution('')
    setSuccess('')
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    
    const payload = {
      name: name.trim(),
      type: type,
      current_balance: parseFloat(currentBalance) || 0,
      annual_contribution: parseFloat(annualContribution) || 0
    }

    try {
      const res = await fetch('/api/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed to create account')
      setSuccess('Account created successfully')
      resetForm()
      fetchAccounts()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleEdit = (account) => {
    setEditingId(account.id)
    setEditName(account.name)
    setEditType(account.type)
    setEditBalance(account.current_balance)
    setEditContribution(account.annual_contribution)
    setError('')
    setSuccess('')
  }

  const handleUpdate = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    const payload = {
      name: editName.trim(),
      type: editType,
      current_balance: parseFloat(editBalance) || 0,
      annual_contribution: parseFloat(editContribution) || 0
    }

    try {
      const res = await fetch(`/api/accounts/${editingId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed to update account')
      setSuccess('Account updated successfully')
      resetForm()
      fetchAccounts()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this account?')) return
    try {
      const res = await fetch(`/api/accounts/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to delete account')
      fetchAccounts()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) return <div className="accounts-container"><p>Loading accounts...</p></div>

  return (
    <div className="accounts-container">
      <h2>Accounts</h2>
      
      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{success}</div>}

      <form onSubmit={editingId ? handleUpdate : handleSubmit} className="account-form">
        <h3>{editingId ? 'Edit Account' : 'Add New Account'}</h3>
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
          <label>Type:</label>
          <select 
            value={editingId ? editType : type} 
            onChange={(e) => editingId ? setEditType(e.target.value) : setType(e.target.value)}
          >
            <option value="post-tax">Post-Tax</option>
            <option value="pre-tax">Pre-Tax</option>
          </select>
        </div>
        <div className="form-group">
          <label>Current Balance:</label>
          <input 
            type="number" 
            step="0.01" 
            value={editingId ? editBalance : currentBalance} 
            onChange={(e) => editingId ? setEditBalance(e.target.value) : setCurrentBalance(e.target.value)} 
            required 
          />
        </div>
        <div className="form-group">
          <label>Annual Contribution:</label>
          <input 
            type="number" 
            step="0.01" 
            value={editingId ? editContribution : annualContribution} 
            onChange={(e) => editingId ? setEditContribution(e.target.value) : setAnnualContribution(e.target.value)} 
            required 
          />
        </div>
        <button type="submit">{editingId ? 'Update Account' : 'Add Account'}</button>
        {editingId && <button type="button" onClick={resetForm} className="cancel-btn">Cancel</button>}
      </form>

      <div className="accounts-list">
        <h3>Existing Accounts</h3>
        {accounts.length === 0 ? (
          <p>No accounts added yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Balance</th>
                <th>Annual Contribution</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map(acc => (
                <tr key={acc.id}>
                  <td>{acc.name}</td>
                  <td>{acc.type}</td>
                  <td>${acc.current_balance.toLocaleString()}</td>
                  <td>${acc.annual_contribution.toLocaleString()}</td>
                  <td>
                    <button onClick={() => handleEdit(acc)}>Edit</button>
                    <button onClick={() => handleDelete(acc.id)}>Delete</button>
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

export default Accounts
