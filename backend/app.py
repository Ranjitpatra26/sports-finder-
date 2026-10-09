from datetime import datetime, timedelta

from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from models import db, User, Tournament, Team, TeamRequest, Registration, Comment, Turf, TurfBooking
from config import Config
from utils import haversine
from mongo_db import MongoDB

app = Flask(__name__)
app.config.from_object(Config)
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)

db.init_app(app)
jwt = JWTManager(app)
CORS(app)

mongo = MongoDB(Config.MONGO_URI)

def seed_mongo_sample_data():
    if not mongo.is_connected:
        return

    organizer_email = 'sample.organizer@sports.local'
    organizer = mongo.get_user_by_email(organizer_email)
    if not organizer:
        organizer = mongo.create_user(
            name='Sample Organizer',
            email=organizer_email,
            password_hash=generate_password_hash('sample1234'),
            role='organizer',
            latitude=19.0760,
            longitude=72.8777
        )

    turf_owner_email = 'owner@turf.local'
    owner = mongo.get_user_by_email(turf_owner_email)
    if not owner:
        owner = mongo.create_user(
            name='Rajesh Turf Owner',
            email=turf_owner_email,
            password_hash=generate_password_hash('owner1234'),
            role='turf_owner',
            latitude=19.0760,
            longitude=72.8777
        )

    sample_tournaments = [
        {
            'name': 'Basketball Championship',
            'sport': 'Basketball',
            'date': '2026-03-20',
            'entry_fee': 50.0,
            'mode': 'team',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'organizer_id': organizer['id'],
            'venue_name': 'Downtown Indoor Arena',
            'venue_address': '42 City Center Plaza, Manhattan, New York, NY 10001',
            'organizer_phone': '+1-555-0101',
            'organizer_verified': True
        },
        {
            'name': 'Soccer Open Cup',
            'sport': 'Soccer',
            'date': '2026-03-25',
            'entry_fee': 30.0,
            'mode': 'team',
            'latitude': 40.7580,
            'longitude': -73.9855,
            'organizer_id': organizer['id'],
            'venue_name': 'Midtown Turf Ground',
            'venue_address': '78 8th Avenue, Midtown, New York, NY 10018',
            'organizer_phone': '+1-555-0102',
            'organizer_verified': True
        },
        {
            'name': 'Mumbai Football Cup',
            'sport': 'Football',
            'date': '2026-03-10',
            'entry_fee': 500.0,
            'mode': 'team',
            'latitude': 19.0760,
            'longitude': 72.8777,
            'organizer_id': organizer['id'],
            'venue_name': 'Shivaji Sports Complex',
            'venue_address': 'Senapati Bapat Marg, Dadar West, Mumbai, Maharashtra 400028',
            'organizer_phone': '+91-90000-11111',
            'organizer_verified': True
        }
    ]

    for st in sample_tournaments:
        existing = mongo.db.tournaments.find_one({'name': st['name'], 'date': st['date']})
        if not existing:
            mongo.create_tournament(**st)

    # Seed sample turfs
    sample_turfs = [
        {
            'name': 'Kickoff Turf Bandra West',
            'owner_id': owner['id'],
            'sport': 'Football',
            'address': 'Hill Road, Bandra West, Mumbai, Maharashtra 400050',
            'latitude': 19.0544,
            'longitude': 72.8402,
            'price_per_hour': 1200.0,
            'rating': 4.9,
            'facilities': ['Floodlights', 'Changing Room', 'Parking', 'Drinking Water', 'Artificial Turf'],
            'rules': 'Studs not allowed. Soft turf shoes required. Arrive 10 mins early.',
            'image_url': 'https://images.unsplash.com/photo-1529900748604-07564a03e7a6?auto=format&fit=crop&w=600&q=80',
            'opening_time': '06:00',
            'closing_time': '23:00'
        },
        {
            'name': 'Arena 57 Turf Juhu',
            'owner_id': owner['id'],
            'sport': 'Cricket',
            'address': 'Juhu Tara Road, Opp Hotel Sea Princess, Juhu, Mumbai 400049',
            'latitude': 19.1075,
            'longitude': 72.8263,
            'price_per_hour': 1500.0,
            'rating': 4.7,
            'facilities': ['Floodlights', 'Locker Room', 'Parking', 'Equipment Rental'],
            'rules': 'Box cricket ball provided. Clean shoes required.',
            'image_url': 'https://images.unsplash.com/photo-1574629810360-7efbbe195018?auto=format&fit=crop&w=600&q=80',
            'opening_time': '06:00',
            'closing_time': '23:00'
        },
        {
            'name': 'Manhattan Pitch Center',
            'owner_id': owner['id'],
            'sport': 'Soccer',
            'address': '550 W 34th St, New York, NY 10001',
            'latitude': 40.7549,
            'longitude': -74.0007,
            'price_per_hour': 80.0,
            'rating': 4.8,
            'facilities': ['Floodlights', 'Changing Room', 'Showers', 'Wifi'],
            'rules': 'No metal spikes allowed.',
            'image_url': 'https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=600&q=80',
            'opening_time': '07:00',
            'closing_time': '22:00'
        }
    ]

    for st in sample_turfs:
        if not mongo.db.turfs.find_one({'name': st['name']}):
            mongo.create_turf(**st)


def seed_sql_sample_data():
    organizer_email = 'sample.organizer@sports.local'
    organizer = User.query.filter_by(email=organizer_email).first()
    if not organizer:
        organizer = User(
            name='Sample Organizer',
            email=organizer_email,
            password=generate_password_hash('sample1234'),
            role='organizer',
            latitude=19.0760,
            longitude=72.8777,
        )
        db.session.add(organizer)
        db.session.flush()

    owner = User.query.filter_by(email='owner@turf.local').first()
    if not owner:
        owner = User(
            name='Rajesh Turf Owner',
            email='owner@turf.local',
            password=generate_password_hash('owner1234'),
            role='turf_owner',
            latitude=19.0760,
            longitude=72.8777,
        )
        db.session.add(owner)
        db.session.flush()

    tournaments = Tournament.query.all()
    for tournament in tournaments:
        if not tournament.organizer_id:
            tournament.organizer_id = organizer.id

    if not Turf.query.filter_by(name='Kickoff Turf Bandra West').first():
        db.session.add(Turf(
            name='Kickoff Turf Bandra West',
            owner_id=owner.id,
            sport='Football',
            address='Hill Road, Bandra West, Mumbai, Maharashtra 400050',
            latitude=19.0544,
            longitude=72.8402,
            price_per_hour=1200.0,
            rating=4.9,
            facilities='Floodlights, Changing Room, Parking, Drinking Water, Artificial Turf',
            rules='Studs not allowed. Soft turf shoes required.',
            image_url='https://images.unsplash.com/photo-1529900748604-07564a03e7a6?auto=format&fit=crop&w=600&q=80',
            opening_time='06:00',
            closing_time='23:00'
        ))

    db.session.commit()


with app.app_context():
    mongo.connect(timeout_ms=3000)
    if mongo.is_connected:
        print("Connected to MongoDB Atlas successfully.")
        seed_mongo_sample_data()
    else:
        print("MongoDB Atlas URI pending or unreachable. Initializing SQL fallback tables...")
        try:
            db.create_all()
            seed_sql_sample_data()
        except Exception as e:
            print(f"SQL table init warning: {e}")


def json_error(message, code=400):
    return jsonify({'error': message}), code


def user_to_public(user):
    if isinstance(user, dict):
        return {
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role'],
            'latitude': user.get('latitude'),
            'longitude': user.get('longitude'),
        }
    return {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role,
        'latitude': user.latitude,
        'longitude': user.longitude,
    }


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f'Invalid {field}')


@app.route('/health', methods=['GET'])
def health():
    db_type = 'mongodb_atlas' if mongo.is_connected else 'sql_fallback'
    return jsonify({'status': 'ok', 'database': db_type})


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}

    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    role = (data.get('role') or 'player').strip().lower()

    if not name or not email or not password:
        return json_error('name, email and password are required')

    if role not in ['player', 'organizer', 'turf_owner']:
        return json_error('role must be player, organizer or turf_owner')

    latitude = data.get('latitude')
    longitude = data.get('longitude')
    if latitude is not None:
        latitude = parse_float(latitude, 'latitude')
    if longitude is not None:
        longitude = parse_float(longitude, 'longitude')

    if mongo.is_connected:
        if mongo.get_user_by_email(email):
            return json_error('Email already registered', 409)
        mongo.create_user(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            latitude=latitude,
            longitude=longitude
        )
        return jsonify({'message': 'User created'}), 201
    else:
        if User.query.filter_by(email=email).first():
            return json_error('Email already registered', 409)

        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            role=role,
            latitude=latitude,
            longitude=longitude,
        )
        db.session.add(user)
        db.session.commit()
        return jsonify({'message': 'User created'}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if mongo.is_connected:
        user = mongo.get_user_by_email(email)
        if not user or not check_password_hash(user['password'], password):
            return json_error('Invalid credentials', 401)
        token = create_access_token(identity=str(user['id']))
        return jsonify({'access_token': token, 'user': user_to_public(user)})
    else:
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            return json_error('Invalid credentials', 401)
        token = create_access_token(identity=str(user.id))
        return jsonify({'access_token': token, 'user': user_to_public(user)})


@app.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    if mongo.is_connected:
        user = mongo.get_user_by_id(user_id)
        if not user:
            return json_error('User not found', 404)
        return jsonify(user_to_public(user))
    else:
        user = User.query.get(user_id)
        if not user:
            return json_error('User not found', 404)
        return jsonify(user_to_public(user))


# --- TURF FINDER & TURF OWNER API ENDPOINTS ---

@app.route('/turfs', methods=['GET'])
def get_turfs():
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    radius = request.args.get('radius', 50)
    sport = (request.args.get('sport') or '').strip()
    max_price = request.args.get('max_price')
    facility = (request.args.get('facility') or '').strip()

    try:
        radius = float(radius)
    except (TypeError, ValueError):
        radius = 50.0

    has_location = lat is not None and lng is not None
    if has_location:
        try:
            lat = float(lat)
            lng = float(lng)
        except ValueError:
            has_location = False

    results = []

    if mongo.is_connected:
        turfs = mongo.get_turfs(sport=sport, max_price=max_price, facility=facility)
        for t in turfs:
            distance = None
            if has_location:
                distance = haversine(lat, lng, t['latitude'], t['longitude'])
                if distance > radius:
                    continue
            results.append({
                'id': t['id'],
                'name': t['name'],
                'sport': t['sport'],
                'address': t['address'],
                'price_per_hour': t['price_per_hour'],
                'rating': t.get('rating', 4.5),
                'facilities': t.get('facilities', []),
                'rules': t.get('rules', ''),
                'image_url': t.get('image_url'),
                'latitude': t['latitude'],
                'longitude': t['longitude'],
                'distance': round(distance, 2) if distance is not None else None,
                'opening_time': t.get('opening_time', '06:00'),
                'closing_time': t.get('closing_time', '23:00')
            })
    else:
        query = Turf.query
        if sport:
            query = query.filter(Turf.sport.ilike(f'%{sport}%'))
        if max_price:
            try:
                query = query.filter(Turf.price_per_hour <= float(max_price))
            except ValueError:
                pass
        turfs = query.all()
        for t in turfs:
            distance = None
            if has_location:
                distance = haversine(lat, lng, t.latitude, t.longitude)
                if distance > radius:
                    continue
            facilities_list = [f.strip() for f in t.facilities.split(',')] if t.facilities else []
            results.append({
                'id': t.id,
                'name': t.name,
                'sport': t.sport,
                'address': t.address,
                'price_per_hour': t.price_per_hour,
                'rating': t.rating or 4.5,
                'facilities': facilities_list,
                'rules': t.rules or '',
                'image_url': t.image_url,
                'latitude': t.latitude,
                'longitude': t.longitude,
                'distance': round(distance, 2) if distance is not None else None,
                'opening_time': t.opening_time or '06:00',
                'closing_time': t.closing_time or '23:00'
            })

    return jsonify(results)


@app.route('/turfs/<int:turf_id>', methods=['GET'])
def get_turf_details(turf_id):
    if mongo.is_connected:
        t = mongo.get_turf_by_id(turf_id)
        if not t:
            return json_error('Turf not found', 404)
        owner = mongo.get_user_by_id(t['owner_id'])
        return jsonify({
            'id': t['id'],
            'name': t['name'],
            'sport': t['sport'],
            'address': t['address'],
            'price_per_hour': t['price_per_hour'],
            'rating': t.get('rating', 4.5),
            'facilities': t.get('facilities', []),
            'rules': t.get('rules', ''),
            'image_url': t.get('image_url'),
            'latitude': t['latitude'],
            'longitude': t['longitude'],
            'opening_time': t.get('opening_time', '06:00'),
            'closing_time': t.get('closing_time', '23:00'),
            'owner_name': owner['name'] if owner else 'Turf Owner',
            'owner_email': owner['email'] if owner else ''
        })
    else:
        t = Turf.query.get(turf_id)
        if not t:
            return json_error('Turf not found', 404)
        owner = User.query.get(t.owner_id) if t.owner_id else None
        facilities_list = [f.strip() for f in t.facilities.split(',')] if t.facilities else []
        return jsonify({
            'id': t.id,
            'name': t.name,
            'sport': t.sport,
            'address': t.address,
            'price_per_hour': t.price_per_hour,
            'rating': t.rating or 4.5,
            'facilities': facilities_list,
            'rules': t.rules or '',
            'image_url': t.image_url,
            'latitude': t.latitude,
            'longitude': t.longitude,
            'opening_time': t.opening_time or '06:00',
            'closing_time': t.closing_time or '23:00',
            'owner_name': owner.name if owner else 'Turf Owner',
            'owner_email': owner.email if owner else ''
        })


@app.route('/turfs/<int:turf_id>/slots', methods=['GET'])
def get_turf_slots(turf_id):
    booking_date = request.args.get('date') or datetime.utcnow().strftime('%Y-%m-%d')

    if mongo.is_connected:
        slots = mongo.get_turf_slots(turf_id, booking_date)
        return jsonify({'date': booking_date, 'slots': slots})
    else:
        t = Turf.query.get(turf_id)
        if not t:
            return json_error('Turf not found', 404)

        start_h = int((t.opening_time or '06:00').split(':')[0])
        end_h = int((t.closing_time or '23:00').split(':')[0])

        bookings = TurfBooking.query.filter(
            TurfBooking.turf_id == turf_id,
            TurfBooking.booking_date == booking_date,
            TurfBooking.status.in_(['confirmed', 'blocked_by_owner'])
        ).all()

        booked_map = {b.time_slot: b.status for b in bookings}

        slots = []
        for h in range(start_h, end_h):
            slot_str = f"{h:02d}:00 - {h+1:02d}:00"
            status = booked_map.get(slot_str, 'available')
            slots.append({
                'time_slot': slot_str,
                'status': status,
                'price': t.price_per_hour
            })
        return jsonify({'date': booking_date, 'slots': slots})


@app.route('/turfs/<int:turf_id>/book', methods=['POST'])
@jwt_required()
def book_turf_slot(turf_id):
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    booking_date = data.get('booking_date')
    time_slot = data.get('time_slot')

    if not booking_date or not time_slot:
        return json_error('booking_date and time_slot are required')

    if mongo.is_connected:
        turf = mongo.get_turf_by_id(turf_id)
        if not turf:
            return json_error('Turf not found', 404)
        try:
            booking = mongo.create_turf_booking(
                turf_id=turf_id,
                user_id=user_id,
                booking_date=booking_date,
                time_slot=time_slot,
                total_price=turf['price_per_hour'],
                status='confirmed'
            )
            return jsonify({'message': 'Turf slot booked successfully!', 'booking': booking}), 201
        except ValueError as err:
            return json_error(str(err), 409)
    else:
        turf = Turf.query.get(turf_id)
        if not turf:
            return json_error('Turf not found', 404)

        existing = TurfBooking.query.filter_by(
            turf_id=turf_id,
            booking_date=booking_date,
            time_slot=time_slot
        ).first()

        if existing and existing.status in ['confirmed', 'blocked_by_owner']:
            return json_error('Slot already booked for this time.', 409)

        booking = TurfBooking(
            turf_id=turf_id,
            user_id=user_id,
            booking_date=booking_date,
            time_slot=time_slot,
            total_price=turf.price_per_hour,
            status='confirmed'
        )
        try:
            db.session.add(booking)
            db.session.commit()
            return jsonify({'message': 'Turf slot booked successfully!', 'id': booking.id}), 201
        except IntegrityError:
            db.session.rollback()
            return json_error('Slot already booked for this time.', 409)


@app.route('/my-turf-bookings', methods=['GET'])
@jwt_required()
def my_turf_bookings():
    user_id = int(get_jwt_identity())

    if mongo.is_connected:
        return jsonify(mongo.get_user_turf_bookings(user_id))
    else:
        bookings = TurfBooking.query.filter_by(user_id=user_id).order_by(TurfBooking.created_at.desc()).all()
        results = []
        for b in bookings:
            t = Turf.query.get(b.turf_id)
            if t:
                results.append({
                    'id': b.id,
                    'turf_id': t.id,
                    'turf_name': t.name,
                    'sport': t.sport,
                    'address': t.address,
                    'booking_date': b.booking_date,
                    'time_slot': b.time_slot,
                    'total_price': b.total_price,
                    'status': b.status,
                    'created_at': b.created_at.isoformat()
                })
        return jsonify(results)


@app.route('/turf-bookings/<int:booking_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_turf_booking(booking_id):
    user_id = int(get_jwt_identity())

    if mongo.is_connected:
        success, msg = mongo.cancel_turf_booking(booking_id, user_id)
        if not success:
            return json_error(msg, 400)
        return jsonify({'message': msg})
    else:
        b = TurfBooking.query.get(booking_id)
        if not b:
            return json_error('Booking not found', 404)
        t = Turf.query.get(b.turf_id)
        if not (b.user_id == user_id or (t and t.owner_id == user_id)):
            return json_error('Unauthorized to cancel booking', 403)
        b.status = 'cancelled'
        db.session.commit()
        return jsonify({'message': 'Booking cancelled successfully'})


# --- TURF OWNER DASHBOARD ENDPOINTS ---

@app.route('/owner/turfs', methods=['GET'])
@jwt_required()
def get_owner_turfs():
    user_id = int(get_jwt_identity())

    if mongo.is_connected:
        return jsonify(mongo.get_owner_turfs(user_id))
    else:
        turfs = Turf.query.filter_by(owner_id=user_id).all()
        results = []
        for t in turfs:
            facilities_list = [f.strip() for f in t.facilities.split(',')] if t.facilities else []
            results.append({
                'id': t.id,
                'name': t.name,
                'sport': t.sport,
                'address': t.address,
                'price_per_hour': t.price_per_hour,
                'rating': t.rating or 4.5,
                'facilities': facilities_list,
                'rules': t.rules or '',
                'image_url': t.image_url,
                'latitude': t.latitude,
                'longitude': t.longitude,
                'opening_time': t.opening_time or '06:00',
                'closing_time': t.closing_time or '23:00'
            })
        return jsonify(results)


@app.route('/turfs', methods=['POST'])
@jwt_required()
def create_turf():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    name = (data.get('name') or '').strip()
    sport = (data.get('sport') or 'Football').strip()
    address = (data.get('address') or '').strip()

    if not name or not address:
        return json_error('Name and address are required')

    try:
        price_per_hour = float(data.get('price_per_hour', 1000))
        latitude = float(data.get('latitude', 19.0760))
        longitude = float(data.get('longitude', 72.8777))
    except ValueError:
        return json_error('Invalid numeric coordinates or price')

    facilities = data.get('facilities') or 'Floodlights, Changing Room, Parking'
    rules = data.get('rules') or 'Standard turf rules apply.'
    image_url = data.get('image_url') or 'https://images.unsplash.com/photo-1529900748604-07564a03e7a6?auto=format&fit=crop&w=600&q=80'
    opening_time = data.get('opening_time') or '06:00'
    closing_time = data.get('closing_time') or '23:00'

    if mongo.is_connected:
        user = mongo.get_user_by_id(user_id)
        if not user:
            return json_error('User not found', 404)
        turf_doc = mongo.create_turf(
            name=name,
            owner_id=user_id,
            sport=sport,
            address=address,
            latitude=latitude,
            longitude=longitude,
            price_per_hour=price_per_hour,
            rating=4.8,
            facilities=facilities,
            rules=rules,
            image_url=image_url,
            opening_time=opening_time,
            closing_time=closing_time
        )
        return jsonify({'message': 'Turf registered successfully!', 'turf': turf_doc}), 201
    else:
        user = User.query.get(user_id)
        if not user:
            return json_error('User not found', 404)
        turf = Turf(
            name=name,
            owner_id=user_id,
            sport=sport,
            address=address,
            latitude=latitude,
            longitude=longitude,
            price_per_hour=price_per_hour,
            rating=4.8,
            facilities=facilities if isinstance(facilities, str) else ', '.join(facilities),
            rules=rules,
            image_url=image_url,
            opening_time=opening_time,
            closing_time=closing_time
        )
        db.session.add(turf)
        db.session.commit()
        return jsonify({'message': 'Turf registered successfully!', 'id': turf.id}), 201


@app.route('/owner/bookings', methods=['GET'])
@jwt_required()
def get_owner_bookings():
    user_id = int(get_jwt_identity())

    if mongo.is_connected:
        bookings = mongo.get_owner_bookings(user_id)
        stats = mongo.get_owner_revenue_stats(user_id)
        return jsonify({'bookings': bookings, 'stats': stats})
    else:
        turfs = Turf.query.filter_by(owner_id=user_id).all()
        t_ids = [t.id for t in turfs]
        t_map = {t.id: t for t in turfs}

        bookings = TurfBooking.query.filter(TurfBooking.turf_id.in_(t_ids)).order_by(TurfBooking.created_at.desc()).all()
        b_list = []
        confirmed_count = 0
        total_revenue = 0.0

        for b in bookings:
            cust = User.query.get(b.user_id)
            t = t_map.get(b.turf_id)
            if b.status == 'confirmed':
                confirmed_count += 1
                total_revenue += b.total_price

            b_list.append({
                'id': b.id,
                'turf_id': b.turf_id,
                'turf_name': t.name if t else 'Turf',
                'customer_name': cust.name if cust else 'Player',
                'customer_email': cust.email if cust else '',
                'booking_date': b.booking_date,
                'time_slot': b.time_slot,
                'total_price': b.total_price,
                'status': b.status,
                'created_at': b.created_at.isoformat()
            })

        return jsonify({
            'bookings': b_list,
            'stats': {
                'total_revenue': total_revenue,
                'total_bookings': confirmed_count,
                'total_turfs': len(turfs)
            }
        })


@app.route('/owner/turfs/<int:turf_id>/block-slot', methods=['POST'])
@jwt_required()
def block_turf_slot(turf_id):
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    booking_date = data.get('booking_date')
    time_slot = data.get('time_slot')

    if not booking_date or not time_slot:
        return json_error('booking_date and time_slot are required')

    if mongo.is_connected:
        turf = mongo.get_turf_by_id(turf_id)
        if not turf or turf['owner_id'] != user_id:
            return json_error('Unauthorized', 403)
        try:
            booking = mongo.create_turf_booking(
                turf_id=turf_id,
                user_id=user_id,
                booking_date=booking_date,
                time_slot=time_slot,
                total_price=0.0,
                status='blocked_by_owner'
            )
            return jsonify({'message': 'Slot marked as blocked by owner', 'booking': booking})
        except ValueError as err:
            return json_error(str(err), 409)
    else:
        turf = Turf.query.get(turf_id)
        if not turf or turf.owner_id != user_id:
            return json_error('Unauthorized', 403)

        booking = TurfBooking(
            turf_id=turf_id,
            user_id=user_id,
            booking_date=booking_date,
            time_slot=time_slot,
            total_price=0.0,
            status='blocked_by_owner'
        )
        try:
            db.session.add(booking)
            db.session.commit()
            return jsonify({'message': 'Slot marked as blocked by owner'})
        except IntegrityError:
            db.session.rollback()
            return json_error('Slot already booked or blocked.', 409)


# --- TEAM FINDER API ENDPOINTS ---

@app.route('/teams', methods=['GET'])
def get_teams():
    sport = (request.args.get('sport') or '').strip().lower()

    if mongo.is_connected:
        return jsonify(mongo.get_teams(sport=sport))
    else:
        query = Team.query
        if sport:
            query = query.filter(Team.sport.ilike(f'%{sport}%'))
        teams = query.all()
        results = []
        for t in teams:
            creator = User.query.get(t.created_by) if t.created_by else None
            member_count = TeamRequest.query.filter_by(team_id=t.id, status='approved').count() + 1
            results.append({
                'id': t.id,
                'name': t.name,
                'sport': t.sport,
                'skill_level': t.skill_level or 'Intermediate',
                'created_by': t.created_by,
                'creator_name': creator.name if creator else 'Captain',
                'creator_email': creator.email if creator else '',
                'members_count': member_count,
                'latitude': t.latitude,
                'longitude': t.longitude
            })
        return jsonify(results)


@app.route('/teams', methods=['POST'])
@jwt_required()
def create_team():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    name = (data.get('name') or '').strip()
    sport = (data.get('sport') or '').strip()
    skill_level = (data.get('skill_level') or 'Intermediate').strip()

    if not name or not sport:
        return json_error('Team name and sport are required')

    latitude = data.get('latitude')
    longitude = data.get('longitude')
    if latitude is not None:
        latitude = float(latitude)
    if longitude is not None:
        longitude = float(longitude)

    if mongo.is_connected:
        user = mongo.get_user_by_id(user_id)
        if not user:
            return json_error('User not found', 404)
        team_doc = mongo.create_team(name, sport, skill_level, user_id, latitude, longitude)
        return jsonify({'message': 'Team created successfully', 'team': team_doc}), 201
    else:
        user = User.query.get(user_id)
        if not user:
            return json_error('User not found', 404)
        team = Team(name=name, sport=sport, skill_level=skill_level, created_by=user_id, latitude=latitude, longitude=longitude)
        db.session.add(team)
        db.session.commit()
        return jsonify({'message': 'Team created successfully', 'id': team.id}), 201


@app.route('/teams/<int:team_id>/join', methods=['POST'])
@jwt_required()
def join_team(team_id):
    user_id = int(get_jwt_identity())

    if mongo.is_connected:
        team = mongo.get_team_by_id(team_id)
        if not team:
            return json_error('Team not found', 404)
        if team['created_by'] == user_id:
            return json_error('You are already the captain of this team', 400)
        
        req_doc = mongo.create_team_request(team_id, user_id)
        return jsonify({'message': 'Join request sent to team captain', 'request_id': req_doc['id']}), 201
    else:
        team = Team.query.get(team_id)
        if not team:
            return json_error('Team not found', 404)
        if team.created_by == user_id:
            return json_error('You are already the captain of this team', 400)

        existing = TeamRequest.query.filter_by(team_id=team_id, user_id=user_id).first()
        if existing:
            return jsonify({'message': 'Request already exists', 'status': existing.status}), 200

        req = TeamRequest(team_id=team_id, user_id=user_id, status='pending')
        db.session.add(req)
        db.session.commit()
        return jsonify({'message': 'Join request sent to team captain', 'id': req.id}), 201


@app.route('/teams/<int:team_id>/requests', methods=['GET'])
@jwt_required()
def get_team_requests(team_id):
    user_id = int(get_jwt_identity())

    if mongo.is_connected:
        team = mongo.get_team_by_id(team_id)
        if not team:
            return json_error('Team not found', 404)
        if team['created_by'] != user_id:
            return json_error('Only team captain can view join requests', 403)
        return jsonify(mongo.get_team_requests(team_id))
    else:
        team = Team.query.get(team_id)
        if not team:
            return json_error('Team not found', 404)
        if team.created_by != user_id:
            return json_error('Only team captain can view join requests', 403)

        reqs = TeamRequest.query.filter_by(team_id=team_id).all()
        results = []
        for r in reqs:
            player = User.query.get(r.user_id)
            results.append({
                'id': r.id,
                'team_id': r.team_id,
                'user_id': r.user_id,
                'user_name': player.name if player else 'Player',
                'user_email': player.email if player else '',
                'status': r.status
            })
        return jsonify(results)


@app.route('/teams/requests/<int:request_id>/respond', methods=['POST'])
@jwt_required()
def respond_team_request(request_id):
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    new_status = (data.get('status') or '').strip().lower()

    if new_status not in ['approved', 'rejected']:
        return json_error('status must be approved or rejected')

    if mongo.is_connected:
        req = mongo.db.team_requests.find_one({'id': request_id})
        if not req:
            return json_error('Request not found', 404)
        team = mongo.get_team_by_id(req['team_id'])
        if not team or team['created_by'] != user_id:
            return json_error('Unauthorized to update request', 403)

        mongo.update_team_request_status(request_id, new_status)
        return jsonify({'message': f'Request {new_status}'})
    else:
        req = TeamRequest.query.get(request_id)
        if not req:
            return json_error('Request not found', 404)
        team = Team.query.get(req.team_id)
        if not team or team.created_by != user_id:
            return json_error('Unauthorized to update request', 403)

        req.status = new_status
        db.session.commit()
        return jsonify({'message': f'Request {new_status}'})


@app.route('/my-teams', methods=['GET'])
@jwt_required()
def my_teams():
    user_id = int(get_jwt_identity())

    if mongo.is_connected:
        created_teams = mongo.get_teams()
        my_created = [t for t in created_teams if t['created_by'] == user_id]
        my_requests = mongo.get_user_team_requests(user_id)
        return jsonify({
            'created_teams': my_created,
            'team_requests': my_requests
        })
    else:
        created_teams = Team.query.filter_by(created_by=user_id).all()
        my_created = [{
            'id': t.id,
            'name': t.name,
            'sport': t.sport,
            'skill_level': t.skill_level,
            'members_count': TeamRequest.query.filter_by(team_id=t.id, status='approved').count() + 1
        } for t in created_teams]

        reqs = TeamRequest.query.filter_by(user_id=user_id).all()
        my_requests = []
        for r in reqs:
            t = Team.query.get(r.team_id)
            if t:
                my_requests.append({
                    'request_id': r.id,
                    'team_id': t.id,
                    'team_name': t.name,
                    'sport': t.sport,
                    'status': r.status
                })

        return jsonify({
            'created_teams': my_created,
            'team_requests': my_requests
        })


# --- TOURNAMENT ENDPOINTS ---

@app.route('/init-data', methods=['POST'])
def init_data():
    samples = [
        {
            'name': 'Basketball Championship',
            'sport': 'Basketball',
            'date': '2026-03-20',
            'entry_fee': 50.0,
            'mode': 'team',
            'latitude': 40.7128,
            'longitude': -74.0060,
        },
        {
            'name': 'Soccer Open Cup',
            'sport': 'Soccer',
            'date': '2026-03-25',
            'entry_fee': 30.0,
            'mode': 'team',
            'latitude': 40.7580,
            'longitude': -73.9855,
        },
        {
            'name': 'Mumbai Football Cup',
            'sport': 'Football',
            'date': '2026-03-10',
            'entry_fee': 500.0,
            'mode': 'team',
            'latitude': 19.0760,
            'longitude': 72.8777,
        },
    ]

    created = 0
    if mongo.is_connected:
        for sample in samples:
            existing = mongo.db.tournaments.find_one({'name': sample['name'], 'date': sample['date']})
            if not existing:
                mongo.create_tournament(
                    name=sample['name'],
                    sport=sample['sport'],
                    date_str=sample['date'],
                    entry_fee=sample['entry_fee'],
                    mode=sample['mode'],
                    latitude=sample['latitude'],
                    longitude=sample['longitude']
                )
                created += 1
    else:
        for sample in samples:
            dt = datetime.strptime(sample['date'], '%Y-%m-%d').date()
            if Tournament.query.filter_by(name=sample['name'], date=dt).first():
                continue
            db.session.add(Tournament(
                name=sample['name'],
                sport=sample['sport'],
                date=dt,
                entry_fee=sample['entry_fee'],
                mode=sample['mode'],
                latitude=sample['latitude'],
                longitude=sample['longitude']
            ))
            created += 1
        db.session.commit()

    return jsonify({'message': 'Sample data processed', 'created': created}), 201


@app.route('/tournaments', methods=['GET'])
def get_tournaments():
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    radius = request.args.get('radius', 50)
    sport = (request.args.get('sport') or '').strip().lower()

    try:
        radius = float(radius)
    except (TypeError, ValueError):
        return json_error('Invalid radius')

    if radius <= 0:
        return json_error('radius must be greater than 0')

    has_location = lat is not None and lng is not None
    if has_location:
        try:
            lat = float(lat)
            lng = float(lng)
        except ValueError:
            return json_error('Invalid lat/lng')

    results = []

    if mongo.is_connected:
        tournaments = mongo.get_tournaments(sport=sport)
        for t in tournaments:
            distance = None
            if has_location:
                distance = haversine(lat, lng, t['latitude'], t['longitude'])
                if distance > radius:
                    continue
            results.append({
                'id': t['id'],
                'name': t['name'],
                'sport': t['sport'],
                'distance': round(distance, 2) if distance is not None else None,
                'date': t['date'],
                'entry_fee': float(t['entry_fee']),
                'mode': t['mode'],
                'latitude': t['latitude'],
                'longitude': t['longitude'],
            })
    else:
        tournaments = Tournament.query.order_by(Tournament.date.asc()).all()
        for tournament in tournaments:
            if sport and tournament.sport.lower() != sport:
                continue

            distance = None
            if has_location:
                distance = haversine(lat, lng, tournament.latitude, tournament.longitude)
                if distance > radius:
                    continue

            results.append(
                {
                    'id': tournament.id,
                    'name': tournament.name,
                    'sport': tournament.sport,
                    'distance': round(distance, 2) if distance is not None else None,
                    'date': tournament.date.isoformat(),
                    'entry_fee': float(tournament.entry_fee),
                    'mode': tournament.mode,
                    'latitude': tournament.latitude,
                    'longitude': tournament.longitude,
                }
            )

    return jsonify(results)


@app.route('/tournaments', methods=['POST'])
@jwt_required()
def create_tournament():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    if mongo.is_connected:
        organizer = mongo.get_user_by_id(user_id)
        if not organizer:
            return json_error('User not found', 404)
        if organizer['role'] != 'organizer':
            return json_error('Only organizer can create tournaments', 403)

        try:
            name = (data.get('name') or '').strip()
            sport = (data.get('sport') or '').strip()
            date_str = data.get('date', '')
            entry_fee = float(data.get('entry_fee', 0))
            mode = (data.get('mode') or '').strip().lower()
            latitude = float(data.get('latitude'))
            longitude = float(data.get('longitude'))
        except ValueError:
            return json_error('Invalid tournament payload')

        if not name or not sport:
            return json_error('name and sport are required')
        if mode not in ['individual', 'team']:
            return json_error('mode must be individual or team')

        t_doc = mongo.create_tournament(
            name=name,
            sport=sport,
            date_str=date_str,
            entry_fee=entry_fee,
            mode=mode,
            latitude=latitude,
            longitude=longitude,
            organizer_id=organizer['id'],
            venue_name=(data.get('venue_name') or '').strip() or None,
            venue_address=(data.get('venue_address') or '').strip() or None,
            organizer_phone=(data.get('organizer_phone') or '').strip() or None,
            organizer_verified=bool(data.get('organizer_verified', False))
        )
        return jsonify({'message': 'Tournament created', 'id': t_doc['id']}), 201

    else:
        organizer = User.query.get(user_id)
        if not organizer:
            return json_error('User not found', 404)
        if organizer.role != 'organizer':
            return json_error('Only organizer can create tournaments', 403)

        try:
            tournament = Tournament(
                name=(data.get('name') or '').strip(),
                sport=(data.get('sport') or '').strip(),
                date=datetime.strptime(data.get('date', ''), '%Y-%m-%d').date(),
                entry_fee=float(data.get('entry_fee', 0)),
                mode=(data.get('mode') or '').strip().lower(),
                latitude=float(data.get('latitude')),
                longitude=float(data.get('longitude')),
                organizer_id=organizer.id,
                venue_name=(data.get('venue_name') or '').strip() or None,
                venue_address=(data.get('venue_address') or '').strip() or None,
                organizer_phone=(data.get('organizer_phone') or '').strip() or None,
                organizer_verified=bool(data.get('organizer_verified', False)),
            )
        except ValueError:
            return json_error('Invalid tournament payload')

        if not tournament.name or not tournament.sport:
            return json_error('name and sport are required')
        if tournament.mode not in ['individual', 'team']:
            return json_error('mode must be individual or team')

        db.session.add(tournament)
        db.session.commit()
        return jsonify({'message': 'Tournament created', 'id': tournament.id}), 201


@app.route('/tournament/<int:tournament_id>', methods=['GET'])
def get_tournament_details(tournament_id):
    if mongo.is_connected:
        t = mongo.get_tournament_by_id(tournament_id)
        if not t:
            return json_error('Tournament not found', 404)
        organizer = mongo.get_user_by_id(t['organizer_id']) if t.get('organizer_id') else None
        return jsonify({
            'id': t['id'],
            'name': t['name'],
            'sport': t['sport'],
            'date': t['date'],
            'entry_fee': float(t['entry_fee']),
            'mode': t['mode'],
            'latitude': t['latitude'],
            'longitude': t['longitude'],
            'venue_name': t.get('venue_name') or t['name'],
            'venue_address': t.get('venue_address') or 'Address not provided',
            'organizer': {
                'id': organizer['id'] if organizer else None,
                'name': organizer['name'] if organizer else 'Unknown organizer',
                'email': organizer['email'] if organizer else None,
            },
        })
    else:
        tournament = Tournament.query.get(tournament_id)
        if not tournament:
            return json_error('Tournament not found', 404)
        organizer = User.query.get(tournament.organizer_id) if tournament.organizer_id else None
        return jsonify({
            'id': tournament.id,
            'name': tournament.name,
            'sport': tournament.sport,
            'date': tournament.date.isoformat(),
            'entry_fee': float(tournament.entry_fee),
            'mode': tournament.mode,
            'latitude': tournament.latitude,
            'longitude': tournament.longitude,
            'venue_name': tournament.venue_name or tournament.name,
            'venue_address': tournament.venue_address or 'Address not provided',
            'organizer': {
                'id': organizer.id if organizer else None,
                'name': organizer.name if organizer else 'Unknown organizer',
                'email': organizer.email if organizer else None,
            },
        })


@app.route('/tournament/<int:tournament_id>/organizer-contact', methods=['GET'])
@jwt_required()
def get_organizer_contact(tournament_id):
    if mongo.is_connected:
        t = mongo.get_tournament_by_id(tournament_id)
        if not t:
            return json_error('Tournament not found', 404)
        organizer = mongo.get_user_by_id(t['organizer_id']) if t.get('organizer_id') else None
        return jsonify({
            'organizer_name': organizer['name'] if organizer else 'Unknown organizer',
            'phone': t.get('organizer_phone') or 'Not provided',
            'email': organizer['email'] if organizer else 'Not available',
            'verified': bool(t.get('organizer_verified', False)),
        })
    else:
        tournament = Tournament.query.get(tournament_id)
        if not tournament:
            return json_error('Tournament not found', 404)

        organizer = User.query.get(tournament.organizer_id) if tournament.organizer_id else None
        return jsonify({
            'organizer_name': organizer.name if organizer else 'Unknown organizer',
            'phone': tournament.organizer_phone or 'Not provided',
            'email': organizer.email if organizer else 'Not available',
            'verified': bool(tournament.organizer_verified),
        })


@app.route('/tournament/<int:tournament_id>/comments', methods=['GET'])
def get_tournament_comments(tournament_id):
    if mongo.is_connected:
        comments = mongo.get_tournament_comments(tournament_id)
        return jsonify(comments)
    else:
        tournament = Tournament.query.get(tournament_id)
        if not tournament:
            return json_error('Tournament not found', 404)

        comment_rows = (
            db.session.query(Comment, User)
            .join(User, User.id == Comment.user_id)
            .filter(Comment.tournament_id == tournament_id)
            .order_by(Comment.created_at.desc())
            .all()
        )

        return jsonify([
            {
                'id': comment.id,
                'tournament_id': comment.tournament_id,
                'user_id': user.id,
                'user_name': user.name,
                'comment_text': comment.comment_text,
                'created_at': comment.created_at.isoformat(),
            }
            for comment, user in comment_rows
        ])


@app.route('/tournament/<int:tournament_id>/comments', methods=['POST'])
@jwt_required()
def post_tournament_comment(tournament_id):
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    comment_text = (data.get('comment_text') or '').strip()
    if not comment_text:
        return json_error('comment_text is required')

    if mongo.is_connected:
        user = mongo.get_user_by_id(user_id)
        if not user:
            return json_error('User not found', 404)
        t = mongo.get_tournament_by_id(tournament_id)
        if not t:
            return json_error('Tournament not found', 404)

        new_c = mongo.add_comment(tournament_id, user_id, comment_text)
        return jsonify({'message': 'Comment added', 'comment_id': new_c['id']}), 201
    else:
        user = User.query.get(user_id)
        if not user:
            return json_error('User not found', 404)
        tournament = Tournament.query.get(tournament_id)
        if not tournament:
            return json_error('Tournament not found', 404)

        new_comment = Comment(
            tournament_id=tournament_id,
            user_id=user_id,
            comment_text=comment_text,
        )

        db.session.add(new_comment)
        db.session.commit()
        return jsonify({'message': 'Comment added', 'comment_id': new_comment.id}), 201


@app.route('/tournaments/<int:tournament_id>/register', methods=['POST'])
@jwt_required()
def register_tournament(tournament_id):
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    team_id = data.get('team_id')

    if mongo.is_connected:
        if not mongo.get_user_by_id(user_id):
            return json_error('User not found', 404)
        if not mongo.get_tournament_by_id(tournament_id):
            return json_error('Tournament not found', 404)
        if mongo.get_registration(user_id, tournament_id):
            return json_error('Already registered for this tournament', 409)

        mongo.create_registration(user_id, tournament_id, team_id=team_id)
        return jsonify({'message': 'Registration successful'}), 201
    else:
        if not User.query.get(user_id):
            return json_error('User not found', 404)
        if not Tournament.query.get(tournament_id):
            return json_error('Tournament not found', 404)
        if Registration.query.filter_by(user_id=user_id, tournament_id=tournament_id).first():
            return json_error('Already registered for this tournament', 409)

        registration = Registration(
            user_id=user_id,
            tournament_id=tournament_id,
            team_id=team_id,
        )
        db.session.add(registration)
        db.session.commit()
        return jsonify({'message': 'Registration successful'}), 201


@app.route('/organizer/registrations', methods=['GET'])
@jwt_required()
def organizer_registrations():
    user_id = int(get_jwt_identity())

    if mongo.is_connected:
        organizer = mongo.get_user_by_id(user_id)
        if not organizer:
            return json_error('User not found', 404)
        if organizer['role'] != 'organizer':
            return json_error('Only organizer can view this data', 403)

        return jsonify(mongo.get_organizer_registrations(user_id))
    else:
        organizer = User.query.get(user_id)
        if not organizer:
            return json_error('User not found', 404)
        if organizer.role != 'organizer':
            return json_error('Only organizer can view this data', 403)

        entries = (
            db.session.query(Registration, Tournament, User)
            .join(Tournament, Tournament.id == Registration.tournament_id)
            .join(User, User.id == Registration.user_id)
            .filter(Tournament.organizer_id == user_id)
            .order_by(Tournament.date.asc(), Registration.id.asc())
            .all()
        )

        grouped = {}
        for registration, tournament, player in entries:
            if tournament.id not in grouped:
                grouped[tournament.id] = {
                    'tournament_id': tournament.id,
                    'name': tournament.name,
                    'sport': tournament.sport,
                    'mode': tournament.mode,
                    'date': tournament.date.isoformat(),
                    'registrations': [],
                }

            grouped[tournament.id]['registrations'].append(
                {
                    'registration_id': registration.id,
                    'user_id': player.id,
                    'user_name': player.name,
                    'user_email': player.email,
                    'team_id': registration.team_id,
                }
            )

        return jsonify(list(grouped.values()))


@app.route('/my-registrations', methods=['GET'])
@jwt_required()
def my_registrations():
    user_id = int(get_jwt_identity())

    if mongo.is_connected:
        return jsonify(mongo.get_user_registrations(user_id))
    else:
        entries = (
            db.session.query(Registration, Tournament)
            .join(Tournament, Tournament.id == Registration.tournament_id)
            .filter(Registration.user_id == user_id)
            .order_by(Tournament.date.asc())
            .all()
        )

        results = []
        for registration, tournament in entries:
            results.append(
                {
                    'registration_id': registration.id,
                    'tournament_id': tournament.id,
                    'name': tournament.name,
                    'sport': tournament.sport,
                    'date': tournament.date.isoformat(),
                    'entry_fee': float(tournament.entry_fee),
                    'mode': tournament.mode,
                }
            )

        return jsonify(results)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
