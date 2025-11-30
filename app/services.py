import uuid
from sqlalchemy import update, select,func,insert
from sqlalchemy.ext.asyncio import AsyncSession
from .models import AvailableSeats, Booking
from aio_pika import connect_robust, Message
import json
from .config import RABBITMQ_URL
from fastapi import HTTPException
from typing import List
from .schemas import BookingBatchResponse,UserBookingResponse,AvailableSeatsResponse,AvailableSeatsRequest,AvailableSeatsGetResponse
import asyncio
async def reserve_seat(event_id: str, user_id: str, email: str, eventName: str, session: AsyncSession):
    reservation_id = str(uuid.uuid4())

    # Atomic decrement: only one request can decrement last seat
    stmt = (
        update(AvailableSeats)
        .where(
            AvailableSeats.event_id == event_id,
            AvailableSeats.remaining_seats > 0
        )
        .values(
            remaining_seats=AvailableSeats.remaining_seats - 1,
            version=AvailableSeats.version + 1
        )
        .returning(AvailableSeats.remaining_seats)
    )

    result = await session.execute(stmt)
    updated_row = result.scalar()
    await session.commit()  # commit the decrement

    if updated_row is None:
        # No seats left → waitlist
        db_status = "waiting"
        message = "Event is full. You are added to waitlist."
        reservation_id_to_return = None
    else:
        # Seat successfully reserved
        db_status = "confirmed"  # must match CHECK constraint in DB
        message = "Seat reserved. Your booking is being processed."
        reservation_id_to_return = reservation_id

    # Push status to RabbitMQ queue
    await push_to_queue({
        "reservation_id": reservation_id,
        "event_id": str(event_id),
        "user_id": str(user_id),
        "user_email": email,
        "Event_Name": eventName,
        "status": db_status
    })

    # Return API-friendly status
    return {
        "status": "RESERVED" if db_status == "confirmed" else "WAITLISTED",
        "message": message,
        "reservation_id": reservation_id_to_return
    }
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

    if booking.status == "canceled":
        return {"status": "ALREADY_CANCELLED", "message": "Booking is already cancelled"}

    # 2. Update booking status to cancelled
    booking.status = "canceled"
    await session.commit()
    return {"status":"CANCELLED_SUCCESSFULLY","message": "Booking  cancelled successfully","event_id": booking.event_id}
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
        .limit(1)  # <-- only fetch the earliest waiting booking
    )
    result = await session.execute(stmt_waiting)
    waiting_booking = result.scalar_one_or_none()  # now safe

    if waiting_booking:
        # Push waiting booking to worker queue
        print({
            "reservation_id": str(waiting_booking.booking_id),
            "event_id": str(waiting_booking.event_id),
            "user_id": str(waiting_booking.user_id),
            "user_email": waiting_booking.user_email,
            "Event_Name": waiting_booking.event_name,
            "status":"confirmed"
        })
   
        await push_to_queue({
            "reservation_id": str(waiting_booking.booking_id),
            "event_id": str(waiting_booking.event_id),
            "user_id": str(waiting_booking.user_id),
            "user_email": waiting_booking.user_email,
            "Event_Name": waiting_booking.event_name,
            "status":"confirmed"
        })
        return waiting_booking.booking_id

    return None
async def get_total_bookings(event_id: str, session: AsyncSession):
    """
    Returns total number of bookings for a given event_id
    """
    event_id = event_id.strip()
    stmt = select(func.count()).select_from(Booking).where(Booking.event_id == event_id)
    result = await session.execute(stmt)
    total = result.scalar()
    return {"event_id": event_id, "total_bookings": total}

async def get_booking_batch(event_id: str, offset: int = 0, batch_size: int = 5, session: AsyncSession = None) -> List[BookingBatchResponse]:
    """
    Returns a batch of bookings for a given event_id
    Pagination is done via offset and batch_size
    """
    stmt = (
        select(Booking)
        .where(Booking.event_id == event_id)
        .order_by(Booking.booking_time)
        .offset(offset * batch_size)
        .limit(batch_size)
    )

    result = await session.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        raise HTTPException(status_code=404, detail="No bookings found for this event in the given batch")

    # Convert rows to Pydantic schema
    bookings = [BookingBatchResponse(
        booking_id=str(row.booking_id),
        event_id=str(row.event_id),
        user_id=str(row.user_id),
        booking_time=row.booking_time,
        status=row.status,
        event_name=row.event_name,
        user_email=row.user_email
    ) for row in rows]

    return bookings

async def get_user_bookings(user_id: str, session: AsyncSession) -> List[UserBookingResponse]:
    """
    Fetch all bookings for a given user_id including RESERVED, WAITING, and CANCELLED
    """
    stmt = select(Booking).where(Booking.user_id == user_id).order_by(Booking.booking_time.desc())
    result = await session.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        raise HTTPException(status_code=404, detail="No bookings found for this user")

    bookings = [
        UserBookingResponse(
            booking_id=str(row.booking_id),
            event_id=str(row.event_id),
            event_name=row.event_name,
            booking_time=row.booking_time,
            status=row.status,
            user_email=row.user_email
        )
        for row in rows
    ]
    return bookings

async def create_available_seats(req: AvailableSeatsRequest, session: AsyncSession) -> AvailableSeatsResponse:
    """
    Create a new entry in available_seats table for an event.
    """
    # Check if event already exists
    stmt = select(AvailableSeats).where(AvailableSeats.event_id == req.event_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="AvailableSeats entry for this event already exists")

    # Insert new record
    stmt_insert = insert(AvailableSeats).values(
        event_id=req.event_id,
        remaining_seats=req.remaining_seats
    ).returning(AvailableSeats.event_id, AvailableSeats.remaining_seats, AvailableSeats.version)

    result = await session.execute(stmt_insert)
    await session.commit()
    row = result.fetchone()

    return AvailableSeatsResponse(
        event_id=str(row.event_id),
        remaining_seats=row.remaining_seats,
        version=row.version
    )


async def get_available_seats(event_id: str, session: AsyncSession) -> AvailableSeatsGetResponse:
    """
    Fetch the available seats for a given event_id
    """
    event_id = event_id.strip()  # remove extra spaces/newlines

    stmt = select(AvailableSeats).where(AvailableSeats.event_id == event_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Event not found in available_seats")

    return AvailableSeatsGetResponse(
        event_id=str(row.event_id),
        remaining_seats=row.remaining_seats,
        version=row.version
    )