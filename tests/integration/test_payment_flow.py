# tests/integration/test_payment_flow.py
import pytest
from src.services.payment_gateway import PaymentGateway
from src.services.email_service import EmailService
from src.services.payment_processor import PaymentProcessor


class TestPaymentIntegration:
    """Тестирование взаимодействия реальных компонентов"""

    @pytest.fixture
    def gateway(self):
        # Используем тестовый API ключ
        return PaymentGateway(api_key="test_key_123")

    @pytest.fixture
    def email_service(self):
        return EmailService()

    @pytest.fixture
    def processor(self, gateway, email_service):
        return PaymentProcessor(gateway, email_service)

    @patch('src.services.payment_gateway.requests.post')
    def test_full_payment_flow_with_mocked_api(self, mock_post, processor):
        """Полный поток с замоканным API"""
        # Настройка мока для внешнего API
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "transaction_id": "txn_123"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Выполнение платежа
        result = processor.make_payment(
            amount=1000.0,
            card_token="tok_test_123",
            user_email="test@example.com"
        )

        assert result["success"] is True
        assert result["transaction_id"] == "txn_123"