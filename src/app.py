# src/app.py
from flask import Flask, jsonify, request, render_template
import os
import logging
from services.payment_gateway import PaymentGateway, PaymentError
from services.email_service import EmailService, EmailError
from services.payment_processor import PaymentProcessor

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # Для корректного отображения кириллицы

# Инициализация сервисов
payment_gateway = PaymentGateway()
email_service = EmailService()
payment_processor = PaymentProcessor(payment_gateway, email_service)


@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint для мониторинга"""
    return jsonify({
        "status": "healthy",
        "service": "payment-api",
        "version": "1.0.0"
    })


@app.route('/api/payments', methods=['POST'])
def create_payment():
    """Создание нового платежа"""
    try:
        data = request.get_json()

        # Валидация обязательных полей
        required_fields = ['amount', 'card_token', 'user_email']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "error": f"Обязательное поле '{field}' отсутствует"
                }), 400

        amount = float(data['amount'])
        card_token = data['card_token']
        user_email = data['user_email']
        description = data.get('description', '')

        # Выполнение платежа
        result = payment_processor.make_payment(amount, card_token, user_email, description)

        if result['success']:
            logger.info(f"Payment successful: {result['transaction_id']}")
            return jsonify({
                "success": True,
                "data": result,
                "message": "Платеж успешно обработан"
            }), 201
        else:
            return jsonify({
                "success": False,
                "error": result.get('message', 'Платеж не удался')
            }), 400

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return jsonify({"error": str(e)}), 400
    except PaymentError as e:
        logger.error(f"Payment error: {e}")
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        logger.error(f"Internal server error: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@app.route('/api/payments/<transaction_id>', methods=['GET'])
def get_payment(transaction_id):
    """Получение информации о платеже по ID"""
    transaction = payment_processor.get_transaction_by_id(transaction_id)

    if not transaction:
        return jsonify({
            "error": f"Транзакция с ID '{transaction_id}' не найдена"
        }), 404

    return jsonify({
        "success": True,
        "data": transaction
    })


@app.route('/api/payments/stats', methods=['GET'])
def get_payment_stats():
    """Получение статистики платежей"""
    stats = payment_processor.get_transaction_stats()
    return jsonify({
        "success": True,
        "data": stats
    })


@app.route('/api/payments/history', methods=['GET'])
def get_payment_history():
    """Получение истории платежей"""
    user_email = request.args.get('user_email')

    if user_email:
        transactions = payment_processor.get_user_transactions(user_email)
    else:
        transactions = payment_processor.transactions

    # Пагинация
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    paginated_transactions = transactions[start_idx:end_idx]

    return jsonify({
        "success": True,
        "data": {
            "transactions": paginated_transactions,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": len(transactions),
                "total_pages": (len(transactions) + per_page - 1) // per_page
            }
        }
    })


@app.route('/api/cards/validate', methods=['POST'])
def validate_card():
    """Валидация карты"""
    try:
        data = request.get_json()

        if 'card_token' not in data:
            return jsonify({"error": "Токен карты обязателен"}), 400

        is_valid = payment_gateway.validate_card(data['card_token'])

        return jsonify({
            "success": True,
            "data": {
                "valid": is_valid,
                "card_token": data['card_token'][-4:] if is_valid else "****"
            }
        })
    except Exception as e:
        logger.error(f"Card validation error: {e}")
        return jsonify({"error": str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    """Обработчик 404 ошибок"""
    return jsonify({"error": "Ресурс не найден"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    """Обработчик 405 ошибок"""
    return jsonify({"error": "Метод не разрешен"}), 405


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='localhost', port=port, debug=debug)