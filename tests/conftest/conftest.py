# tests/conftest.py
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from flask import Flask

# Добавляем src в путь для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.app import app as flask_app
from src.services.payment_gateway import PaymentGateway
from src.services.email_service import EmailService
from src.services.payment_processor import PaymentProcessor


@pytest.fixture
def app():
    """Фикстура Flask приложения для тестирования"""
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    return flask_app


@pytest.fixture
def client(app):
    """Фикстура тестового клиента Flask"""
    return app.test_client()


@pytest.fixture
def mock_gateway():
    """Фикстура мока платежного шлюза"""
    gateway = Mock(spec=PaymentGateway)
    gateway.base_url = "https://api.payment-gateway.com"
    gateway.api_key = "test_key_123"
    return gateway


@pytest.fixture
def mock_email():
    """Фикстура мока email сервиса"""
    email = Mock(spec=EmailService)
    email.smtp_server = "smtp.test.com"
    return email


@pytest.fixture
def payment_processor(mock_gateway, mock_email):
    """Фикстура PaymentProcessor с моками"""
    return PaymentProcessor(mock_gateway, mock_email)


@pytest.fixture
def sample_payment_data():
    """Фикстура с тестовыми данными платежа"""
    return {
        "amount": 1500.50,
        "card_token": "tok_test_123456789",
        "user_email": "customer@example.com",
        "description": "Test payment"
    }


@pytest.fixture
def successful_payment_response():
    """Фикстура с успешным ответом платежного шлюза"""
    return {
        "status": "success",
        "transaction_id": "txn_test_123456",
        "message": "Payment processed successfully"
    }


@pytest.fixture
def failed_payment_response():
    """Фикстура с неудачным ответом платежного шлюза"""
    return {
        "status": "failed",
        "transaction_id": "txn_test_654321",
        "message": "Insufficient funds"
    }


@pytest.fixture
def mock_requests_post():
    """Фикстура для мока requests.post"""
    with patch('src.services.payment_gateway.requests.post') as mock_post:
        yield mock_post


@pytest.fixture
def mock_smtp():
    """Фикстура для мока smtplib.SMTP"""
    with patch('src.services.email_service.smtplib.SMTP') as mock_smtp:
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        yield mock_server