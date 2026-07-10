import { useState, useEffect } from 'react'
import './App.css'

function HistoricalReturns() {
  const [returns, setReturns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [uploadErrors, setUploadErrors] = useState([])
  const [file, setFile] = useState(null)

  const fetchReturns = async () => {
    try {
      const res = await fetch('/api/annual-returns')
      if (!res.ok) throw new Error('Failed to fetch returns')
      const data = await res.json()
      setReturns(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchReturns()
  }, [])

  const handleFileChange = (e) => {
    setFile(e.target.files[0])
    setError('')
    setSuccess('')
    setUploadErrors([])
  }

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!file) {
      setError('Please select a CSV file first.')
      return
    }
    
    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/annual-returns', {
        method: 'POST',
        body: formData
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Upload failed')
      
      setSuccess(`Upload successful! Added: ${data.added}, Updated: ${data.updated}`)
      setUploadErrors(data.errors || [])
      setFile(null)
      fetchReturns()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) return <div className="returns-container"><p>Loading returns...</p></div>

  return (
    <div className="returns-container">
      <h2>Historical Returns</h2>
      
      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{success}</div>}
      {uploadErrors.length > 0 && (
        <div className="error-list">
          <strong>Upload Errors:</strong>
          <ul>
            {uploadErrors.map((err, idx) => <li key={idx}>{err}</li>)}
          </ul>
        </div>
      )}

      <form onSubmit={handleUpload} className="upload-area">
        <h3>Upload CSV</h3>
        <p>Expected CSV format: two columns named <code>year</code> and <code>return</code>. The header row should look like: <code>year,return</code></p>
        <input type="file" accept=".csv" onChange={handleFileChange} />
        <br />
        <button type="submit" disabled={!file}>Upload</button>
      </form>

      <div className="preview-table">
        <h3>Preview ({returns.length} years)</h3>
        {returns.length === 0 ? (
          <p>No historical returns uploaded yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Year</th>
                <th>Return (%)</th>
              </tr>
            </thead>
            <tbody>
              {returns.map(r => (
                <tr key={r.year}>
                  <td>{r.year}</td>
                  <td>{r.return_pct}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export default HistoricalReturns
