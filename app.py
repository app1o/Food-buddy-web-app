import os
import json
import sqlite3
from datetime import datetime, date
from math import radians, sin, cos, sqrt, asin, atan2
from functools import lru_cache
from typing import List, Dict
import numpy as np
from scipy.optimize import linear_sum_assignment
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import requests
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this to a secure secret key
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['GOOGLE_MAPS_API_KEY'] = 'AIzaSyDrrceQef_0ShmLxgyg-VrHv_I1UQJfQB8'
app.config['GEOCODING_API_URL'] = 'https://maps.googleapis.com/maps/api/geocode/json'
app.config['GOOGLE_MAPS_LIBRARIES'] = 'places,geometry'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, email, name, role, points=0, level=1, dark_mode=False):
        self.id = id
        self.email = email
        self.name = name
        self.role = role
        self.points = points if points is not None else 0
        self.level = level if level is not None else 1
        self.dark_mode = dark_mode
    
    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('user.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, name, role, points, level, dark_mode FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        # user[0]=id, user[1]=email, user[2]=name, user[3]=role, user[4]=points, user[5]=level, user[6]=dark_mode
        return User(user[0], user[1], user[2], user[3], user[4], user[5], bool(user[6]))
    return None

def create_tables():
    conn = sqlite3.connect('user.db')
    cursor = conn.cursor()
    
    try:
        # Backup existing data
        users_data = []
        donations_data = []
        try:
            cursor.execute("SELECT * FROM users")
            users_data = cursor.fetchall()
            cursor.execute("SELECT * FROM donations")
            donations_data = cursor.fetchall()
        except sqlite3.Error:
            pass
        
        # Drop existing tables
        cursor.execute('DROP TABLE IF EXISTS donations')
        cursor.execute('DROP TABLE IF EXISTS users')
        
        # Create users table with location coordinates
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('donor', 'recipient', 'delivery')),
            points INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            badges TEXT DEFAULT '[]',
            location TEXT DEFAULT 'Not specified',
            latitude REAL,
            longitude REAL,
            dark_mode BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create donations table with coordinates for both pickup and delivery
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            expiry DATE NOT NULL,
            location TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            recipient_location TEXT,
            recipient_latitude REAL,
            recipient_longitude REAL,
            food_type TEXT NOT NULL CHECK (food_type IN ('vegetables', 'fruits', 'grains', 'protein', 'dairy', 'prepared')),
            image TEXT,
            image_data BLOB,
            donor_id INTEGER NOT NULL,
            recipient_id INTEGER,
            delivery_partner_id INTEGER,
            status TEXT DEFAULT 'available' CHECK (status IN ('available', 'assigned', 'in_delivery', 'delivered')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (donor_id) REFERENCES users (id),
            FOREIGN KEY (recipient_id) REFERENCES users (id),
            FOREIGN KEY (delivery_partner_id) REFERENCES users (id)
        )
        ''')
        
        # Restore users data if any
        if users_data:
            cursor.executemany('''
                INSERT INTO users (id, email, password, name, role, points, level, badges, location, dark_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', users_data)
        
        # Restore donations data if any
        if donations_data:
            cursor.executemany('''
                INSERT INTO donations (
                    id, name, quantity, expiry, location, food_type, image, image_data,
                    donor_id, recipient_id, delivery_partner_id, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', donations_data)
        
        conn.commit()
        print("Database tables created successfully")
        
    except sqlite3.Error as e:
        print(f"Error creating database tables: {e}")
        conn.rollback()
    finally:
        conn.close()

# Initialize database
create_tables()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    roles = [
        {
            'id': 'donor',
            'name': 'Donor',
            'description': 'Share surplus food with those in need.',
            'icon_class': 'text-primary-600 text-xl',
            'bg_class': 'bg-primary-100'
        },
        {
            'id': 'recipient',
            'name': 'Recipient',
            'description': 'Request food for your family or organization.',
            'icon_class': 'text-primary-600 text-xl',
            'bg_class': 'bg-primary-100'
        },
        {
            'id': 'delivery',
            'name': 'Delivery Partner',
            'description': 'Help deliver food to those who need it.',
            'icon_class': 'text-primary-600 text-xl',
            'bg_class': 'bg-primary-100'
        }
    ]

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        role = request.form.get('role')
        
        if not all([email, password, name, role]):
            flash('All fields are required.')
            return render_template('signup.html', roles=roles)
        
        conn = sqlite3.connect('user.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)',
                         (email, generate_password_hash(password), name, role))
            conn.commit()
            
            # Get the user id
            cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
            user_id = cursor.fetchone()[0]
            
            # Create user object and log them in
            user = User(user_id, email, name, role)
            login_user(user)
            
            # Redirect based on role
            return redirect(url_for(f'{role}_dashboard'))
            
        except sqlite3.IntegrityError:
            flash('Email already exists.')
        finally:
            conn.close()
    
    return render_template('signup.html', roles=roles)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please enter both email and password.')
            return render_template('login.html')
        
        try:
            conn = sqlite3.connect('user.db')
            cursor = conn.cursor()
            
            # First check if the user exists
            cursor.execute('SELECT COUNT(*) FROM users WHERE email = ?', (email,))
            if cursor.fetchone()[0] == 0:
                flash('No account found with this email address.')
                return render_template('login.html')
            
            # Get user data
            cursor.execute('''
                SELECT id, email, password, name, role, points, level 
                FROM users 
                WHERE email = ?
            ''', (email,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user[2], password):
                # Create user object with all fields
                user_obj = User(
                    id=user[0],
                    email=user[1],
                    name=user[3],
                    role=user[4],
                    points=user[5],
                    level=user[6]
                )
                login_user(user_obj)
                
                # Log successful login
                print(f"User logged in - Email: {email}, Role: {user[4]}")
                
                # Redirect based on role
                next_page = url_for(f'{user[4]}_dashboard')
                return redirect(next_page)
            else:
                flash('Invalid password.')
                
        except sqlite3.Error as e:
            print(f"Database error during login: {e}")
            flash('An error occurred during login. Please try again.')
        finally:
            conn.close()
            
        flash('Invalid email or password.')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard/delivery')
@login_required
def delivery_dashboard():
    if current_user.role != 'delivery':
        flash('Unauthorized access')
        return redirect(url_for('index'))
    
    conn = sqlite3.connect('user.db')
    cursor = conn.cursor()
    
    try:
        # Get active deliveries (assigned or in_delivery) for this delivery partner
        cursor.execute('''
            SELECT 
                d.id,
                d.name,
                d.quantity,
                d.location as donor_location,
                d.latitude as donor_latitude,
                d.longitude as donor_longitude,
                COALESCE(d.recipient_location, 'Not specified') as recipient_location,
                d.recipient_latitude,
                d.recipient_longitude,
                d.status,
                u1.name as donor_name,
                COALESCE(u2.name, 'Pending') as recipient_name
            FROM donations d
            JOIN users u1 ON d.donor_id = u1.id
            LEFT JOIN users u2 ON d.recipient_id = u2.id
            WHERE d.delivery_partner_id = ? 
            AND d.status IN ('assigned', 'in_delivery')
        ''', (current_user.id,))
        active_deliveries = [dict(zip([
            'id', 'name', 'quantity', 'donor_location', 'donor_latitude', 'donor_longitude',
            'recipient_location', 'recipient_latitude', 'recipient_longitude',
            'status', 'donor_name', 'recipient_name'
        ], row)) for row in cursor.fetchall()]
        
        # Get available deliveries (status = 'available' AND has a recipient)
        cursor.execute('''
            SELECT 
                d.id,
                d.name,
                d.quantity,
                d.location as donor_location,
                d.latitude as donor_latitude,
                d.longitude as donor_longitude,
                COALESCE(d.recipient_location, 'Not specified') as recipient_location,
                d.recipient_latitude,
                d.recipient_longitude,
                u1.name as donor_name,
                COALESCE(u2.name, 'Waiting for delivery') as recipient_name
            FROM donations d
            JOIN users u1 ON d.donor_id = u1.id
            JOIN users u2 ON d.recipient_id = u2.id
            WHERE d.status = 'available'
            AND d.delivery_partner_id IS NULL
        ''')
        available_deliveries = [dict(zip([
            'id', 'name', 'quantity', 'donor_location', 'donor_latitude', 'donor_longitude',
            'recipient_location', 'recipient_latitude', 'recipient_longitude',
            'donor_name', 'recipient_name'
        ], row)) for row in cursor.fetchall()]
        
        # Get completed deliveries count
        cursor.execute('''
            SELECT COUNT(*) 
            FROM donations 
            WHERE delivery_partner_id = ? AND status = 'delivered'
        ''', (current_user.id,))
        completed_deliveries = cursor.fetchone()[0]
        
        return render_template('delivery_dashboard.html',
                             active_deliveries=active_deliveries,
                             available_deliveries=available_deliveries,
                             completed_deliveries=completed_deliveries,
                             google_maps_api_key=app.config['GOOGLE_MAPS_API_KEY'])
    
    except sqlite3.Error as e:
        flash(f'Database error: {str(e)}')
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/dashboard/donor')
@login_required
def donor_dashboard():
    if current_user.role != 'donor':
        flash('Access denied.')
        return redirect(url_for('login'))
    
    # Get donor's stats
    conn = sqlite3.connect('user.db')
    cursor = conn.cursor()
    
    # Get donations count
    cursor.execute('SELECT COUNT(*) FROM donations WHERE donor_id = ?', (current_user.id,))
    donations_count = cursor.fetchone()[0]
    
    # Get user's points, level, and badges
    cursor.execute('SELECT points, level, badges FROM users WHERE id = ?', (current_user.id,))
    user_data = cursor.fetchone()
    current_user.points = user_data[0]
    current_user.level = user_data[1]
    badges = json.loads(user_data[2])
    
    # Calculate impact score (example: 10 points per donation)
    impact_score = donations_count * 10
    
    # Get user counts for each role
    cursor.execute('''
        SELECT role, COUNT(*) 
        FROM users 
        GROUP BY role
    ''')
    user_counts = dict(cursor.fetchall())
    
    # Get active donations (available or in progress)
    cursor.execute('''
        SELECT 
            d.id,
            d.name,
            d.quantity,
            d.expiry,
            d.location,
            d.food_type,
            d.status,
            COALESCE(r.name, 'Not requested yet') as recipient_name,
            COALESCE(dp.name, 'No delivery partner yet') as delivery_partner_name
        FROM donations d
        LEFT JOIN users r ON d.recipient_id = r.id
        LEFT JOIN users dp ON d.delivery_partner_id = dp.id
        WHERE d.donor_id = ?
        AND d.status != 'delivered'
        ORDER BY 
            CASE d.status
                WHEN 'available' THEN 1
                WHEN 'assigned' THEN 2
                WHEN 'in_delivery' THEN 3
            END,
            d.created_at DESC
    ''', (current_user.id,))
    
    active_donations = [dict(zip([
        'id', 'name', 'quantity', 'expiry', 'location', 'food_type', 
        'status', 'recipient_name', 'delivery_partner_name'
    ], row)) for row in cursor.fetchall()]
    
    # Get completed donations
    cursor.execute('''
        SELECT 
            d.id,
            d.name,
            d.quantity,
            d.expiry,
            d.location,
            d.food_type,
            r.name as recipient_name,
            dp.name as delivery_partner_name,
            d.created_at
        FROM donations d
        JOIN users r ON d.recipient_id = r.id
        JOIN users dp ON d.delivery_partner_id = dp.id
        WHERE d.donor_id = ?
        AND d.status = 'delivered'
        ORDER BY d.created_at DESC
        LIMIT 5
    ''', (current_user.id,))
    
    completed_donations = [dict(zip([
        'id', 'name', 'quantity', 'expiry', 'location', 'food_type',
        'recipient_name', 'delivery_partner_name', 'created_at'
    ], row)) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('donor_dashboard.html',
                         donations_count=donations_count,
                         badges=badges,
                         impact_score=impact_score,
                         user_counts=user_counts,
                         active_donations=active_donations,
                         completed_donations=completed_donations)

@app.route('/dashboard/recipient')
@login_required
def recipient_dashboard():
    if current_user.role != 'recipient':
        flash('Access denied.')
        return redirect(url_for('login'))
    
    # Get recipient's stats
    conn = sqlite3.connect('user.db')
    cursor = conn.cursor()
    
    # Get available donations count
    cursor.execute('SELECT COUNT(*) FROM donations WHERE status = "available" AND recipient_id IS NULL')
    available_count = cursor.fetchone()[0]
    
    # Get assigned donations count
    cursor.execute('SELECT COUNT(*) FROM donations WHERE status = "assigned" AND recipient_id = ?', (current_user.id,))
    assigned_count = cursor.fetchone()[0]
    
    # Get received donations count
    cursor.execute('SELECT COUNT(*) FROM donations WHERE status = "delivered" AND recipient_id = ?', (current_user.id,))
    received_count = cursor.fetchone()[0]
    
    # Get user's points, level, and badges
    cursor.execute('SELECT points, level, badges FROM users WHERE id = ?', (current_user.id,))
    user_data = cursor.fetchone()
    points = user_data[0]
    level = user_data[1]
    badges = json.loads(user_data[2])
    
    # Get available donations with donor information
    cursor.execute('''
        SELECT 
            d.id,
            d.name,
            d.quantity,
            d.expiry,
            d.location,
            d.image,
            u.name as donor_name 
        FROM donations d 
        JOIN users u ON d.donor_id = u.id 
        WHERE d.status = 'available' AND d.recipient_id IS NULL
        ORDER BY 
            CASE WHEN d.id = ? THEN 0 ELSE 1 END,
            d.created_at DESC
    ''', (request.args.get('highlight_id', -1),))
    available_items = [dict(zip(['id', 'name', 'quantity', 'expiry', 'location', 'image', 'donor_name'], row)) 
                      for row in cursor.fetchall()]
    
    # Get assigned donations
    cursor.execute('''
        SELECT 
            d.id,
            d.name,
            d.quantity,
            d.status,
            d.expiry,
            d.location,
            d.image,
            u.name as donor_name 
        FROM donations d 
        JOIN users u ON d.donor_id = u.id 
        WHERE d.recipient_id = ? AND d.status IN ('assigned', 'in_delivery')
    ''', (current_user.id,))
    assigned_items = [dict(zip(['id', 'name', 'quantity', 'status', 'expiry', 'location', 'image', 'donor_name'], row)) 
                     for row in cursor.fetchall()]
    
    # Get food requests (all donations requested by this recipient)
    cursor.execute('''
        SELECT 
            d.id,
            d.name as item_name,
            d.quantity,
            d.status,
            d.created_at,
            u.name as donor_name,
            CASE 
                WHEN d.status = 'available' THEN 'pending'
                WHEN d.status = 'assigned' THEN 'approved'
                WHEN d.status = 'in_delivery' THEN 'approved'
                WHEN d.status = 'delivered' THEN 'completed'
            END as request_status
        FROM donations d 
        JOIN users u ON d.donor_id = u.id 
        WHERE d.recipient_id = ?
        ORDER BY d.created_at DESC
    ''', (current_user.id,))
    food_requests = [dict(zip(['id', 'item_name', 'quantity', 'status', 'created_at', 'donor_name', 'status'], row)) 
                    for row in cursor.fetchall()]
    
    conn.close()
    
    stats = {
        'available': available_count,
        'assigned': assigned_count,
        'received': received_count
    }
    
    return render_template('recipient_dashboard.html',
                         stats=stats,
                         points=points,
                         level=level,
                         badges=badges,
                         available_items=available_items,
                         assigned_items=assigned_items,
                         food_requests=food_requests,
                         config={'GOOGLE_MAPS_API_KEY': app.config['GOOGLE_MAPS_API_KEY']})

@app.route('/donation/add', methods=['POST'])
@login_required
def add_donation():
    if current_user.role != 'donor':
        flash('Access denied.')
        return redirect(url_for('login'))

    name = request.form.get('name')
    quantity = request.form.get('quantity')
    expiry = request.form.get('expiry')
    location = request.form.get('location')
    food_type = request.form.get('food_type')
    latitude = request.form.get('lat')
    longitude = request.form.get('lng')
    image = request.files.get('image')

    if not all([name, quantity, expiry, location, food_type, latitude, longitude]):
        flash('All fields are required.')
        return redirect(url_for('donor_dashboard'))

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (ValueError, TypeError):
        flash('Invalid coordinates provided.')
        return redirect(url_for('donor_dashboard'))

    image_data = None
    filename = None
    if image and allowed_file(image.filename):
        image_data = image.read()
        filename = secure_filename(image.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(image_path, 'wb') as f:
            f.write(image_data)

    try:
        conn = sqlite3.connect('user.db')
        cursor = conn.cursor()
        
        # Add donation with coordinates
        cursor.execute('''
            INSERT INTO donations (
                name, quantity, expiry, location, latitude, longitude,
                food_type, image, image_data, donor_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, quantity, expiry, location, latitude, longitude,
              food_type, filename, image_data, current_user.id))
        
        # Update user points
        cursor.execute('''
            UPDATE users 
            SET points = points + 10
            WHERE id = ?
        ''', (current_user.id,))
        
        conn.commit()
        flash('Donation added successfully!')
        
    except sqlite3.Error as e:
        flash(f'Error adding donation: {str(e)}')
    finally:
        conn.close()

    return redirect(url_for('donor_dashboard'))

@app.route('/donation/image/<int:donation_id>')
def get_donation_image(donation_id):
    try:
        conn = sqlite3.connect('user.db')
        cursor = conn.cursor()
        cursor.execute('SELECT image, image_data FROM donations WHERE id = ?', (donation_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            # If we have image_data (BLOB), serve it directly
            if result[1]:
                response = make_response(result[1])
                response.headers.set('Content-Type', 'image/jpeg')
                return response
            # If we have image path, serve from uploads folder
            elif result[0]:
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], result[0])
                if os.path.exists(image_path):
                    return send_file(image_path, mimetype='image/jpeg')
        
        # If no image found or error, return default image
        default_image_path = os.path.join(app.root_path, 'static', 'img', 'default-food.png')
        return send_file(default_image_path, mimetype='image/png')
        
    except Exception as e:
        print(f"Error serving image: {str(e)}")
        default_image_path = os.path.join(app.root_path, 'static', 'img', 'default-food.png')
        return send_file(default_image_path, mimetype='image/png')

@app.route('/donation/request', methods=['POST'])
@login_required
def request_food():
    if current_user.role != 'recipient':
        flash('Access denied.')
        return redirect(url_for('login'))

    item_id = request.form.get('item_id')
    recipient_location = request.form.get('recipient_location')
    recipient_lat = request.form.get('recipient_lat')
    recipient_lng = request.form.get('recipient_lng')

    if not all([item_id, recipient_location, recipient_lat, recipient_lng]):
        flash('All location details are required.')
        return redirect(url_for('recipient_dashboard'))

    try:
        recipient_lat = float(recipient_lat)
        recipient_lng = float(recipient_lng)
    except (ValueError, TypeError):
        flash('Invalid coordinates provided.')
        return redirect(url_for('recipient_dashboard'))

    try:
        conn = sqlite3.connect('user.db')
        cursor = conn.cursor()
        
        # Check if item is still available
        cursor.execute('''
            SELECT status, recipient_id 
            FROM donations 
            WHERE id = ?
        ''', (item_id,))
        item = cursor.fetchone()
        
        if not item or item[0] != 'available' or item[1] is not None:
            flash('This item is no longer available.')
            conn.close()
            return redirect(url_for('recipient_dashboard'))
        
        # Associate the item with the recipient and store location
        cursor.execute('''
            UPDATE donations 
            SET recipient_id = ?,
                recipient_location = ?,
                recipient_latitude = ?,
                recipient_longitude = ?
            WHERE id = ? AND status = 'available' AND recipient_id IS NULL
        ''', (current_user.id, recipient_location, recipient_lat, recipient_lng, item_id))
        
        if cursor.rowcount > 0:
            # Add points to recipient
            cursor.execute('''
                UPDATE users 
                SET points = points + 5
                WHERE id = ?
            ''', (current_user.id,))
            
            conn.commit()
            flash('Food item requested successfully! A delivery partner will be assigned soon.')
        else:
            flash('Unable to request this item. It may have been assigned to someone else.')
            
    except sqlite3.Error as e:
        flash(f'Error requesting food: {str(e)}')
    finally:
        conn.close()

    return redirect(url_for('recipient_dashboard'))

@app.route('/find_best_match', methods=['POST'])
@login_required
def find_best_match():
    if current_user.role != 'recipient':
        flash('Access denied.')
        return redirect(url_for('login'))

    food_type = request.form.get('food_type')
    quantity_needed = int(request.form.get('quantity_needed'))
    preferred_location = request.form.get('preferred_location')
    max_distance = int(request.form.get('max_distance'))
    additional_notes = request.form.get('additional_notes')

    try:
        conn = sqlite3.connect('user.db')
        cursor = conn.cursor()

        # Get all current stats and user data
        cursor.execute('SELECT COUNT(*) FROM donations WHERE status = "available" AND recipient_id IS NULL')
        available_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM donations WHERE status = "assigned" AND recipient_id = ?', (current_user.id,))
        assigned_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM donations WHERE status = "delivered" AND recipient_id = ?', (current_user.id,))
        received_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT points, level, badges FROM users WHERE id = ?', (current_user.id,))
        user_data = cursor.fetchone()
        points = user_data[0]
        level = user_data[1]
        badges = json.loads(user_data[2])

        # Find matching donations
        cursor.execute('''
            SELECT 
                d.id,
                d.name,
                d.quantity,
                d.expiry,
                d.location,
                d.image,
                u.name as donor_name,
                CASE 
                    WHEN d.location = ? THEN 0
                    ELSE 1
                END as location_match
            FROM donations d
            JOIN users u ON d.donor_id = u.id
            WHERE d.status = 'available' 
            AND d.recipient_id IS NULL
            AND d.name LIKE ?
            AND d.quantity >= ?
            ORDER BY 
                location_match ASC,
                d.expiry ASC,
                d.quantity ASC
            LIMIT 5
        ''', (preferred_location, f'%{food_type}%', quantity_needed))

        available_items = [dict(zip(['id', 'name', 'quantity', 'expiry', 'location', 'image', 'donor_name', 'location_match'], row)) 
                         for row in cursor.fetchall()]

        # Get assigned items
        cursor.execute('''
            SELECT 
                d.id,
                d.name,
                d.quantity,
                d.status,
                d.expiry,
                d.location,
                d.image,
                u.name as donor_name 
            FROM donations d 
            JOIN users u ON d.donor_id = u.id 
            WHERE d.recipient_id = ? AND d.status IN ('assigned', 'in_delivery')
        ''', (current_user.id,))
        assigned_items = [dict(zip(['id', 'name', 'quantity', 'status', 'expiry', 'location', 'image', 'donor_name'], row)) 
                        for row in cursor.fetchall()]
        
        conn.close()

        stats = {
            'available': available_count,
            'assigned': assigned_count,
            'received': received_count
        }

        if available_items:
            flash('Found matching food items!')
        else:
            flash('No matching food items found. Please try different criteria.')

        return render_template('recipient_dashboard.html',
                            stats=stats,
                            points=points,
                            level=level,
                            badges=badges,
                            available_items=available_items,
                            assigned_items=assigned_items,
                            show_match_results=True,
                            match_query={
                                'food_type': food_type,
                                'quantity_needed': quantity_needed,
                                'preferred_location': preferred_location,
                                'max_distance': max_distance
                            })
            
    except sqlite3.Error as e:
        flash(f'Error finding matches: {str(e)}')
        return redirect(url_for('recipient_dashboard'))

@app.route('/delivery/accept', methods=['POST'])
@login_required
def accept_delivery():
    if current_user.role != 'delivery':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    delivery_id = data.get('delivery_id')
    
    if not delivery_id:
        return jsonify({'success': False, 'message': 'Delivery ID is required'}), 400
    
    conn = sqlite3.connect('user.db')
    cursor = conn.cursor()
    
    try:
        # Check if delivery is available
        cursor.execute('SELECT status FROM donations WHERE id = ?', (delivery_id,))
        result = cursor.fetchone()
        
        if not result or result[0] != 'available':
            conn.close()
            return jsonify({'success': False, 'message': 'Delivery not available'}), 400
        
        # Update delivery status and assign delivery partner
        cursor.execute('''
            UPDATE donations 
            SET status = 'assigned', delivery_partner_id = ? 
            WHERE id = ?
        ''', (current_user.id, delivery_id))
        
        # Add points for accepting delivery
        cursor.execute('''
            UPDATE users 
            SET points = points + 5 
            WHERE id = ?
        ''', (current_user.id,))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Delivery accepted successfully'})
        
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/delivery/start', methods=['POST'])
@login_required
def start_delivery():
    if current_user.role != 'delivery':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    delivery_id = data.get('delivery_id')
    
    if not delivery_id:
        return jsonify({'success': False, 'message': 'Delivery ID is required'}), 400
    
    conn = sqlite3.connect('user.db')
    cursor = conn.cursor()
    
    try:
        # Check if delivery is assigned to this delivery partner
        cursor.execute('''
            SELECT status 
            FROM donations 
            WHERE id = ? AND delivery_partner_id = ? AND status = 'assigned'
        ''', (delivery_id, current_user.id))
        
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': 'Delivery not found or not assigned to you'}), 400
        
        # Update delivery status
        cursor.execute('''
            UPDATE donations 
            SET status = 'in_delivery' 
            WHERE id = ?
        ''', (delivery_id,))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Delivery started successfully'})
        
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/delivery/complete', methods=['POST'])
@login_required
def complete_delivery():
    if current_user.role != 'delivery':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    delivery_id = data.get('delivery_id')
    
    if not delivery_id:
        return jsonify({'success': False, 'message': 'Delivery ID is required'}), 400
    
    conn = sqlite3.connect('user.db')
    cursor = conn.cursor()
    
    try:
        # Check if delivery is in progress by this delivery partner
        cursor.execute('''
            SELECT status 
            FROM donations 
            WHERE id = ? AND delivery_partner_id = ? AND status = 'in_delivery'
        ''', (delivery_id, current_user.id))
        
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': 'Delivery not found or not in progress'}), 400
        
        # Update delivery status
        cursor.execute('''
            UPDATE donations 
            SET status = 'delivered' 
            WHERE id = ?
        ''', (delivery_id,))
        
        # Add points for completing delivery
        cursor.execute('''
            UPDATE users 
            SET points = points + 10,
                level = CASE 
                    WHEN points >= 100 THEN 3
                    WHEN points >= 50 THEN 2
                    ELSE 1
                END
            WHERE id = ?
        ''', (current_user.id,))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Delivery completed successfully'})
        
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/request/cancel', methods=['POST'])
@login_required
def cancel_request():
    if current_user.role != 'recipient':
        flash('Access denied.')
        return redirect(url_for('login'))

    request_id = request.form.get('request_id')
    if not request_id:
        flash('Invalid request.')
        return redirect(url_for('recipient_dashboard'))

    try:
        conn = sqlite3.connect('user.db')
        cursor = conn.cursor()
        
        # Check if request exists and belongs to this recipient
        cursor.execute('''
            SELECT status 
            FROM donations 
            WHERE id = ? AND recipient_id = ? AND status = 'available'
        ''', (request_id, current_user.id))
        request = cursor.fetchone()
        
        if not request:
            flash('Request not found or cannot be cancelled.')
            conn.close()
            return redirect(url_for('recipient_dashboard'))
        
        # Remove recipient from the donation
        cursor.execute('''
            UPDATE donations 
            SET recipient_id = NULL 
            WHERE id = ? AND recipient_id = ? AND status = 'available'
        ''', (request_id, current_user.id))
        
        if cursor.rowcount > 0:
            # Remove points that were awarded for the request
            cursor.execute('''
                UPDATE users 
                SET points = points - 5
                WHERE id = ?
            ''', (current_user.id,))
            
            conn.commit()
            flash('Food request cancelled successfully.')
        else:
            flash('Unable to cancel request. It may have already been assigned.')
            
    except sqlite3.Error as e:
        flash(f'Error cancelling request: {str(e)}')
    finally:
        conn.close()

    return redirect(url_for('recipient_dashboard'))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([email, new_password, confirm_password]):
            flash('Please fill in all fields.')
            return render_template('reset_password.html')
            
        if new_password != confirm_password:
            flash('Passwords do not match.')
            return render_template('reset_password.html')
        
        try:
            conn = sqlite3.connect('user.db')
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
            user = cursor.fetchone()
            
            if not user:
                flash('No account found with this email address.')
                return render_template('reset_password.html')
            
            # Update password
            hashed_password = generate_password_hash(new_password)
            cursor.execute('UPDATE users SET password = ? WHERE email = ?', 
                         (hashed_password, email))
            conn.commit()
            
            flash('Password has been reset successfully. Please login with your new password.')
            return redirect(url_for('login'))
            
        except sqlite3.Error as e:
            flash('An error occurred. Please try again.')
        finally:
            conn.close()
    
    return render_template('reset_password.html')

@app.route('/api/recommendations', methods=['GET'])
@login_required
def get_recommendations():
    preferences = {
        'food_type': request.args.get('food_type'),
        'location': request.args.get('location')
    }
    recommendations = food_agent.get_food_recommendations(current_user.id, preferences)
    return jsonify(recommendations)

@app.route('/api/donation-needs/<location>', methods=['GET'])
@login_required
def get_donation_needs(location):
    needs = food_agent.predict_donation_needs(location)
    return jsonify(needs)

@app.route('/api/optimize-routes', methods=['GET'])
@login_required
def get_optimized_routes():
    if current_user.role != 'delivery':
        return jsonify({'error': 'Unauthorized'}), 403
    routes = food_agent.optimize_delivery_routes(current_user.id)
    return jsonify(routes)

@app.route('/api/user-impact', methods=['GET'])
@login_required
def get_user_impact():
    impact = food_agent.analyze_user_impact(current_user.id)
    return jsonify(impact)

@app.route('/api/preferences/dark-mode', methods=['POST'])
@login_required
def update_dark_mode():
    try:
        data = request.get_json()
        dark_mode = data.get('darkMode', False)
        
        conn = sqlite3.connect('user.db')
        cursor = conn.cursor()
        
        # Update user's dark mode preference
        cursor.execute('''
            UPDATE users 
            SET dark_mode = ? 
            WHERE id = ?
        ''', (1 if dark_mode else 0, current_user.id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'darkMode': dark_mode})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/preferences/dark-mode', methods=['GET'])
@login_required
def get_dark_mode():
    try:
        conn = sqlite3.connect('user.db')
        cursor = conn.cursor()
        
        # Get user's dark mode preference
        cursor.execute('SELECT dark_mode FROM users WHERE id = ?', (current_user.id,))
        result = cursor.fetchone()
        dark_mode = bool(result[0]) if result else False
        
        conn.close()
        
        return jsonify({'success': True, 'darkMode': dark_mode})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Add geocoding cache
@lru_cache(maxsize=1000)
def geocode_address(address):
    """Convert address to coordinates using Google Geocoding API with caching"""
    # Check if address is in database cache first
    conn = sqlite3.connect('user.db')
    cursor = conn.cursor()
    
    try:
        # Create geocoding cache table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                address TEXT PRIMARY KEY,
                coordinates TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Check cache
        cursor.execute('SELECT coordinates FROM geocoding_cache WHERE address = ?', (address,))
        result = cursor.fetchone()
        
        if result:
            return tuple(json.loads(result[0]))
        
        # If not in cache, call Google API
        params = {
            'address': address,
            'key': app.config['GOOGLE_MAPS_API_KEY']
        }
        
        response = requests.get(app.config['GEOCODING_API_URL'], params=params)
        data = response.json()
        
        if data['status'] == 'OK':
            location = data['results'][0]['geometry']['location']
            coordinates = (location['lat'], location['lng'])
            
            # Store in cache
            cursor.execute('''
                INSERT OR REPLACE INTO geocoding_cache (address, coordinates)
                VALUES (?, ?)
            ''', (address, json.dumps(coordinates)))
            
            conn.commit()
            return coordinates
            
        return None
        
    finally:
        conn.close()

# Add this function to periodically clean old cache entries
def clean_geocoding_cache():
    """Remove geocoding cache entries older than 30 days"""
    conn = sqlite3.connect('user.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            DELETE FROM geocoding_cache 
            WHERE timestamp < datetime('now', '-30 days')
        ''')
        conn.commit()
    finally:
        conn.close()

# Add rate limiting for API calls
def rate_limit_decorator(max_calls, time_window):
    calls = []
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            now = datetime.now()
            # Remove old calls
            while calls and (now - calls[0]).total_seconds() > time_window:
                calls.pop(0)
            
            if len(calls) >= max_calls:
                wait_time = time_window - (now - calls[0]).total_seconds()
                if wait_time > 0:
                    time.sleep(wait_time)
                    calls.pop(0)
            
            calls.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Apply rate limiting to route optimization
@rate_limit_decorator(max_calls=25, time_window=1)  # 25 calls per second
def optimize_delivery_routes():
    if current_user.role != 'delivery':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        conn = sqlite3.connect('user.db')
        cursor = conn.cursor()
        
        # Get active deliveries for this delivery partner
        cursor.execute('''
            SELECT 
                d.id,
                d.name,
                d.location as donor_location,
                COALESCE(u.location, 'Not specified') as recipient_location,
                d.status
            FROM donations d
            LEFT JOIN users u ON d.recipient_id = u.id
            WHERE d.delivery_partner_id = ?
            AND d.status IN ('assigned', 'in_delivery')
        ''', (current_user.id,))
        
        deliveries = [dict(zip(['id', 'name', 'donor_location', 'recipient_location', 'status'], row))
                     for row in cursor.fetchall()]
        
        # Get delivery partner's current location as depot
        cursor.execute('SELECT location FROM users WHERE id = ?', (current_user.id,))
        depot_location = cursor.fetchone()[0]
        
        # Convert all addresses to coordinates
        locations = []
        
        # Add depot as first location
        depot_coords = geocode_address(depot_location)
        if depot_coords:
            locations.append({
                'lat': depot_coords[0],
                'lng': depot_coords[1],
                'type': 'depot',
                'name': 'Current Location'
            })
        
        # Add delivery locations
        for delivery in deliveries:
            # Add donor location
            donor_coords = geocode_address(delivery['donor_location'])
            if donor_coords:
                locations.append({
                    'lat': donor_coords[0],
                    'lng': donor_coords[1],
                    'type': 'pickup',
                    'name': f"Pickup: {delivery['name']}",
                    'delivery_id': delivery['id']
                })
            
            # Add recipient location
            recipient_coords = geocode_address(delivery['recipient_location'])
            if recipient_coords:
                locations.append({
                    'lat': recipient_coords[0],
                    'lng': recipient_coords[1],
                    'type': 'delivery',
                    'name': f"Delivery: {delivery['name']}",
                    'delivery_id': delivery['id']
                })
        
        # Optimize routes using Clarke-Wright algorithm
        optimized_routes = clarke_wright_savings(locations)
        
        # Calculate estimated times and distances
        route_details = []
        total_distance = 0
        total_time = 0
        
        for route in optimized_routes:
            route_distance = 0
            for i in range(len(route)-1):
                distance = calculate_distance(
                    route[i]['lat'], route[i]['lng'],
                    route[i+1]['lat'], route[i+1]['lng']
                )
                route_distance += distance
            
            # Estimate time (assuming average speed of 30 km/h)
            estimated_time = (route_distance / 30) * 60  # Convert to minutes
            
            route_details.append({
                'stops': route,
                'distance': round(route_distance, 2),
                'estimated_time': round(estimated_time)
            })
            
            total_distance += route_distance
            total_time += estimated_time
        
        return jsonify({
            'success': True,
            'routes': route_details,
            'total_distance': round(total_distance, 2),
            'total_time': round(total_time),
            'deliveries_count': len(deliveries)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula"""
    R = 6371  # Earth's radius in kilometers

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c

    return distance

def clarke_wright_savings(depot, locations):
    """
    Implement Clarke-Wright savings algorithm for route optimization
    depot: dict with lat, lng of depot location
    locations: list of dicts with lat, lng, and other location details
    """
    if len(locations) <= 2:
        return locations

    # Calculate savings for all location pairs
    savings = []
    for i in range(len(locations)):
        for j in range(i + 1, len(locations)):
            # Calculate savings = dist(depot,i) + dist(depot,j) - dist(i,j)
            saving = (
                calculate_distance(depot['lat'], depot['lng'], 
                                locations[i]['lat'], locations[i]['lng']) +
                calculate_distance(depot['lat'], depot['lng'],
                                locations[j]['lat'], locations[j]['lng']) -
                calculate_distance(locations[i]['lat'], locations[i]['lng'],
                                locations[j]['lat'], locations[j]['lng'])
            )
            savings.append({
                'i': i,
                'j': j,
                'saving': saving
            })

    # Sort savings in descending order
    savings.sort(key=lambda x: x['saving'], reverse=True)

    # Build routes
    routes = []
    used = set()

    for save in savings:
        if save['i'] not in used and save['j'] not in used:
            route = [locations[save['i']], locations[save['j']]]
            used.add(save['i'])
            used.add(save['j'])
            routes.append(route)

    # Add unused locations as single-point routes
    for i in range(len(locations)):
        if i not in used:
            routes.append([locations[i]])

    return routes

def calculate_days_until_expiry(expiry_date):
    """Calculate the number of days until expiry"""
    if isinstance(expiry_date, str):
        expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
    today = date.today()
    delta = expiry_date - today
    return max(0, delta.days) / 30  # Normalize to 0-1 range assuming 30 days max

def create_cost_matrix(items: List[Dict], request_params: Dict) -> np.ndarray:
    """Create cost matrix for Hungarian algorithm considering multiple factors"""
    n = len(items)
    if n == 0:
        return np.array([[]])
        
    cost_matrix = np.zeros((n, n))
    quantity_requested = float(request_params['quantity'])
    print("\nRequest parameters:")
    print(f"Quantity requested: {quantity_requested}")

    for i in range(n):
        for j in range(n):
            item = items[i]
            quantity_available = float(item['quantity'])
            
            # Calculate absolute difference from requested quantity
            quantity_diff = abs(quantity_available - quantity_requested)
            
            # Convert to a cost where 0 means perfect match
            # and higher values mean bigger difference
            if quantity_available == quantity_requested:
                cost = 0  # Perfect match
            else:
                # Calculate percentage difference from requested quantity
                cost = (quantity_diff / quantity_requested) * 100
            
            print(f"\nItem: {item['name']}")
            print(f"Available: {quantity_available}, Requested: {quantity_requested}")
            print(f"Cost: {cost:.2f}")
            
            cost_matrix[i][j] = cost
    
    return cost_matrix

def calculate_match_score(requested_quantity: float, available_quantity: float) -> float:
    """Calculate match score (0-100) based on quantity difference"""
    if available_quantity == requested_quantity:
        return 100.0
    
    # Calculate percentage difference
    diff_ratio = abs(available_quantity - requested_quantity) / requested_quantity
    
    # Convert to score (0-100)
    # The closer the quantities, the higher the score
    score = max(0, 100 * (1 - diff_ratio))
    
    return score

def hungarian_algorithm(cost_matrix: np.ndarray) -> List[Dict]:
    """Implementation of Hungarian algorithm for optimal assignment"""
    # Use scipy's implementation for efficiency
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    
    assignments = []
    for i, j in zip(row_ind, col_ind):
        assignments.append({
            'row': int(i),
            'col': int(j),
            'cost': float(cost_matrix[i, j])
        })
    
    return assignments

@app.route('/api/find_optimal_matches', methods=['POST'])
@login_required
def find_optimal_matches():
    """API endpoint for finding optimal food matches"""
    try:
        data = request.get_json()
        print("\n=== Starting find_optimal_matches ===")
        print("Received data:", data)
        
        # Validate request parameters
        required_params = ['food_type', 'quantity']
        if not all(param in data for param in required_params):
            missing = [param for param in required_params if param not in data]
            print("Missing parameters:", missing)
            return jsonify({'error': 'Missing required parameters'}), 400

        try:
            requested_quantity = float(data['quantity'])
        except (ValueError, TypeError) as e:
            print("Parameter conversion error:", str(e))
            return jsonify({'error': 'Invalid quantity parameter'}), 400

        # Get available items from database
        conn = sqlite3.connect('user.db')
        cursor = conn.cursor()
        
        query = '''
            SELECT 
                d.id,
                d.name,
                d.quantity,
                d.food_type,
                d.expiry,
                d.location,
                d.latitude,
                d.longitude,
                u.name as donor_name,
                d.image
            FROM donations d
            JOIN users u ON d.donor_id = u.id
            WHERE d.status = 'available'
            AND d.food_type = ?
            AND d.quantity > 0
        '''
        
        cursor.execute(query, (data['food_type'],))
        rows = cursor.fetchall()
        print(f"\nFound {len(rows)} matching items")
        
        items = []
        for row in rows:
            item = {
                'id': row[0],
                'name': row[1],
                'quantity': row[2],
                'food_type': row[3],
                'expiry': row[4],
                'location': row[5],
                'latitude': row[6],
                'longitude': row[7],
                'donor_name': row[8],
                'image_path': row[9]
            }
            items.append(item)
        
        if not items:
            return jsonify({'matches': []}), 200

        # Create cost matrix and find optimal matches
        cost_matrix = create_cost_matrix(items, data)
        assignments = hungarian_algorithm(cost_matrix)
        
        # Convert assignments to scored items
        scored_items = []
        for assignment in assignments:
            item = items[assignment['row']]
            
            # Calculate match score based on quantity difference
            match_score = calculate_match_score(requested_quantity, float(item['quantity']))
            
            scored_items.append({
                'item': item,
                'score': match_score
            })
        
        # Sort by score descending
        scored_items.sort(key=lambda x: x['score'], reverse=True)
        
        print("\nScored matches:")
        for item in scored_items:
            print(f"Item: {item['item']['name']}")
            print(f"Quantity: {item['item']['quantity']}")
            print(f"Score: {item['score']:.1f}%")
        
        return jsonify({
            'matches': scored_items
        }), 200

    except Exception as e:
        print(f"\nError in find_optimal_matches: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 