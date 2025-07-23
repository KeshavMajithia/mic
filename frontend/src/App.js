import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [country, setCountry] = useState('');
  const [weight, setWeight] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!country.trim() || !weight || weight <= 0) {
      setError('Please enter a valid country and weight');
      return;
    }

    setLoading(true);
    setError('');
    setResults(null);

    try {
      const response = await axios.post(`${process.env.REACT_APP_API_URL}/api/get-rates`, {
        country: country.trim(),
        weight: parseFloat(weight)
      });

      setResults(response.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to fetch rates. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const parseResponse = (responseData) => {
    // The new backend returns structured data directly
    if (responseData && responseData.results) {
      return responseData;
    }
    
    // Fallback for any unexpected format
    return { results: [], raw_response: JSON.stringify(responseData) };
  };

  const renderResults = () => {
    if (!results) return null;

    const { data } = results;
    const responseData = parseResponse(data.gemini_response);
    
    return (
      <div className="results-container">
        <h2>Shipping Rates for {results.country} ({results.weight} kg)</h2>
        
        {/* Zone Information */}
        <div className="zone-info">
          <h3>Zone Mappings</h3>
          <div className="zone-grid">
            {data.zone_mappings.fedex_zone && (
              <div className="zone-item">
                <strong>FedEx Zone:</strong> {data.zone_mappings.fedex_zone}
              </div>
            )}
            {data.zone_mappings.dhl_zone && (
              <div className="zone-item">
                <strong>DHL Zone:</strong> {data.zone_mappings.dhl_zone}
              </div>
            )}
          </div>
        </div>

        {/* Gemini Analysis Results */}
        <div className="gemini-results">
          <h3>Available Rates</h3>
          {responseData.results ? (
            <div className="rates-grid">
              {responseData.results.map((rate, index) => (
                <div key={index} className="rate-card">
                  <div className="carrier-name">{rate.carrier}</div>
                  <div className="service-type">{rate.service_type}</div>
                  <div className="rate-amount">{rate.rate} {rate.currency || ''}</div>
                  {rate.zone && <div className="zone">Zone: {rate.zone}</div>}
                </div>
              ))}
            </div>
          ) : (
            <div className="raw-response">
              <h4>Analysis Result:</h4>
              <pre>{responseData.raw_response || JSON.stringify(data.gemini_response)}</pre>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🚚 Majithia International Courier Rate Finder</h1>
        <p>Find the best shipping rates for your international deliveries</p>
      </header>

      <main className="main-content">
        <form onSubmit={handleSubmit} className="search-form">
          <div className="form-group">
            <label htmlFor="country">Destination Country:</label>
            <input
              type="text"
              id="country"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              placeholder="e.g., United States, Germany, Japan"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="weight">Package Weight (kg):</label>
            <input
              type="number"
              id="weight"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              placeholder="e.g., 2.5"
              min="0.5"
              step="0.5"
              required
            />
          </div>

          <button type="submit" disabled={loading} className="search-button">
            {loading ? 'Searching...' : 'Find Rates'}
          </button>
        </form>

        {error && (
          <div className="error-message">
            <p>❌ {error}</p>
          </div>
        )}

        {loading && (
          <div className="loading-message">
            <p>🔍 Analyzing rates from multiple carriers...</p>
          </div>
        )}

        {renderResults()}
      </main>

      <footer className="App-footer">
        <p>Built with ❤️ for efficient courier rate management</p>
      </footer>
    </div>
  );
}

export default App;
