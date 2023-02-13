from http import HTTPStatus
from typing import Union
import telegram
import requests
import os
import logging
import time
from dotenv import load_dotenv
import exceptions


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def check_tokens():
    """Проверяет доступность переменных окружения."""
    result = True
    if not all([
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]):
        result = False
        logger.critical('Не все переменные окружения получены.')
    return result


def send_message(bot: telegram.bot.Bot, message: str) -> None:
    """Отправляет сообщение в Telegram чат."""
    logger.debug('Попытка отправить сообщение.')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение успешно отправлено: {message}')
    except telegram.TelegramError as telegram_error:
        logger.error(f'Ошибка при отправке сообщения: {telegram_error}')


def get_api_answer(timestamp: int) -> Union[dict, requests.RequestException]:
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            logger.error(
                f'{ENDPOINT} недоступен.'
                f'Код ответа API: {response.status_code}'
            )
            raise exceptions.TheAnswerIsNotOk
        return response.json()
    except requests.RequestException as request_error:
        logger.error(f'Ошибка при запросе к основному API: {request_error}')
        return request_error


def check_response(response: dict) -> dict:
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError
    if 'homeworks' not in response:
        logger.error('Ключ homeworks или response имеет неправильное значение')
        raise KeyError
    if not isinstance(response['homeworks'], list):
        raise TypeError
    status = response['homeworks'][0].get('status')
    if status not in HOMEWORK_VERDICTS:
        logger.error('Получен недокументированный статус')
        raise exceptions.UndocumentedStatus
    return response['homeworks'][0]


def parse_status(homework: dict) -> str:
    """Извлекает статус из информации о конкретной домашней работы."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if homework_name is None:
        logger.error('Не получен ключ homework_name')
        raise KeyError
    if status not in HOMEWORK_VERDICTS or None:
        logger.error(f'Неизвестный статус: {status}')
        raise KeyError
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    if not check_tokens():
        exit()

    tmp_status = 'reviewing'
    errors = True

    while True:
        try:
            response = get_api_answer(0)
            homework = check_response(response)
            if homework and tmp_status != homework['status']:
                message = parse_status(homework)
                send_message(bot, message)
                tmp_status = homework['status']
            logger.info('Изменений нет')
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if errors:
                errors = False
                send_message(bot, message)
            logger.critical(message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
