from pydantic import BaseModel
from uuid import UUID

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
