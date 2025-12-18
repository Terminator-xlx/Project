# tests/integration/test_payment_flow.py
import pytest
from unittest.mock import Mock, patch
from src.services.payment_gateway import PaymentGateway
from src.services.email_service import EmailService
from src.services.payment_processor import PaymentProcessor


class TestPaymentIntegration:
    """Интеграционные тесты для потока платежей"""

    @pytest.fixture
    def real_gateway(self):
        """Реальный PaymentGateway (но с замоканным requests)"""
        return PaymentGateway(api_key="test_key_123")

    @pytest.fixture
    def real_email_service(self):
        """Реальный EmailService"""
        return EmailService(
            smtp_server="smtp.test.com",
            smtp_user="",
            smtp_password=""  # Без credentials - будет только логировать
        )

    def test_full_payment_flow_with_mocked_api(self, real_gateway, real_email_service):
        """Полный поток платежа с замоканным API"""
        # Создаем реальные объекты
        processor = PaymentProcessor(real_gateway, real_email_service)

        # Мокаем только requests.post внутри PaymentGateway
        with patch('src.services.payment_gateway.requests.post') as mock_post:
            # Настройка мока
            mock_response = Mock()
            mock_response.json.return_value = {
                "status": "success",
                "transaction_id": "txn_int_123456",
                "message": "Payment successful"
            }
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            # Выполняем платеж
            result = processor.make_payment(
                amount=2500.75,
                card_token="tok_int_987654321",
                user_email="integration@test.com",
                description="Integration test payment"
            )

            # Проверяем результат
            assert result["success"] is True
            assert result["transaction_id"] == "txn_int_123456"
            assert result["amount"] == 2500.75

            # Проверяем вызов API
            mock_post.assert_called_once_with(
                "https://api.payment-gateway.com/payments",
                json={
                    "amount": 2500.75,
                    "card_token": "tok_int_987654321",
                    "api_key": "test_key_123"
                },
                timeout=10
            )

            # Проверяем сохранение транзакции
            assert len(processor.transactions) == 1
            transaction = processor.transactions[0]
            assert transaction["id"] == "txn_int_123456"
            assert transaction["user_email"] == "integration@test.com"
            assert transaction["description"] == "Integration test payment"

            # Проверяем статистику
            stats = processor.get_transaction_stats()
            assert stats["total"] == 1
            assert stats["successful"] == 1
            assert stats["success_rate"] == 100.0

    def test_payment_flow_with_retry_logic(self):
        """Тест потока платежа с логикой повторных попыток"""
        # Этот тест можно расширить для тестирования retry логики
        # Например, при временной ошибке сети

        gateway = PaymentGateway(api_key="test_key")
        email_service = EmailService()
        processor = PaymentProcessor(gateway, email_service)

        call_count = 0

        def mock_post_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # Первый вызов падает с ConnectionError
                raise ConnectionError("Network error")
            else:
                # Второй вызов успешен
                mock_response = Mock()
                mock_response.json.return_value = {
                    "status": "success",
                    "transaction_id": "txn_retry_123"
                }
                mock_response.raise_for_status.return_value = None
                return mock_response

        with patch('src.services.payment_gateway.requests.post') as mock_post:
            mock_post.side_effect = mock_post_side_effect

            # В текущей реализации это вызовет исключение
            # Но можно показать, как бы работала retry логика
            with pytest.raises(Exception):
                processor.make_payment(1000, "tok_retry", "test@example.com")

            # Проверяем, что было 2 попытки
            assert call_count == 2

    def test_multiple_payments_statistics(self):
        """Тест статистики после нескольких платежей"""
        gateway = PaymentGateway(api_key="test_key")
        email_service = EmailService()
        processor = PaymentProcessor(gateway, email_service)

        # Мокаем API для последовательных вызовов
        responses = [
            {"status": "success", "transaction_id": "txn_1"},
            {"status": "failed", "transaction_id": "txn_2"},
            {"status": "success", "transaction_id": "txn_3"},
        ]

        response_iter = iter(responses)

        def mock_post_side_effect(*args, **kwargs):
            mock_response = Mock()
            response = next(response_iter)
            mock_response.json.return_value = response
            mock_response.raise_for_status.return_value = None
            return mock_response

        with patch('src.services.payment_gateway.requests.post') as mock_post:
            mock_post.side_effect = mock_post_side_effect

            # Выполняем 3 платежа
            processor.make_payment(1000, "tok_1", "user1@example.com")
            processor.make_payment(2000, "tok_2", "user2@example.com")
            processor.make_payment(1500, "tok_3", "user3@example.com")

        # Проверяем статистику
        stats = processor.get_transaction_stats()

        assert stats["total"] == 3
        assert stats["successful"] == 2
        assert stats["failed"] == 1
        assert stats["total_amount"] == 4500  # 1000 + 2000 + 1500
        assert stats["success_rate"] == pytest.approx(66.67, 0.01)

    def test_user_specific_transactions(self):
        """Тест получения транзакций конкретного пользователя"""
        gateway = PaymentGateway(api_key="test_key")
        email_service = EmailService()
        processor = PaymentProcessor(gateway, email_service)

        # Создаем тестовые транзакции
        test_transactions = [
            {"id": "txn_1", "user_email": "alice@example.com", "amount": 1000},
            {"id": "txn_2", "user_email": "bob@example.com", "amount": 2000},
            {"id": "txn_3", "user_email": "alice@example.com", "amount": 1500},
            {"id": "txn_4", "user_email": "charlie@example.com", "amount": 500},
            {"id": "txn_5", "user_email": "alice@example.com", "amount": 300},
        ]

        # Используем патч, чтобы избежать реальных API вызовов
        with patch.object(processor, 'transactions', test_transactions):
            # Получаем транзакции Алисы
            alice_transactions = processor.get_user_transactions("alice@example.com")

            assert len(alice_transactions) == 3
            assert all(t["user_email"] == "alice@example.com" for t in alice_transactions)

            # Проверяем суммы
            amounts = [t["amount"] for t in alice_transactions]
            assert sum(amounts) == 2800  # 1000 + 1500 + 300

    def test_payment_processor_with_different_email_services(self):
        """Тест PaymentProcessor с разными конфигурациями EmailService"""
        gateway = PaymentGateway(api_key="test_key")

        # Тест 1: EmailService с credentials
        email_with_creds = EmailService(
            smtp_server="smtp.gmail.com",
            smtp_user="sender@gmail.com",
            smtp_password="password123"
        )

        processor1 = PaymentProcessor(gateway, email_with_creds)
        assert processor1.email_service.smtp_user == "sender@gmail.com"

        # Тест 2: EmailService без credentials (только логирование)
        email_without_creds = EmailService(
            smtp_server="smtp.test.com",
            smtp_user="",
            smtp_password=""
        )

        processor2 = PaymentProcessor(gateway, email_without_creds)
        assert processor2.email_service.smtp_user == ""

        # Оба процессора должны работать
        assert isinstance(processor1, PaymentProcessor)
        assert isinstance(processor2, PaymentProcessor)

    def test_error_propagation_in_integration(self):
        """Тест распространения ошибок через всю цепочку"""
        gateway = PaymentGateway(api_key="test_key")
        email_service = EmailService()
        processor = PaymentProcessor(gateway, email_service)

        # Симулируем ошибку на уровне API
        with patch('src.services.payment_gateway.requests.post') as mock_post:
            mock_post.side_effect = ConnectionError("No internet connection")

            # Ошибка должна пройти через весь стек
            with pytest.raises(Exception) as exc_info:
                processor.make_payment(1000, "tok_error", "test@example.com")

            # Проверяем, что транзакция не сохранилась
            assert len(processor.transactions) == 0