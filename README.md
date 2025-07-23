# 🚚 International Courier Rate Finder

A smart web application that helps find shipping rates from multiple courier companies by intelligently parsing rate sheets and zone mappings using Google's Gemini AI.

## 🌟 Features

- **Smart Rate Detection**: Uses Gemini AI to parse complex CSV rate data
- **Multi-Carrier Support**: Handles rates from Aramax, DPEX, DPD, FedEx, UPS, and more
- **Zone Mapping**: Automatically maps countries to carrier zones (FedEx, DHL, UPS)
- **User-Friendly Interface**: Clean, modern React frontend
- **Real-time Results**: Instant rate comparison across carriers

## 🛠️ Setup Instructions

### Prerequisites
- Python 3.8+
- Node.js 16+
- Google Gemini API key

### Backend Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Gemini API key:**
   - Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Set environment variable:
     ```bash
     # Windows
     set GEMINI_API_KEY=your_api_key_here
     
     # Linux/Mac
     export GEMINI_API_KEY=your_api_key_here
     ```

3. **Run the backend:**
   ```bash
   python app.py
   ```
   Backend will run on `http://localhost:5000`

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the frontend:**
   ```bash
   npm start
   ```
   Frontend will run on `http://localhost:3000`

## 📁 Project Structure

```
MajIntCour/
├── app.py                 # Flask backend with Gemini AI integration
├── requirements.txt       # Python dependencies
├── price csv.csv         # Rate data from courier companies
├── README.md             # This file
└── frontend/
    ├── package.json      # React dependencies
    ├── public/
    │   └── index.html    # HTML template
    └── src/
        ├── App.js        # Main React component
        ├── App.css       # Styling
        ├── index.js      # React entry point
        └── index.css     # Base styles
```

## 🚀 How It Works

1. **User Input**: Enter destination country and package weight
2. **AI Processing**: Gemini AI analyzes the CSV data to find relevant rates
3. **Zone Mapping**: System automatically determines carrier zones for the country
4. **Results Display**: Shows all available rates with carrier, service type, and pricing

## 🔧 API Endpoints

- `POST /api/get-rates` - Get shipping rates
  ```json
  {
    "country": "United States",
    "weight": 2.5
  }
  ```

- `GET /api/health` - Health check

## 📊 Supported Carriers

- **Aramax**: Direct country-based pricing
- **DPEX**: Zone-based pricing (Zones 1-5)
- **DPD**: European country-based pricing
- **FedEx Express**: Zone-based pricing (Zones A-Q)
- **UPS**: Mixed zone and country-based pricing
- **DHL**: Zone-based pricing (Zones 1-14)

## 🔒 Security Notes

- Store your Gemini API key securely as an environment variable
- Never commit API keys to version control
- Consider rate limiting for production use

## 🐛 Troubleshooting

1. **"Could not load pricing data"**: Ensure `price csv.csv` is in the root directory
2. **Gemini API errors**: Check your API key and internet connection
3. **CORS issues**: Ensure both frontend and backend are running on correct ports

## 📝 Usage Example

1. Start both backend and frontend servers
2. Open `http://localhost:3000` in your browser
3. Enter "Germany" as country and "2.5" as weight
4. Click "Find Rates" to see results from all carriers

## 🤝 Contributing

This application was built specifically for courier business rate management. Feel free to customize the zone mappings and add new carriers as needed.

## 📄 License

Built for internal business use. Modify as needed for your requirements.
