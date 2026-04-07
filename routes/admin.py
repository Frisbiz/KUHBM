from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Room, Booking, User, ServiceRequest
from datetime import date

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Access denied.', 'danger')
            return redirect(url_for('auth.index'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_rooms = Room.query.count()
    occupied = Room.query.filter_by(status='occupied').count()
    available = Room.query.filter_by(status='available').count()
    total_guests = User.query.filter_by(role='guest').count()
    pending_requests = ServiceRequest.query.filter_by(status='pending').count()
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html',
                           total_rooms=total_rooms, occupied=occupied,
                           available=available, total_guests=total_guests,
                           pending_requests=pending_requests,
                           recent_bookings=recent_bookings)


@admin_bp.route('/rooms')
@login_required
@admin_required
def rooms():
    all_rooms = Room.query.order_by(Room.number).all()
    return render_template('admin/rooms.html', rooms=all_rooms)


@admin_bp.route('/rooms/add', methods=['POST'])
@login_required
@admin_required
def add_room():
    number = request.form.get('number')
    room_type = request.form.get('type')
    price = request.form.get('price')
    description = request.form.get('description')
    if Room.query.filter_by(number=number).first():
        flash(f'Room {number} already exists.', 'danger')
    else:
        room = Room(number=number, type=room_type, base_price=float(price), description=description)
        db.session.add(room)
        db.session.commit()
        flash(f'Room {number} added.', 'success')
    return redirect(url_for('admin.rooms'))


@admin_bp.route('/rooms/<int:room_id>/status', methods=['POST'])
@login_required
@admin_required
def update_room_status(room_id):
    room = Room.query.get_or_404(room_id)
    room.status = request.form.get('status')
    db.session.commit()
    flash(f'Room {room.number} status updated.', 'success')
    return redirect(url_for('admin.rooms'))


@admin_bp.route('/pricing')
@login_required
@admin_required
def pricing():
    rooms = Room.query.all()
    today = date.today()
    total_rooms = len(rooms)

    booked_count = Booking.query.filter(
        Booking.status.in_(['confirmed', 'checked_in']),
        Booking.check_in <= today,
        Booking.check_out > today
    ).count()

    occupancy_rate = booked_count / total_rooms if total_rooms > 0 else 0

    pricing_suggestions = []
    for room in rooms:
        suggested = calculate_suggested_price(room.base_price, occupancy_rate)
        pricing_suggestions.append({
            'room': room,
            'suggested_price': suggested,
            'change': round(((suggested - room.base_price) / room.base_price) * 100, 1)
        })

    return render_template('admin/pricing.html',
                           pricing=pricing_suggestions,
                           occupancy_rate=round(occupancy_rate * 100, 1))


def calculate_suggested_price(base_price, occupancy_rate):
    multiplier = 1.0
    if occupancy_rate > 0.8:
        multiplier = 1.30
    elif occupancy_rate > 0.6:
        multiplier = 1.15
    elif occupancy_rate < 0.3:
        multiplier = 0.85
    return round(base_price * multiplier, 2)
