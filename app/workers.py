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

async def send_confirmation_email(to_email: str, eventName: str, reservation_id: str, status):
    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    
    # Customize subject based on status
    if status == "RESERVED":
        msg["Subject"] = "🎉 Event Booking Confirmed!"
        status_color = "#10b981"
        status_emoji = "✅"
        status_message = "Successfully Reserved"
    elif status == "WAITING":
        msg["Subject"] = "⏳ You're on the Waitlist"
        status_color = "#f59e0b"
        status_emoji = "⏳"
        status_message = "Added to Waitlist"
    else:
        msg["Subject"] = "📧 Event Booking Update"
        status_color = "#6366f1"
        status_emoji = "📧"
        status_message = status

    # Plain text fallback
    plain_text = f"""
Hello,

Your booking has been {status}!

Event Name: {eventName}
Reservation ID: {reservation_id}

Thank you for booking with us.

Best regards,
Event Team
"""
    
    # Beautiful HTML email
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-font-smoothing: antialiased;
        }}
        
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: #ffffff;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 40px 30px;
            text-align: center;
            color: white;
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}
        
        .status-badge {{
            display: inline-block;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            padding: 8px 20px;
            border-radius: 50px;
            margin-top: 15px;
            font-size: 14px;
            font-weight: 600;
        }}
        
        .content {{
            padding: 40px 30px;
        }}
        
        .greeting {{
            font-size: 18px;
            color: #1f2937;
            margin-bottom: 20px;
            font-weight: 500;
        }}
        
        .status-card {{
            background: linear-gradient(135deg, {status_color}15 0%, {status_color}05 100%);
            border-left: 4px solid {status_color};
            padding: 20px;
            border-radius: 12px;
            margin: 25px 0;
        }}
        
        .status-card h2 {{
            margin: 0 0 10px 0;
            color: {status_color};
            font-size: 20px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .status-card p {{
            margin: 0;
            color: #6b7280;
            font-size: 14px;
        }}
        
        .details-box {{
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 25px;
            margin: 25px 0;
        }}
        
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #e5e7eb;
        }}
        
        .detail-row:last-child {{
            border-bottom: none;
        }}
        
        .detail-label {{
            color: #6b7280;
            font-size: 14px;
            font-weight: 500;
        }}
        
        .detail-value {{
            color: #1f2937;
            font-size: 14px;
            font-weight: 600;
            text-align: right;
        }}
        
        .message {{
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 12px;
            padding: 20px;
            margin: 25px 0;
        }}
        
        .message p {{
            margin: 0;
            color: #1e40af;
            font-size: 14px;
            line-height: 1.6;
        }}
        
        .footer {{
            background: #f9fafb;
            padding: 30px;
            text-align: center;
            border-top: 1px solid #e5e7eb;
        }}
        
        .footer p {{
            margin: 5px 0;
            color: #6b7280;
            font-size: 13px;
        }}
        
        .footer strong {{
            color: #1f2937;
            font-weight: 600;
        }}
        
        .divider {{
            height: 1px;
            background: linear-gradient(to right, transparent, #e5e7eb, transparent);
            margin: 20px 0;
        }}
        
        @media only screen and (max-width: 600px) {{
            .container {{
                margin: 20px;
                border-radius: 12px;
            }}
            
            .header, .content, .footer {{
                padding: 25px 20px;
            }}
            
            .detail-row {{
                flex-direction: column;
                gap: 5px;
            }}
            
            .detail-value {{
                text-align: left;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎫 Event Booking Portal</h1>
            <div class="status-badge">
                {status_emoji} {status_message}
            </div>
        </div>
        
        <div class="content">
            <p class="greeting">Hello there! 👋</p>
            
            <div class="status-card">
                <h2>
                    <span>{status_emoji}</span>
                    <span>Booking {status_message}</span>
                </h2>
                <p>Your event booking request has been processed successfully.</p>
            </div>
            
            <div class="details-box">
                <div class="detail-row">
                    <span class="detail-label">📅 Event Name</span>
                    <span class="detail-value">{eventName}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">🎟️ Reservation ID</span>
                    <span class="detail-value">{reservation_id}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">📊 Status</span>
                    <span class="detail-value" style="color: {status_color}">{status}</span>
                </div>
            </div>
            
            <div class="message">
                <p>
                    <strong>💡 What's next?</strong><br>
                    {'Keep this email for your records. You can use your Reservation ID to check your booking status at any time.' if status == 'RESERVED' else 'We\'ll notify you as soon as a spot becomes available. Keep this email for your records!'}
                </p>
            </div>
            
            <div class="divider"></div>
            
            <p style="color: #6b7280; font-size: 14px; line-height: 1.6; margin: 20px 0;">
                Thank you for choosing our Event Booking Portal. We're excited to have you join us! 
                If you have any questions, feel free to reach out to our support team.
            </p>
        </div>
        
        <div class="footer">
            <p><strong>Event Team</strong></p>
            <p>Making your events memorable ✨</p>
            <p style="margin-top: 15px; font-size: 12px;">
                © 2025 Event Booking Portal. All rights reserved.
            </p>
        </div>
    </div>
</body>
</html>
"""
    
    msg.set_content(plain_text)
    msg.add_alternative(html_content, subtype='html')

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
