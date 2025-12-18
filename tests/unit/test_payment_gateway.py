# tests/unit/test_payment_gateway.py
import pytest
import requests
from unittest.mock import Mock, patch
from src.services.payment_gateway import PaymentGateway, PaymentError


class TestPaymentGateway:
    """Модульные тесты для PaymentGateway"""

    @pytest.fixture
    def gateway(self):
        return PaymentGateway(api_key="test_key_123")

    def test_init_default_values(self):
        """Тест инициализации с значениями по умолчанию"""
        gateway = PaymentGateway()
        assert gateway.api_key is not None
        assert gateway.base_url == "https://api.payment-gateway.com"

    def test_process_payment_success(self, gateway, mock_requests_post):
        """Тест успешной обработки платежа"""
        # Настройка мока
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "transaction_id": "txn_123",
            "message": "Payment successful"
        }
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response

        # Вызов метода
        result = gateway.process_payment(1000.0, "tok_abc123")

        # Проверки
        assert result["status"] == "success"
        assert result["transaction_id"] == "txn_123"

        # Проверка вызова API
        mock_requests_post.assert_called_once_with(
            "https://api.payment-gateway.com/payments",
            json={
                "amount": 1000.0,
                "card_token": "tok_abc123",
                "api_key": "test_key_123"
            },
            timeout=10
        )

    def test_process_payment_timeout_error(self, gateway, mock_requests_post):
        """Тест таймаута при обработке платежа"""
        mock_requests_post.side_effect = requests.exceptions.Timeout("Request timeout")

        with pytest.raises(PaymentError, match="Таймаут соединения"):
            gateway.process_payment(1000.0, "tok_abc123")

    def test_process_payment_connection_error(self, gateway, mock_requests_post):
        """Тест ошибки соединения"""
        mock_requests_post.side_effect = requests.exceptions.ConnectionError("No connection")

        with pytest.raises(PaymentError, match="Нет соединения"):
            gateway.process_payment(1000.0, "tok_abc123")

    def test_process_payment_http_401_error(self, gateway, mock_requests_post):
        """Тест ошибки 401 (неавторизован)"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401")
        mock_requests_post.return_value = mock_response

        with pytest.raises(PaymentError, match="Неверный API ключ"):
            gateway.process_payment(1000.0, "tok_abc123")

    def test_process_payment_http_402_error(self, gateway, mock_requests_post):
        """Тест ошибки 402 (недостаточно средств)"""
        mock_response = Mock()
        mock_response.status_code = 402
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("402")
        mock_requests_post.return_value = mock_response

        with pytest.raises(PaymentError, match="Недостаточно средств"):
            gateway.process_payment(1000.0, "tok_abc123")

    def test_process_payment_http_500_error(self, gateway, mock_requests_post):
        """Тест ошибки 500 (серверная ошибка)"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
        mock_requests_post.return_value = mock_response

        with pytest.raises(PaymentError, match="Ошибка сервера"):
            gateway.process_payment(1000.0, "tok_abc123")

    @patch('src.services.payment_gateway.requests.get')
    def test_validate_card_success(self, mock_get, gateway):
        """Тест успешной валидации карты"""
        mock_response = Mock()
        mock_response.json.return_value = {"valid": True}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = gateway.validate_card("tok_abc123")

        assert result is True
        mock_get.assert_called_once_with(
            "https://api.payment-gateway.com/cards/tok_abc123/validate",
            params={"api_key": "test_key_123"},
            timeout=5
        )

    @patch('src.services.payment_gateway.requests.get')
    def test_validate_card_failure(self, mock_get, gateway):
        """Тест неудачной валидации карты"""
        mock_get.side_effect = requests.exceptions.RequestException("Error")

        result = gateway.validate_card("tok_abc123")

        assert result is False

    @pytest.mark.parametrize("amount,card_token", [
        (0.01, "tok_123"),  # Минимальная сумма
        (999999.99, "tok_456"),  # Большая сумма
        (100.50, "tok_" + "a" * 20),  # Длинный токен
    ])
    def test_process_payment_various_inputs(self, gateway, mock_requests_post, amount, card_token):
        """Тест обработки платежа с различными входными данными"""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "success", "transaction_id": "txn_123"}
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response

        result = gateway.process_payment(amount, card_token)

        assert result["status"] == "success"
        mock_requests_post.assert_called_once()