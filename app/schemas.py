from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
class BookEventRequest(BaseModel):
    event_id: UUID
    user_id: UUID
    user_email:str
    event_Name:str


class BookEventResponse(BaseModel):
    status: str
    message: str
    reservation_id: str | None = None

class BookingStatusResponse(BaseModel):
    status: str
    message: str



class BookingBatchResponse(BaseModel):
    booking_id: str
    event_id: str
    user_id: str
    booking_time: datetime
    status: str
    event_name: str
    user_email: str

class UserBookingResponse(BaseModel):
    booking_id: str
    event_id: str
    event_name: str
    booking_time: datetime
    status: str
    user_email: str


class AvailableSeatsRequest(BaseModel):
    event_id: str
    remaining_seats: int

class AvailableSeatsResponse(BaseModel):
    event_id: str
    remaining_seats: int
    version: int