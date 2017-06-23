#!/usr/bin/python3

import requests
import sys

from base64 import b64encode
from json import dumps
from re import search
from time import time, sleep

from settings import ANTIGATE_KEY

def return_json(obj):
    print('Content-Type: application/json; charset=utf-8')
    print(dumps(obj))

def return_error(error_text):
    return_json({
        'result': 0,
        'error': error_text
    })
    sys.exit(1)

def current_milli_time():
   return str(round(time() * 1000))

def main():
    if not sys.argv[1]:
        return_error('Не указан VIN-код')

    vin = sys.argv[1].strip()

    if not search(r'^[0-9A-HJ-NPR-Z]{17}$', vin):
        return_error('Указан некорректный VIN-код')

    captcha_url = 'http://check.gibdd.ru/proxy/captcha.jpg?' + current_milli_time()
    captcha_response = requests.get(captcha_url)
    if not captcha_response.status_code == requests.codes.ok:
        return_error('Произошла ошибка при загрузке капчи')
    captcha_body = str(b64encode(captcha_response.content).decode('utf-8'))

    session_match = search(r'JSESSIONID=(.*?);', captcha_response.headers['Set-Cookie'])
    if not session_match:
        return_error('Не удалось получить идентификатор сессии')
    session_id = session_match.group(1)

    anticaptcha_task_payload = {
        'clientKey': ANTIGATE_KEY,
        'task': {
            'type': 'ImageToTextTask',
            'body': captcha_body,
            'phrase': False,
            'case': False,
            'numeric': 1,
            'math': False,
            'minLength': 0,
            'maxLength': 0
        }
    }
    anticaptcha_task_response = requests.post('https://api.anti-captcha.com/createTask', data = dumps(anticaptcha_task_payload))
    if not anticaptcha_task_response.status_code == requests.codes.ok:
        return_error('Произошла ошибка при создании задачи распознавания капчи')
    anticaptcha_task_data = anticaptcha_task_response.json()
    if anticaptcha_task_data['errorId']:
        return_error(anticaptcha_task_data['errorDescription'])

    anticaptcha_task_id = anticaptcha_task_data['taskId']
    anticaptcha_code = ''

    for i in range(5):
        sleep(3)
        anticaptcha_result_payload = {
            'clientKey': ANTIGATE_KEY,
            'taskId': anticaptcha_task_id
        }
        anticaptcha_result_response = requests.post('https://api.anti-captcha.com/getTaskResult', data = dumps(anticaptcha_result_payload))
        if not anticaptcha_result_response.status_code == requests.codes.ok:
            return_error('Произошла ошибка при получении ответа распознавания капчи')
        anticaptcha_result_data = anticaptcha_result_response.json()
        if anticaptcha_result_data['errorId']:
            return_error(anticaptcha_result_data['errorDescription'])
        if anticaptcha_result_data['status'] == 'ready':
            anticaptcha_code = anticaptcha_result_data['solution']['text']
            break

    if not anticaptcha_code:
        return_error('Произошла ошибка при распознавании капчи')

    history_cookies = requests.cookies.RequestsCookieJar()
    history_cookies.set('JSESSIONID', session_id, domain='check.gibdd.ru', path='/')
    history_payload = {
        'vin': vin,
        'captchaWord': anticaptcha_code,
        'checkType': 'history'
    }
    history_response = requests.post('http://check.gibdd.ru/proxy/check/auto/history', data = history_payload, cookies = history_cookies)
    if not history_response.status_code == requests.codes.ok:
        return_error('Произошла ошибка при получении информации о VIN-коде')
    history_data = history_response.json()

    if history_data['status'] == 200:
        return_json({
          'result': 1,
          'info': history_data['RequestResult']
        })
    else:
        return_error('Информация о VIN-коде не найдена')

if __name__ == '__main__':
    main()
