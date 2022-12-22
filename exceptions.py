class StatusCodeError(Exception):
    """Код запроса отличается от ожидаемого."""

    pass


class TelegramError(Exception):
    """Ошибка отправки сообщения в Telegram."""

    pass


class ConnectionError(Exception):
    """Ошибка при запросе."""

    pass
