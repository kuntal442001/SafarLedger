from flask import current_app
from flask_mail import Message

from app.extensions import mail


def send_email(subject, recipients, body):
    """
    Sends an email if MAIL_SERVER is configured in the environment.

    Returns True if a real email was sent, False if it fell back to just
    logging the message (e.g. no mail server has been configured yet).
    Callers use the return value to decide whether to show the
    confirmation/reset link directly to the user instead of telling them
    to "check their email".
    """
    if current_app.config.get("MAIL_SERVER"):
        try:
            msg = Message(
                subject=subject,
                recipients=recipients,
                body=body,
                sender=current_app.config.get("MAIL_DEFAULT_SENDER"),
            )
            mail.send(msg)
            return True
        except Exception as exc:
            current_app.logger.error(
                f"Failed to send email to {recipients}: {exc}"
            )
            return False

    current_app.logger.info(
        f"[DEV EMAIL - no MAIL_SERVER configured]\n"
        f"To: {recipients}\nSubject: {subject}\n\n{body}"
    )
    return False
