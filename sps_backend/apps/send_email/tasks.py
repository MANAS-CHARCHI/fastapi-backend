from celery import shared_task
import time

@shared_task
def send_email_task(email: str):
    # Your SMTP logic here
    time.sleep(5)  # Simulate network delay
    print(f"Sending email to {email}")
    return {"status": "sent", "to": email}
