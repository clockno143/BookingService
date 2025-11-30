from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .schemas import BookEventRequest, BookEventResponse, BookingStatusResponse
from .database import get_session
from .services import reserve_seat, get_booking_status,cancel_booking,promote_waiting_booking
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from .database import async_session_maker

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

        # 2️⃣ Promote a waiting booking asynchronously
        if "booking_id" in cancel_result:  # optional: if cancel_booking returns the booking object
            import asyncio
            asyncio.create_task(promote_waiting_booking(cancel_result["booking_id"], session))

        return cancel_result