from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .schemas import BookEventRequest, BookEventResponse, BookingStatusResponse,BookingBatchResponse
from .database import get_session
from .services import reserve_seat, get_booking_status,cancel_booking,promote_waiting_booking,get_booking_batch,get_total_bookings,get_user_bookings,create_available_seats,get_available_seats
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from typing import List
from .database import async_session_maker
from .schemas import UserBookingResponse,AvailableSeatsRequest, AvailableSeatsResponse,AvailableSeatsGetResponse

router = APIRouter()

@router.post("/book", response_model=BookEventResponse)
async def book_event(req: BookEventRequest, session: AsyncSession = Depends(get_session)):
    return await reserve_seat(req.event_id,req.user_id,req.user_email,req.event_Name, session)

@router.get("/booking-status/{reservation_id}", response_model=BookingStatusResponse)
async def booking_status(reservation_id: str, session: AsyncSession = Depends(get_session)):
    return await get_booking_status(reservation_id, session)

@router.post("/booking/cancel/{booking_id}")
async def cancel_booking_route(booking_id: str):
    async with async_session_maker() as session:
        # 1️⃣ Cancel the booking synchronously
        cancel_result = await cancel_booking(booking_id, session)

    # 2️⃣ Promote a waiting booking asynchronously in a separate session
    if cancel_result["status"] == "CANCELLED_SUCCESSFULLY":
        import asyncio
        asyncio.create_task(promote_waiting_booking_background(cancel_result["event_id"]))

    return cancel_result

async def promote_waiting_booking_background(event_id: str):
    async with async_session_maker() as session:
        await promote_waiting_booking(event_id, session)
    
@router.get("/bookings/count")
async def bookings_count(event_id: str, session: AsyncSession = Depends(get_session)):
    return await get_total_bookings(event_id, session)

@router.get("/bookings/batch", response_model=List[BookingBatchResponse])
async def bookings_batch(event_id: str, offset: int = 0, batch_size: int = 5, session: AsyncSession = Depends(get_session)):
    return await get_booking_batch(event_id, offset, batch_size, session)


@router.get("/user/{user_id}/bookings", response_model=List[UserBookingResponse])
async def user_bookings(user_id: str, session: AsyncSession = Depends(get_session)):
    """
    Get all bookings of a user with statuses RESERVED, WAITING, CANCELLED
    """
    return await get_user_bookings(user_id, session)



@router.post("/available-seats", response_model=AvailableSeatsResponse)
async def add_available_seats(req: AvailableSeatsRequest, session: AsyncSession = Depends(get_session)):
    """
    Create an entry in available_seats table for an event
    """
    return await create_available_seats(req, session)


@router.get("/available-seats/{event_id}", response_model=AvailableSeatsGetResponse)
async def available_seats(event_id: str, session: AsyncSession = Depends(get_session)):
    """
    Get available seats for a given event_id
    """
    return await get_available_seats(event_id, session)

