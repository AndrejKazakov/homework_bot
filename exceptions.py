class TheAnswerIsNotOk(Exception):
    """Статус ответа отличен от 200."""


class UndocumentedStatus(Exception):
    """Получен недокументированный статус"""
