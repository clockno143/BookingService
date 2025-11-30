import uuid
from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import AvailableSeats, Booking
from aio_pika import connect_robust, Message
import json
from .config import RABBITMQ_URL

async def reserve_seat(event_id: str, user_id: str, email:str,eventName:str ,session: AsyncSession):
    reservation_id = str(uuid.uuid4())

    # Optimistic locking
    stmt = (
        update(AvailableSeats)
        .where(AvailableSeats.event_id == event_id, AvailableSeats.remaining_seats > 0)
        .values(
            remaining_seats=AvailableSeats.remaining_seats - 1,
            version=AvailableSeats.version + 1
        )
        .returning(AvailableSeats.remaining_seats)
    )

    result = await session.execute(stmt)
    updated_row = result.scalar()

    if updated_row is None:
        return {"status": "WAITLISTED", "message": "Event is full. You are added to waitlist.", "reservation_id": None}

    # # Insert temporary booking
    # temp_booking = Booking(
    #     booking_id=reservation_id,
    #     event_id=event_id,
    #     user_id=user_id,
    #     status="waiting"
    # )
    # session.add(temp_booking)
    # await session.commit()

    # Push to RabbitMQ asynchronously
    await push_to_queue({
        "reservation_id": reservation_id,
        "event_id": str(event_id),
        "user_id": str(user_id),
        "user_email":email,
        "Event_Name": eventName

    })

    return {"status": "RESERVED", "message": "Seat reserved. Your booking is being processed.", "reservation_id": reservation_id}


async def push_to_queue(payload: dict):
    connection = await connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    queue = await channel.declare_queue("booking_queue", durable=True)
    message = Message(json.dumps(payload).encode())
    await channel.default_exchange.publish(message, routing_key=queue.name)
    await connection.close()


async def get_booking_status(reservation_id: str, session: AsyncSession):
    stmt = select(Booking).where(Booking.booking_id == reservation_id)
    result = await session.execute(stmt)
    booking = result.scalar()
    if booking:
        return {"status": booking.status, "message": f"Booking {booking.status}"}
    return {"status": "NOT_FOUND", "message": "Reservation ID not found"}

async def cancel_booking(booking_id: str, session: AsyncSession):
    """
    Cancel a booking.
    1. Update booking status to 'cancelled'.
    2. Increment available seats.
    3. Promote earliest waiting booking if exists.
    """
    # 1. Fetch booking
    stmt = select(Booking).where(Booking.booking_id == booking_id)
    booking = (await session.execute(stmt)).scalar_one_or_none()

    if not booking:
        return {"status": "NOT_FOUND", "message": "Booking not found"}

    if booking.status == "cancelled":
        return {"status": "ALREADY_CANCELLED", "message": "Booking is already cancelled"}

    # 2. Update booking status to cancelled
    booking.status = "cancelled"
    await session.commit()
    
async def promote_waiting_booking(event_id: str, session: AsyncSession):
    """
    Promote the earliest waiting booking (if any) for a given event.
    Pushes it to RabbitMQ queue for worker to confirm.
    """
    stmt_waiting = (
        select(Booking)
        .where(
            Booking.event_id == event_id,
            Booking.status == "waiting"
        )
        .order_by(Booking.booking_time.asc())
    )
    waiting_booking = (await session.execute(stmt_waiting)).scalar_one_or_none()

    if waiting_booking:
        # Push waiting booking to worker queue
        await push_to_queue({
            "reservation_id": str(waiting_booking.booking_id),
            "event_id": str(waiting_booking.event_id),
            "user_id": str(waiting_booking.user_id),
            "user_email": waiting_booking.user_email,
            "event_name": waiting_booking.event_name
        })
        return waiting_booking.booking_id

    return None
