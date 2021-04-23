import smtplib, ssl
import os
from email.message import EmailMessage
from django.conf import settings

port = 465
smtp_server = "smtp.gmail.com"
sender_email = settings.SENDER_EMAIL
receiver_email = settings.SUBSCRIBER_LIST

password = settings.EMAIL_PASSWORD


def send_email(message):
    print("Sending email with message: {}".format(message))
    msg = EmailMessage()
    msg.set_content(message)
    msg['Subject'] = 'Song Recommendation'
    msg['From'] = "Aakash Mishra"
    msg['To'] = receiver_email

    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    server.login(sender_email, password)
    server.send_message(msg)
    server.quit()