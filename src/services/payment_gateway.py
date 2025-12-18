# src/services/payment_gateway.py
import requests
from typing import Dict
import os


class PaymentError(Exception):
    """Исключение для ошибок платежа"""
    pass


class PaymentGateway:
    """Класс для работы с внешним платежным шлюзом"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('PAYMENT_API_KEY', 'test_key_123')
        self.base_url = os.getenv('PAYMENT_API_URL', "https://api.payment-gateway.com")

    def process_payment(self, amount: float, card_token: str) -> Dict:
        """Обработка платежа через внешний API"""
        try:
            response = requests.post(
                f"{self.base_url}/payments",
                json={
                    "amount": amount,
                    "card_token": card_token,
                    "api_key": self.api_key
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise PaymentError("Таймаут соединения с платежным шлюзом")
        except requests.exceptions.ConnectionError:
            raise PaymentError("Нет соединения с платежным шлюзом")
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise PaymentError("Неверный API ключ")
            elif response.status_code == 402:
                raise PaymentError("Недостаточно средств")
            elif response.status_code >= 500:
                raise PaymentError("Ошибка сервера платежного шлюза")
            else:
                raise PaymentError(f"Ошибка HTTP: {e}")
        except requests.exceptions.RequestException as e:
            raise PaymentError(f"Ошибка платежного шлюза: {e}")

    def validate_card(self, card_token: str) -> bool:
        """Валидация карты"""
        try:
            response = requests.get(
                f"{self.base_url}/cards/{card_token}/validate",
                params={"api_key": self.api_key},
                timeout=5
            )
            response.raise_for_status()
            return response.json().get('valid', False)
        except requests.exceptions.RequestException:
            return False