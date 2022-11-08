import os
import datetime
import sys
import time
import requests
import telegram
from dotenv import load_dotenv
import logging
from telegram import Bot

from exceptions import TheAnswerIsNot200Error, EmptyListError, \
    UndocumentedStatusError, UndocumentedNameError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('TOKEN_HW')
TELEGRAM_TOKEN = os.getenv('TOKEN_TM')
TELEGRAM_CHAT_ID = os.getenv('ID_N')

RETRY_TIME = 60 * 0.1
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

log = logging.getLogger("ex")


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат.
    На вход два параметра: экземпляр класса Bot и строка с текстом сообщения.
    """
    bot.send_message(TELEGRAM_CHAT_ID, message)


def get_api_answer(current_timestamp):
    """Сделать запрос к API, вернуть."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.ConnectionError:
        raise ConnectionError('Эндпоинт: {ENDPOINT} не доступен')
    if response.status_code != 200:
        raise TheAnswerIsNot200Error(
            f'Эндпоинт {ENDPOINT} с HEADERS: {HEADERS}, с параметрами {params}'
            f' не доступен и имеет статус кода {response.status_code}')
    try:
        return response.json()
    except ValueError:
        raise ValueError(f'Ответ на запрос {ENDPOINT} не в формате json')


def check_response(response):
    """
    Проверяет ответ API приведенный к типам данных Python.
    Если ответ API соответствует ожиданиям, то функция должна вернуть список
    домашних работ
    (он может быть и пустым), доступный в ответе API по ключу 'homeworks'
    """
    if not (isinstance(response, dict)):
        raise TypeError(f'Ошибка response: '
                        f'{response} не является словарём')
    if 'homeworks' not in response:
        raise KeyError(
            f'Ошибка '
            f'В словаре {response} отсутствует ключ: "homeworks"')
    if 'current_date' not in response:
        raise KeyError(
            f'Ошибка '
            f'В словаре {response} отсутствует ключ: "current_date"')
    homeworks = response['homeworks']
    if homeworks is None:
        raise EmptyListError('Некорректный ответ сервера')
    if not (isinstance(homeworks, list)):
        raise TypeError(f'Ошибка возвращаемый объект по ключу homeworks: '
                        f'{homeworks} не является списком')
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы.
    В случае успеха, функция возвращает подготовленную для отправки в Telegram
    строку, содержащую один из вердиктов словаря HOMEWORK_STATUSES
    """
    homework_name = homework['homework_name']
    homework_status = homework.get('status')
    if homework_status is None:
        raise UndocumentedStatusError(
            f'Ошибка пустое значение homework_status: {homework_status}')
    if homework_name is None:
        raise UndocumentedNameError(
            f'Ошибка пустое значение homework_name: {homework_name}')

    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens_bool = True
    if PRACTICUM_TOKEN is None:
        tokens_bool = False
        logging.critical('Отсутствует обязательная переменная окружения:'
                         '"PRACTICUM_TOKEN" Программа остановлена.')
    if TELEGRAM_TOKEN is None:
        tokens_bool = False
        logging.critical('Отсутствует обязательная переменная окружения: '
                         '"TELEGRAM_TOKEN" Программа остановлена.')
    if TELEGRAM_CHAT_ID is None:
        tokens_bool = False
        logging.critical('Отсутствует обязательная переменная окружения: '
                         '"TELEGRAM_CHAT_ID" Программа остановлена.')
    return tokens_bool


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        level=logging.DEBUG,
        filename='main.log',
        format='%(asctime)s, %(funcName)s, %(levelname)s, %(message)s'
    )
    if not check_tokens():
        sys.exit('Отсутствует обязательная переменная окружения')
    bot = Bot(token=TELEGRAM_TOKEN)
    now = datetime.datetime.now()
    message = f'Я начал свою работу: {now.strftime("%d-%m-%Y %H:%M")}'
    try:
        send_message(bot, message)
        logging.info(f'Сообщение в Telegram отправлено: {message}')
    except telegram.TelegramError as telegram_error:
        logging.error(
            f'Сообщение в Telegram не отправлено: {telegram_error}')

    current_timestamp = int(time.time()) - 1550000000
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks_info = check_response(response)
            if len(homeworks_info) == 0:
                logging.info('Нет работ на проверку')
            elif len(homeworks_info) > 0:
                message = parse_status(homeworks_info[0])
                send_message(bot, message)
            else:
                logging.debug('Статус не изменился')

            current_timestamp = int(time.time())

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            try:
                send_message(bot, message)
            except telegram.TelegramError as telegram_error:
                logging.error(
                    f'Сообщение в Telegram не отправлено: {telegram_error}')
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
