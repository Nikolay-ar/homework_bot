
class TheAnswerIsNot200Error(Exception):
    """Ответ сервера не равен 200."""


class EmptyListError(Exception):
    """Пустой словарь или список."""


class UndocumentedStatusError(Exception):
    """Недокументированный статус."""


class UndocumentedNameError(Exception):
    """Недокументированное имя домашней работы."""
