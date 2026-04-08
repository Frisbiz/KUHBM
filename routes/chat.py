from flask import Blueprint, render_template, request, jsonify, session, abort
from flask_login import login_required, current_user
from models import Room, Booking, ServiceRequest
from config import Config
from openai import OpenAI

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')


@chat_bp.route('/')
@login_required
def index():
    if current_user.role != 'guest':
        abort(403)
    return render_template('guest/chat.html')


@chat_bp.route('/send', methods=['POST'])
@login_required
def send():
    if current_user.role != 'guest':
        abort(403)
    if not Config.OPENAI_API_KEY:
        return jsonify({'response': 'AI assistant is not configured. Please add an API key.'})

    user_message = request.json.get('message', '')
    if not user_message.strip():
        return jsonify({'response': 'Please enter a message.'})

    if len(user_message) > 500:
        return jsonify({'response': 'Message too long. Please keep messages under 500 characters.'})

    # Build context about available rooms
    available_rooms = Room.query.filter_by(status='available').all()
    room_info = '\n'.join([
        f"- Room {r.number} ({r.type}): ${r.base_price}/night. {r.description or ''}"
        for r in available_rooms
    ])

    # Guest's active bookings
    active_bookings = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.status.in_(['confirmed', 'checked_in'])
    ).all()
    booking_info = '\n'.join([
        f"- Room {b.room.number} ({b.room.type}): check-in {b.check_in}, check-out {b.check_out}, status: {b.status}, total: ${b.total_price}"
        for b in active_bookings
    ]) or 'No active bookings.'

    # Guest's open service requests
    open_requests = ServiceRequest.query.filter(
        ServiceRequest.user_id == current_user.id,
        ServiceRequest.status.in_(['pending', 'in_progress'])
    ).all()
    request_info = '\n'.join([
        f"- {r.type} request: '{r.description}', status: {r.status}"
        for r in open_requests
    ]) or 'No open service requests.'

    system_prompt = f"""You are a friendly hotel assistant for GuestFlow.
You are speaking with {current_user.name}.
Help them with room inquiries, booking information, service requests, and general hotel questions.

Currently available rooms:
{room_info if room_info else 'No rooms currently available.'}

{current_user.name}'s active bookings:
{booking_info}

{current_user.name}'s open service requests:
{request_info}

Keep responses concise and helpful. If the guest wants to make a new booking, direct them to the Booking page.
If they want to submit a new service request, direct them to the Services page.
You can answer questions about their existing bookings and requests using the information above."""

    try:
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            max_tokens=512,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_message}
            ]
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = 'Sorry, I encountered an error. Please try again later.'

    return jsonify({'response': reply})
