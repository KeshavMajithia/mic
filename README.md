# 🚚 Majithia International Courier

A comprehensive courier management system designed to streamline international shipping operations, featuring real-time rate calculation, booking management, and shipment tracking.

![Majithia International Courier Banner](https://via.placeholder.com/1200x400/1e40af/ffffff?text=Majithia+International+Courier)

## 🌟 Features

- **Intelligent Rate Finder**: Real-time shipping rate calculation across multiple carriers
- **Automated Booking System**: Streamlined booking process with customer data management
- **Multi-Carrier Integration**: Supports major international courier services
- **Admin Dashboard**: Comprehensive tracking and management of all shipments
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Secure Authentication**: Role-based access control for staff and administrators

## 🛠️ Setup Instructions

### Prerequisites

- Node.js 16+
- npm or yarn package manager
- Supabase account
- Google Gemini API key

### Environment Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/majithia-courier.git
   cd majithia-courier
   ```

2. **Install dependencies**
   ```bash
   # Install frontend dependencies
   npm install
   
   # Install backend dependencies
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   Create a `.env` file in the root directory with the following variables:
   ```
   # Supabase Configuration
   VITE_SUPABASE_URL=your_supabase_url
   VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
   
   # Google Gemini API
   VITE_GEMINI_API_KEY=your_gemini_api_key
   GEMINI_API_KEY=your_gemini_api_key
   
   # API Configuration
   VITE_API_URL=http://localhost:5000/api  # For local development
   ```

### Backend Setup

1. **Initialize the database**
   - Set up your Supabase project
   - Import the database schema from `supabase/schema.sql`

2. **Start the backend server**
   ```bash
   python app_smart_fixed.py
   ```
   The backend will be available at `http://localhost:5000`

### Frontend Setup

1. **Start the development server**
   ```bash
   npm run dev
   ```
   The application will be available at `http://localhost:5173`

## 🚀 Features in Detail

### Rate Finder
- Real-time shipping rate calculation
- Multiple carrier support
- Weight and destination-based pricing
- Service level options

### Booking Management
- Customer information collection
- Shipment details
- Real-time tracking
- Booking history

### Admin Dashboard
- View all bookings
- Filter and search functionality
- Export data to CSV/Excel
- System analytics

## 🔒 Authentication

Majithia International Courier uses Supabase Auth for secure authentication with role-based access control:

- **Admin**: Full system access
- **Staff**: Limited access to booking management
- **Customers**: Self-service portal access

## 📦 Deployment

### Production Deployment

1. **Build the frontend**
   ```bash
   npm run build
   ```

2. **Deploy the backend**
   - Deploy `app_smart_fixed.py` to your preferred Python hosting (e.g., Google Cloud Run, Heroku, or AWS Elastic Beanstalk)
   - Update the `VITE_API_URL` in your production environment

3. **Configure Supabase**
   - Set up production environment variables
   - Configure CORS settings
   - Set up database backups

## 📁 Project Structure

```
majithia-courier/
├── app_smart_fixed.py    # Flask backend with Gemini AI integration
├── requirements.txt      # Python dependencies
├── .env.example         # Example environment variables
├── README.md            # This file
└── src/
    ├── components/      # React components
    ├── lib/             # Utility functions
    ├── pages/           # Application pages
    └── App.tsx          # Main application component
```

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

- Store your API keys securely as environment variables
- Never commit sensitive information to version control
- Implement proper CORS policies in production
- Use HTTPS for all API communications

## 🐛 Troubleshooting

1. **"Could not connect to server"**: Ensure the backend server is running
2. **Authentication errors**: Verify your Supabase credentials
3. **CORS issues**: Check your CORS configuration in the backend
4. **Missing data**: Ensure all required environment variables are set

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with React, Vite, and Supabase
- Powered by Google Gemini AI
- Modern UI with Tailwind CSS

---

<div align="center">
  <p>Developed with ❤️ by Keshav Majithia</p>
</div>
