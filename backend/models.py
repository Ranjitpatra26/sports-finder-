from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='player')  # player, organizer, turf_owner
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)


class Tournament(db.Model):
    __tablename__ = 'tournaments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    sport = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    entry_fee = db.Column(db.Float, nullable=False, default=0)
    mode = db.Column(db.String(20), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    organizer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    venue_name = db.Column(db.String(255))
    venue_address = db.Column(db.Text)
    organizer_phone = db.Column(db.String(32))
    youtube_link = db.Column(db.String(500))
    organizer_verified = db.Column(db.Boolean, nullable=False, default=False)


class Team(db.Model):
    __tablename__ = 'teams'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sport = db.Column(db.String(100), nullable=False)
    skill_level = db.Column(db.String(50))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))


class TeamRequest(db.Model):
    __tablename__ = 'team_requests'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')


class Registration(db.Model):
    __tablename__ = 'registrations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'tournament_id', name='uq_user_tournament'),
    )


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    comment_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


# --- EXCLUSIVE FEATURE: TURF FINDER & TURF OWNER DASHBOARD ---
class Turf(db.Model):
    __tablename__ = 'turfs'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sport = db.Column(db.String(100), nullable=False, default='Football')
    address = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    price_per_hour = db.Column(db.Float, nullable=False)
    rating = db.Column(db.Float, default=4.5)
    facilities = db.Column(db.Text)
    rules = db.Column(db.Text)
    image_url = db.Column(db.Text)
    opening_time = db.Column(db.String(10), default='06:00')
    closing_time = db.Column(db.String(10), default='23:00')


class TurfBooking(db.Model):
    __tablename__ = 'turf_bookings'

    id = db.Column(db.Integer, primary_key=True)
    turf_id = db.Column(db.Integer, db.ForeignKey('turfs.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    booking_date = db.Column(db.String(20), nullable=False)
    time_slot = db.Column(db.String(30), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='confirmed')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('turf_id', 'booking_date', 'time_slot', name='uq_turf_slot_booking'),
    )
