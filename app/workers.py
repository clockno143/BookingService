import asyncio
import json
from aio_pika import connect_robust
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session_maker
from app.models import Booking
from app.config import RABBITMQ_URL, GMAIL_USER, GMAIL_APP_PASSWORD
from aiosmtplib import send
from email.message import EmailMessage
from sqlalchemy.dialects.postgresql import insert



async def worker():
    print("Worker started... Listening for messages.")

    connection = await connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    queue = await channel.declare_queue("booking_queue", durable=True)

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                payload = json.loads(message.body)
                print(f"[worker] Received: {payload}")
                await finalize_booking(payload)


async def finalize_booking(payload: dict):
    reservation_id = payload["reservation_id"]
    event_id = payload["event_id"]
    user_id = payload["user_id"]
    user_email = payload["user_email"]
    event_name = payload["Event_Name"]  # make sure keys match your queue message
    status = payload["status"]

    async with async_session_maker() as session:
        stmt = insert(Booking).values(
            booking_id=reservation_id,
            event_id=event_id,
            user_id=user_id,
            user_email=user_email,
            event_name=event_name,
            status=status
        ).on_conflict_do_update(
            index_elements=[Booking.booking_id],  # primary key
            set_={
                "status": status,
                "event_id": event_id,
                "user_id": user_id,
                "user_email": user_email,
                "event_name": event_name
            }
        )

        await session.execute(stmt)
        await session.commit()

        print(f"[worker] Booking upserted: {reservation_id}")

        # Send email after saving to DB
        await send_confirmation_email(user_email, event_name, reservation_id, status)
        print(f"[worker] Email sent to {user_email}")

async def send_confirmation_email(to_email: str, eventName: str, reservation_id: str,status):
    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = "Your Event Booking Confirmation"

    msg.set_content(
        f"""
Hello,

Your booking has been {status}!

Event nmae: {eventName}
Reservation ID: {reservation_id}

Thank you for booking with us.

Best regards,
Event Team
"""
    )

    await send(
        msg,
        hostname="smtp.gmail.com",
        port=587,
        start_tls=True,
        username=GMAIL_USER,
        password=GMAIL_APP_PASSWORD,
    )


if __name__ == "__main__":
    asyncio.run(worker())
