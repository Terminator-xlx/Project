# tests/e2e/test_payment_ui.py (опционально)
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class TestPaymentUI:
    """E2E тесты пользовательского интерфейса"""

    @pytest.fixture
    def driver(self):
        driver = webdriver.Chrome()
        driver.implicitly_wait(10)
        yield driver
        driver.quit()

    def test_payment_form_submission(self, driver, live_server):
        """Тест заполнения и отправки формы платежа"""
        # Переходим на страницу
        driver.get(f"{live_server.url}/")

        # Заполняем форму
        amount_input = driver.find_element(By.ID, "amount")
        amount_input.send_keys("1000")

        card_input = driver.find_element(By.ID, "card_token")
        card_input.send_keys("tok_test_123")

        email_input = driver.find_element(By.ID, "email")
        email_input.send_keys("test@example.com")

        # Отправляем форму
        submit_button = driver.find_element(By.ID, "submit-payment")
        submit_button.click()

        # Проверяем результат
        success_message = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "success-message"))
        )
        assert "Payment successful" in success_message.text