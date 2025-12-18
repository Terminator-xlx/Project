# src/services/email_service.py
from typing import Dict
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

logger = logging.getLogger(__name__)


class EmailError(Exception):
    """Исключение для ошибок отправки email"""
    pass


class EmailService:
    """Сервис отправки email уведомлений"""

    def __init__(self, smtp_server: str = None, smtp_port: int = None,
                 smtp_user: str = None, smtp_password: str = None):
        self.smtp_server = smtp_server or os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = smtp_port or int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = smtp_user or os.getenv('SMTP_USER', '')
        self.smtp_password = smtp_password or os.getenv('SMTP_PASSWORD', '')
        self.use_tls = os.getenv('SMTP_USE_TLS', 'True').lower() == 'true'

    def send_receipt(self, email: str, amount: float, transaction_id: str) -> bool:
        """Отправка чека на email"""
        subject = f"Квитанция об оплате #{transaction_id}"
        body = self._create_receipt_body(amount, transaction_id)

        try:
            return self._send_email(email, subject, body)
        except Exception as e:
            logger.error(f"Ошибка отправки email: {e}")
            raise EmailError(f"Не удалось отправить email: {str(e)}")

    def _create_receipt_body(self, amount: float, transaction_id: str) -> str:
        """Создание тела письма с чеком"""
        return f"""
        <html>
        <body>
            <h2>Квитанция об оплате</h2>
            <p><strong>ID транзакции:</strong> {transaction_id}</p>
            <p><strong>Сумма:</strong> {amount:.2f} руб.</p>
            <p><strong>Статус:</strong> Успешно оплачено</p>
            <p>Спасибо за оплату!</p>
            <hr>
            <p><small>Это автоматическое письмо, пожалуйста, не отвечайте на него.</small></p>
        </body>
        </html>
        """

    def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Отправка email через SMTP"""
        if not self.smtp_user or not self.smtp_password:
            logger.warning("SMTP credentials not set. Email will be logged instead.")
            logger.info(f"Would send email to {to_email}: {subject}")
            return True

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.smtp_user
        msg['To'] = to_email

        html_part = MIMEText(body, 'html')
        msg.attach(html_part)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_notification(self, email: str, subject: str, message: str) -> bool:
        """Отправка уведомления"""
        return self._send_email(email, subject, message)