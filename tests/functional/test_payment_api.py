# tests/functional/test_payment_api.py
import json
import pytest
from unittest.mock import Mock, patch


class TestPaymentAPI:
    """Функциональные тесты для API endpoints"""

    def test_health_check(self, client):
        """Тест health check endpoint"""
        response = client.get('/api/health')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert data['service'] == 'payment-api'
        assert 'version' in data

    def test_create_payment_success(self, client, mocker):
        """Тест успешного создания платежа через API"""
        # Мокаем сервисы
        mock_processor = mocker.Mock()
        mock_result = {
            "success": True,
            "transaction_id": "txn_api_123",
            "message": "Payment successful",
            "amount": 1500.50,
            "timestamp": "2024-01-15T12:30:00"
        }
        mock_processor.make_payment.return_value = mock_result

        # Подменяем payment_processor в приложении
        mocker.patch('src.app.payment_processor', mock_processor)

        # Отправляем запрос
        response = client.post('/api/payments',
                               json={
                                   "amount": 1500.50,
                                   "card_token": "tok_api_123456789",
                                   "user_email": "api_test@example.com",
                                   "description": "API test payment"
                               }
                               )

        # Проверяем ответ
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['transaction_id'] == 'txn_api_123'
        assert data['message'] == 'Платеж успешно обработан'

        # Проверяем вызов сервиса
        mock_processor.make_payment.assert_called_once_with(
            amount=1500.50,
            card_token="tok_api_123456789",
            user_email="api_test@example.com",
            description="API test payment"
        )

    def test_create_payment_validation_error(self, client):
        """Тест валидации входных данных через API"""
        # Тест 1: Отсутствует обязательное поле
        response = client.post('/api/payments',
                               json={
                                   "amount": 1000,
                                   # card_token отсутствует
                                   "user_email": "test@example.com"
                               }
                               )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'card_token' in data['error']

        # Тест 2: Невалидная сумма
        response = client.post('/api/payments',
                               json={
                                   "amount": -100,
                                   "card_token": "tok_123",
                                   "user_email": "test@example.com"
                               }
                               )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_create_payment_payment_error(self, client, mocker):
        """Тест ошибки платежа через API"""
        # Мокаем исключение от платежного сервиса
        mock_processor = mocker.Mock()
        mock_processor.make_payment.side_effect = Exception("Payment gateway error")

        mocker.patch('src.app.payment_processor', mock_processor)

        response = client.post('/api/payments',
                               json={
                                   "amount": 1000,
                                   "card_token": "tok_123",
                                   "user_email": "test@example.com"
                               }
                               )

        # При ошибке платежного шлюза должен быть 502
        assert response.status_code == 502
        data = json.loads(response.data)
        assert 'error' in data

    def test_get_payment_by_id_found(self, client, mocker):
        """Тест получения платежа по ID (найден)"""
        mock_processor = mocker.Mock()
        mock_transaction = {
            "id": "txn_123",
            "amount": 1000,
            "status": "success",
            "user_email": "test@example.com",
            "timestamp": "2024-01-15T12:30:00"
        }
        mock_processor.get_transaction_by_id.return_value = mock_transaction

        mocker.patch('src.app.payment_processor', mock_processor)

        response = client.get('/api/payments/txn_123')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['id'] == 'txn_123'

        mock_processor.get_transaction_by_id.assert_called_once_with('txn_123')

    def test_get_payment_by_id_not_found(self, client, mocker):
        """Тест получения платежа по ID (не найден)"""
        mock_processor = mocker.Mock()
        mock_processor.get_transaction_by_id.return_value = None

        mocker.patch('src.app.payment_processor', mock_processor)

        response = client.get('/api/payments/nonexistent')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_get_payment_stats(self, client, mocker):
        """Тест получения статистики платежей"""
        mock_processor = mocker.Mock()
        mock_stats = {
            "total": 10,
            "successful": 8,
            "failed": 2,
            "total_amount": 15000,
            "average_amount": 1500,
            "success_rate": 80.0
        }
        mock_processor.get_transaction_stats.return_value = mock_stats

        mocker.patch('src.app.payment_processor', mock_processor)

        response = client.get('/api/payments/stats')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data'] == mock_stats

    def test_get_payment_history(self, client, mocker):
        """Тест получения истории платежей"""
        mock_transactions = [
            {"id": f"txn_{i}", "amount": i * 1000, "user_email": f"user{i}@example.com"}
            for i in range(1, 16)  # 15 транзакций
        ]

        mock_processor = mocker.Mock()
        mock_processor.transactions = mock_transactions

        mocker.patch('src.app.payment_processor', mock_processor)

        # Тест с пагинацией
        response = client.get('/api/payments/history?page=2&per_page=5')

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['success'] is True
        assert len(data['data']['transactions']) == 5
        assert data['data']['pagination']['page'] == 2
        assert data['data']['pagination']['per_page'] == 5
        assert data['data']['pagination']['total'] == 15
        assert data['data']['pagination']['total_pages'] == 3

        # Транзакции на странице 2 должны быть с 6 по 10
        transaction_ids = [t['id'] for t in data['data']['transactions']]
        assert transaction_ids == ['txn_6', 'txn_7', 'txn_8', 'txn_9', 'txn_10']

    def test_get_payment_history_with_user_filter(self, client, mocker):
        """Тест истории платежей с фильтром по пользователю"""
        mock_processor = mocker.Mock()

        # Мокаем метод get_user_transactions
        user_transactions = [
            {"id": "txn_1", "amount": 1000, "user_email": "alice@example.com"},
            {"id": "txn_3", "amount": 1500, "user_email": "alice@example.com"},
        ]
        mock_processor.get_user_transactions.return_value = user_transactions

        mocker.patch('src.app.payment_processor', mock_processor)

        response = client.get('/api/payments/history?user_email=alice@example.com')

        assert response.status_code == 200
        data = json.loads(response.data)

        assert len(data['data']['transactions']) == 2
        assert all(t['user_email'] == 'alice@example.com' for t in data['data']['transactions'])

        mock_processor.get_user_transactions.assert_called_once_with('alice@example.com')

    def test_validate_card_endpoint(self, client, mocker):
        """Тест endpoint валидации карты"""
        mock_gateway = mocker.Mock()
        mock_gateway.validate_card.return_value = True

        mocker.patch('src.app.payment_gateway', mock_gateway)

        response = client.post('/api/cards/validate',
                               json={"card_token": "tok_valid_123456789"}
                               )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['valid'] is True

        mock_gateway.validate_card.assert_called_once_with("tok_valid_123456789")

    def test_validate_card_missing_token(self, client):
        """Тест валидации карты без токена"""
        response = client.post('/api/cards/validate',
                               json={}  # Нет card_token
                               )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Токен карты обязателен' in data['error']

    def test_404_error_handler(self, client):
        """Тест обработчика 404 ошибок"""
        response = client.get('/api/nonexistent/endpoint')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['error'] == 'Ресурс не найден'

    def test_method_not_allowed_error(self, client):
        """Тест обработчика 405 ошибок"""
        # Пытаемся вызвать POST на endpoint, который поддерживает только GET
        response = client.post('/api/health')

        assert response.status_code == 405
        data = json.loads(response.data)
        assert 'error' in data

    def test_api_error_handling(self, client, mocker):
        """Тест обработки непредвиденных ошибок в API"""
        # Симулируем неожиданное исключение
        mock_processor = mocker.Mock()
        mock_processor.make_payment.side_effect = ValueError("Unexpected error")

        mocker.patch('src.app.payment_processor', mock_processor)

        response = client.post('/api/payments',
                               json={
                                   "amount": 1000,
                                   "card_token": "tok_123",
                                   "user_email": "test@example.com"
                               }
                               )

        # Непредвиденные ошибки должны возвращать 500
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data