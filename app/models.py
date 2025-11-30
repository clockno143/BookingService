import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class AvailableSeats(Base):
    __tablename__ = "available_seats"
    event_id = sa.Column(UUID(as_uuid=True), primary_key=True)
    remaining_seats = sa.Column(sa.Integer, nullable=False)
    version = sa.Column(sa.Integer, nullable=False, server_default="1")

class Booking(Base):
    __tablename__ = "bookings"
    booking_id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = sa.Column(UUID(as_uuid=True))
    user_id = sa.Column(UUID(as_uuid=True))
    booking_time = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())
    status = sa.Column(sa.String(20), nullable=False)
    event_name = sa.Column(sa.String, nullable=False)
    user_email = sa.Column(sa.String, nullable=False)
