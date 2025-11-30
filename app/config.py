import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
RESERVATION_EXPIRY_MINUTES = int(os.getenv("RESERVATION_EXPIRY_MINUTES", 10))
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
GMAIL_USER="nikhilvishnubonageri@gmail.com"
GMAIL_APP_PASSWORD="bgrz axhf etif suky"