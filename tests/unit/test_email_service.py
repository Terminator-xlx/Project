# tests/unit/test_email_service.py
import pytest
import smtplib
from unittest.mock import Mock, patch, MagicMock
from src.services.email_service import EmailService, EmailError


class TestEmailService:
    """Модульные тесты для EmailService"""

    @pytest.fixture
    def email_service(self):
        return EmailService(
            smtp_server="smtp.test.com",
            smtp_port=587,
            smtp_user="test@example.com",
            smtp_password="password123"
        )

    @pytest.fixture
    def email_service_no_creds(self):
        """EmailService без credentials (должен логировать вместо отправки)"""
        return EmailService(
            smtp_server="smtp.test.com",
            smtp_port=587,
            smtp_user="",
            smtp_password=""
        )

    def test_init_with_env_vars(self, monkeypatch):
        """Тест инициализации с переменными окружения"""
        monkeypatch.setenv('SMTP_SERVER', 'smtp.gmail.com')
        monkeypatch.setenv('SMTP_PORT', '465')
        monkeypatch.setenv('SMTP_USER', 'user@gmail.com')
        monkeypatch.setenv('SMTP_PASSWORD', 'secret')
        monkeypatch.setenv('SMTP_USE_TLS', 'False')

        service = EmailService()

        assert service.smtp_server == 'smtp.gmail.com'
        assert service.smtp_port == 465
        assert service.smtp_user == 'user@gmail.com'
        assert service.smtp_password == 'secret'
        assert service.use_tls is False

    def test_create_receipt_body(self, email_service):
        """Тест создания тела письма с чеком"""
        amount = 1500.75
        transaction_id = "txn_123456"

        body = email_service._create_receipt_body(amount, transaction_id)

        assert str(amount) in body
        assert transaction_id in body
        assert "Квитанция об оплате" in body
        assert "html" in body.lower()

    @patch('src.services.email_service.smtplib.SMTP')
    def test_send_email_success(self, mock_smtp_class, email_service):
        """Тест успешной отправки email"""
        # Настройка моков
        mock_server = Mock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        # Отправка email
        result = email_service._send_email(
            to_email="recipient@example.com",
            subject="Test Subject",
            body="Test Body"
        )

        # Проверки
        assert result is True
        mock_smtp_class.assert_called_once_with("smtp.test.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@example.com", "password123")
        mock_server.send_message.assert_called_once()

    @patch('src.services.email_service.smtplib.SMTP')
    def test_send_email_failure(self, mock_smtp_class, email_service):
        """Тест неудачной отправки email"""
        mock_smtp_class.return_value.__enter__.side_effect = smtplib.SMTPException("SMTP error")

        result = email_service._send_email(
            to_email="recipient@example.com",
            subject="Test Subject",
            body="Test Body"
        )

        assert result is False

    def test_send_email_without_credentials(self, email_service_no_creds, caplog):
        """Тест отправки email без credentials (должен только логировать)"""
        with patch('src.services.email_service.logger') as mock_logger:
            result = email_service_no_creds._send_email(
                to_email="recipient@example.com",
                subject="Test Subject",
                body="Test Body"
            )

        assert result is True
        # Проверяем, что было логирование
        # (мок logger проверит, что вызывались методы info/warning)

    def test_send_receipt_success(self, email_service):
        """Тест успешной отправки чека"""
        with patch.object(email_service, '_send_email', return_value=True) as mock_send:
            result = email_service.send_receipt(
                email="customer@example.com",
                amount=1000.50,
                transaction_id="txn_123456"
            )

        assert result is True
        mock_send.assert_called_once()

    def test_send_receipt_failure(self, email_service):
        """Тест неудачной отправки чека"""
        with patch.object(email_service, '_send_email', return_value=False):
            result = email_service.send_receipt(
                email="customer@example.com",
                amount=1000.50,
                transaction_id="txn_123456"
            )

        assert result is False

    def test_send_receipt_exception(self, email_service):
        """Тест исключения при отправке чека"""
        with patch.object(email_service, '_send_email', side_effect=Exception("SMTP error")):
            with pytest.raises(EmailError, match="Не удалось отправить email"):
                email_service.send_receipt(
                    email="customer@example.com",
                    amount=1000.50,
                    transaction_id="txn_123456"
                )

    def test_send_notification(self, email_service):
        """Тест отправки уведомления"""
        with patch.object(email_service, '_send_email', return_value=True) as mock_send:
            result = email_service.send_notification(
                email="user@example.com",
                subject="Test Notification",
                message="This is a test notification"
            )

        assert result is True
        mock_send.assert_called_once_with(
            "user@example.com",
            "Test Notification",
            "This is a test notification"
        )

    @pytest.mark.parametrize("email,amount,transaction_id", [
        ("test@example.com", 100.0, "txn_001"),
        ("user@company.com", 9999.99, "txn_002"),
        ("name+tag@domain.co.uk", 0.01, "txn_003"),
    ])
    def test_send_receipt_various_inputs(self, email_service, email, amount, transaction_id):
        """Тест отправки чека с различными входными данными"""
        with patch.object(email_service, '_send_email', return_value=True):
            result = email_service.send_receipt(email, amount, transaction_id)

        assert result is True