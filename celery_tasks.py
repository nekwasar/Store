import asyncio
import os
import smtplib
from datetime import datetime, timezone
from email import encoders
from email.message import EmailMessage
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from celery import Celery

from db import db
from pdf import PDFReport

celery = Celery(
    'tasks',
    broker=os.environ.get('CELERY_BROKER_URL', 'amqp://guest:guest@rabbitmq:5672//'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/3'),
)

cart_collection = db['cart']

SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '465'))
SMTP_TIMEOUT = int(os.environ.get('SMTP_TIMEOUT', '10'))
GMAIL_USER = os.environ.get('GMAIL_USER', '')
GMAIL_PASS = os.environ.get('GMAIL_PASS', '')


@celery.task
def send_order_email(order_id: str, email_to: str):
    email = EmailMessage()
    email['Subject'] = 'Your order info'
    email['From'] = GMAIL_USER
    email['To'] = email_to

    email.set_content(f'You have successfully placed an order. Your order ID is {order_id}.')
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(email)


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(3600.0, delete_expired_carts.s(), name='delete expired carts')
    sender.add_periodic_task(1800.0, remind_abandoned_carts.s(), name='remind abandoned carts')


@celery.task
def remind_abandoned_carts():
    import asyncio
    from datetime import timedelta

    async def _remind():
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(hours=1)
        soon = now + timedelta(minutes=30)
        cursor = cart_collection.find({
            'expiration_time': {'$gt': now, '$lt': soon},
            'items': {'$ne': {}},
        })
        async for cart in cursor:
            pass

    loop = asyncio.get_event_loop()
    loop.run_until_complete(_remind())


@celery.task
def delete_expired_carts():
    expiration_time = datetime.now(timezone.utc)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        cart_collection.delete_many({'expiration_time': {'$lt': expiration_time}})
    )


@celery.task
def send_verification_email(email_to: str, token: str, base_url: str):
    verify_url = f"{base_url}/user/verify?token={token}"
    email = EmailMessage()
    email['Subject'] = 'Verify your email address'
    email['From'] = GMAIL_USER
    email['To'] = email_to
    email.set_content(
        f'Thank you for registering!\n\n'
        f'Please verify your email address by clicking the link below:\n\n'
        f'{verify_url}\n\n'
        f'This link expires in 24 hours.\n'
        f'If you did not create an account, please ignore this email.'
    )
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(email)


@celery.task
def send_password_reset_email(email_to: str, token: str, base_url: str):
    reset_url = f"{base_url}/user/reset-password?token={token}"
    email = EmailMessage()
    email['Subject'] = 'Password reset request'
    email['From'] = GMAIL_USER
    email['To'] = email_to
    email.set_content(
        f'You have requested a password reset.\n\n'
        f'Click the link below to reset your password:\n\n'
        f'{reset_url}\n\n'
        f'This link expires in 15 minutes.\n'
        f'If you did not request a password reset, please ignore this email.'
    )
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(email)


@celery.task
def send_bill_email(order):
    body = 'Please, find attached the invoice for your recent purchase.'

    message = MIMEMultipart()
    message['From'] = GMAIL_USER
    message['To'] = order['email']
    message['Subject'] = f'Invoice for order {order["_id"]}'
    message.attach(MIMEText(body, 'plain'))

    pdf_name = 'invoice.pdf'
    report = PDFReport()
    report_binary = report.get_report(order)
    payload = MIMEBase('application', 'octet-stream', Name=pdf_name)
    payload.set_payload(report_binary)
    encoders.encode_base64(payload)

    payload.add_header('Content-Disposition', 'attachment', filename='invoice.pdf')
    message.attach(payload)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(message)
