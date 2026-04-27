import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart


def send_with_retry(
    sender_email: str,
    sender_password: str,
    to_email: str,
    msg: MIMEMultipart,
    max_attempts: int = 3,
) -> bool:
    for attempt in range(1, max_attempts + 1):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, to_email, msg.as_string())
            return True
        except smtplib.SMTPAuthenticationError:
            logging.warning(
                "SMTP authentication failed for %s — not retrying", to_email
            )
            return False
        except Exception as exc:
            if attempt < max_attempts:
                delay = 2 ** (attempt - 1)
                logging.warning(
                    "Email to %s failed (attempt %d/%d): %s — retrying in %ds",
                    to_email,
                    attempt,
                    max_attempts,
                    exc,
                    delay,
                )
                time.sleep(delay)
            else:
                logging.warning(
                    "Email to %s failed after %d attempts: %s",
                    to_email,
                    max_attempts,
                    exc,
                )
    return False
