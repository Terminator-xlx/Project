# src/services/payment_processor.py
from typing import Dict, List, Optional
from datetime import datetime
import logging
from .payment_gateway import PaymentGateway, PaymentError
from .email_service import EmailService, EmailError

logger = logging.getLogger(__name__)


class PaymentProcessor:
    """Основной класс для обработки платежей"""

    def __init__(self, payment_gateway: PaymentGateway, email_service: EmailService):
        self.payment_gateway = payment_gateway
        self.email_service = email_service
        self.transactions: List[Dict] = []

    def make_payment(self, amount: float, card_token: str, user_email: str,
                     description: str = "") -> Dict:
        """Выполнение платежа"""
        # Валидация входных данных
        self._validate_payment_data(amount, card_token, user_email)

        try:
            # Обработка платежа через шлюз
            result = self.payment_gateway.process_payment(amount, card_token)

            # Сохранение транзакции
            transaction = {
                "id": result.get("transaction_id"),
                "amount": amount,
                "status": result.get("status"),
                "user_email": user_email,
                "description": description,
                "timestamp": datetime.now().isoformat(),
                "card_last_four": card_token[-4:] if len(card_token) >= 4 else "****"
            }
            self.transactions.append(transaction)

            # Отправка чека
            if result.get("status") == "success":
                try:
                    self.email_service.send_receipt(
                        email=user_email,
                        amount=amount,
                        transaction_id=result.get("transaction_id")
                    )
                    transaction["receipt_sent"] = True
                except EmailError as e:
                    logger.warning(f"Failed to send receipt: {e}")
                    transaction["receipt_sent"] = False
                    transaction["receipt_error"] = str(e)
            else:
                transaction["receipt_sent"] = False

            return {
                "success": result.get("status") == "success",
                "transaction_id": result.get("transaction_id"),
                "message": result.get("message", ""),
                "amount": amount,
                "timestamp": transaction["timestamp"]
            }

        except PaymentError as e:
            logger.error(f"Payment failed: {e}")
            raise

    def _validate_payment_data(self, amount: float, card_token: str, user_email: str):
        """Валидация данных платежа"""
        if amount <= 0:
            raise ValueError("Сумма платежа должна быть положительной")

        if amount > 1000000:  # Максимальная сумма
            raise ValueError("Сумма платежа не может превышать 1 000 000 руб.")

        if not card_token or not card_token.strip():
            raise ValueError("Токен карты не может быть пустым")

        if len(card_token) < 10:
            raise ValueError("Неверный формат токена карты")

        if not user_email or "@" not in user_email:
            raise ValueError("Неверный формат email")

    def get_transaction_stats(self) -> Dict:
        """Получение статистики транзакций"""
        if not self.transactions:
            return {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "total_amount": 0,
                "success_rate": 0,
                "average_amount": 0
            }

        successful = [t for t in self.transactions if t.get("status") == "success"]
        failed = [t for t in self.transactions if t.get("status") != "success"]

        total_amount = sum(t.get("amount", 0) for t in self.transactions)
        average_amount = total_amount / len(self.transactions) if self.transactions else 0

        return {
            "total": len(self.transactions),
            "successful": len(successful),
            "failed": len(failed),
            "total_amount": total_amount,
            "average_amount": round(average_amount, 2),
            "success_rate": round((len(successful) / len(self.transactions)) * 100, 2)
        }

    def get_transaction_by_id(self, transaction_id: str) -> Optional[Dict]:
        """Получение транзакции по ID"""
        for transaction in self.transactions:
            if transaction.get("id") == transaction_id:
                return transaction
        return None

    def get_user_transactions(self, user_email: str) -> List[Dict]:
        """Получение транзакций пользователя"""
        return [t for t in self.transactions if t.get("user_email") == user_email]

    def clear_transactions(self):
        """Очистка истории транзакций"""
        self.transactions.clear()
        logger.info("Transaction history cleared")