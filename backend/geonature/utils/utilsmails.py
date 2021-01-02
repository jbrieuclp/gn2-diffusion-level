# Fonctions génériques permettant l'envoie de mails

from flask import current_app
from flask_mail import Message

from server import MAIL


def send_mail(recipients, subject, msg_html):
    """
        Send email with Flask_mail

        .. :quickref:  Generic fonction for sending email

        :query [str] recipients: List of recipients
        :query str subject: Subjet of the mail
        :query str msg_html: Mail content in HTML

        **Returns:**
        .. void
    """
    if not MAIL:
        raise Exception("No configuration for email")

    with MAIL.connect() as conn:
        mail_sender = current_app.config.get('MAIL_DEFAULT_SENDER') 
        if not mail_sender:
            mail_sender = current_app.config["MAIL_USERNAME"]
        msg = Message(subject, sender=mail_sender, recipients=recipients)

        msg.html = msg_html

        conn.send(msg)
