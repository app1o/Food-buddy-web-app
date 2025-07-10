# Food Buddy 🍽️

A comprehensive food sharing platform that connects food donors with recipients and delivery partners to reduce food waste and help communities access nutritious meals.

## 🌟 Features

### For Donors
- **Food Donation Management**: Easily add and track food donations with photos
- **Location Integration**: GPS-enabled location tracking for accurate pickup addresses
- **Gamification**: Earn points and badges for donations
- **Real-time Tracking**: Monitor donation status from listing to delivery

### For Recipients
- **Smart Food Matching**: AI-powered algorithm finds the best food matches based on preferences
- **Location-Based Search**: Find nearby food donations with distance filtering
- **Request System**: Simple interface to request available food items
- **Delivery Tracking**: Track assigned deliveries in real-time

### For Delivery Partners
- **Route Optimization**: Clarke-Wright algorithm optimizes delivery routes
- **Interactive Maps**: Google Maps integration for navigation
- **Delivery Management**: Accept, start, and complete deliveries with status updates
- **Performance Tracking**: Monitor completed deliveries and earnings

### Universal Features
- **Multi-Role Support**: Users can switch between donor, recipient, and delivery partner roles
- **Dark Mode**: Toggle between light and dark themes
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Secure Authentication**: Password-protected accounts with role-based access

## 🚀 Technology Stack

### Backend
- **Python Flask**: Web framework
- **SQLite**: Database for user data and donations
- **Flask-Login**: User session management
- **Werkzeug**: Password hashing and file handling

### Frontend
- **HTML5/CSS3**: Modern responsive design
- **JavaScript**: Interactive functionality
- **Google Maps API**: Location services and mapping
- **Bootstrap**: UI components and styling

### Algorithms & AI
- **Hungarian Algorithm**: Optimal food matching using scipy
- **Clarke-Wright Savings**: Route optimization for deliveries
- **Haversine Formula**: Distance calculations between coordinates
- **Linear Sum Assignment**: Efficient matching algorithm

### APIs & Services
- **Google Maps API**: Geocoding and mapping services
- **Google Geocoding API**: Address to coordinates conversion
- **Caching System**: LRU cache for performance optimization

## 📋 Prerequisites

- Python 3.7 or higher
- Google Maps API key
- SQLite (included with Python)

## 🔧 Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/food-buddy.git
cd food-buddy
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up Google Maps API**
   - Get a Google Maps API key from [Google Cloud Console](https://console.cloud.google.com/)
   - Enable the following APIs:
     - Maps JavaScript API
     - Geocoding API
     - Places API
   - Update the API key in the code:
```python
app.config['GOOGLE_MAPS_API_KEY'] = 'your-api-key-here'
```

4. **Configure the application**
```python
# Update the secret key for security
app.config['SECRET_KEY'] = 'your-secure-secret-key'

# Create uploads directory
mkdir -p static/uploads
```

## 🏃‍♂️ Running the Application

1. **Start the Flask server**
```bash
python app.py
```

2. **Access the application**
   - Open your browser and navigate to `http://localhost:5000`
   - The database will be automatically created on first run

## 📁 Project Structure

```
food-buddy/
├── app.py                 # Main Flask application
├── user.db               # SQLite database (auto-created)
├── static/
│   ├── uploads/          # Food images
│   ├── css/             # Stylesheets
│   ├── js/              # JavaScript files
│   └── img/             # Static images
├── templates/
│   ├── index.html       # Landing page
│   ├── login.html       # Authentication
│   ├── signup.html      # User registration
│   ├── donor_dashboard.html
│   ├── recipient_dashboard.html
│   ├── delivery_dashboard.html
│   └── reset_password.html
└── requirements.txt     # Python dependencies
```

## 🎯 How It Works

### Registration & Login
1. Users sign up choosing their role (Donor, Recipient, or Delivery Partner)
2. Secure authentication with hashed passwords
3. Role-based dashboard access

### Food Donation Process
1. **Donors** add food items with photos and location
2. **Recipients** browse available items or use smart matching
3. **Recipients** request items they need
4. **Delivery Partners** accept delivery assignments
5. Real-time status updates throughout the process

### Smart Matching Algorithm
- Uses Hungarian algorithm for optimal food-recipient matching
- Considers quantity requirements, location preferences, and expiry dates
- Provides match scores to help users make informed decisions

### Route Optimization
- Clarke-Wright savings algorithm optimizes delivery routes
- Minimizes total distance and travel time
- Provides turn-by-turn navigation integration

## 📊 Database Schema

### Users Table
- User authentication and profile data
- Role-based permissions (donor/recipient/delivery)
- Location coordinates and preferences
- Gamification data (points, level, badges)

### Donations Table
- Food item details and images
- Donor and recipient information
- Delivery partner assignments
- Status tracking and timestamps
- Location coordinates for all parties

## 🔐 Security Features

- Password hashing with Werkzeug
- SQL injection protection with parameterized queries
- File upload validation and sanitization
- Role-based access control
- Session management with Flask-Login

## 🎮 Gamification System

- **Points System**: Earn points for donations and deliveries
- **Level Progression**: Automatic level advancement based on points
- **Badges**: Achievement system for milestones
- **Leaderboards**: Community engagement features

## 📱 Mobile Responsiveness

- Bootstrap-based responsive design
- Touch-friendly interface elements
- Optimized for mobile browsers
- GPS integration for location services

## 🔧 Configuration Options

```python
# File upload settings
UPLOAD_FOLDER = 'static/uploads'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB limit
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Google Maps configuration
GOOGLE_MAPS_API_KEY = 'your-api-key'
GOOGLE_MAPS_LIBRARIES = 'places,geometry'

# Database settings
DATABASE_URL = 'user.db'
```

## 📈 Performance Optimizations

- **Caching**: LRU cache for geocoding results
- **Rate Limiting**: API call throttling
- **Database Optimization**: Indexed queries and efficient joins
- **Image Optimization**: Compressed image storage
- **Lazy Loading**: On-demand content loading

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/yourusername/food-buddy/issues) page
2. Create a new issue with detailed information
3. Include error messages and steps to reproduce

## 🙏 Acknowledgments

- Google Maps API for location services
- Flask community for excellent documentation
- Bootstrap for responsive design components
- SciPy for optimization algorithms
- The open-source community for inspiration

## 📞 Contact

- **Developer**: Your Name
- **Email**: your.email@example.com
- **LinkedIn**: [Your LinkedIn Profile](https://linkedin.com/in/yourprofile)
- **GitHub**: [Your GitHub Profile](https://github.com/yourusername)

---

Made with ❤️ to reduce food waste and help communities thrive.
