#!/usr/bin/env python3
"""Demo web server for autorecord UI without ALSA/GPIO hardware."""

from flask import Flask, Response, render_template, request

import datetime as dt
import ipaddress
import json
import logging
import os
import threading
import time


dirname = os.path.dirname(__file__)

log_control = logging.getLogger('werkzeug')
log_control.setLevel(logging.ERROR)

app = Flask(__name__)


def _fmt_hms(seconds):
    seconds = max(0, int(seconds))
    return time.strftime('%H:%M:%S', time.gmtime(seconds))


class DemoLogger:
    def __init__(self):
        self._lock = threading.Lock()
        self._lines = []

    def log(self, message):
        now = dt.datetime.now().strftime('%a, %d %b %Y %H:%M:%S')
        line = f'{now}: {message}'
        with self._lock:
            self._lines.append(line)
            # keep memory bounded for long demo sessions
            if len(self._lines) > 5000:
                self._lines = self._lines[-5000:]
        print(line)

    def get_log(self, last=1000):
        with self._lock:
            return '\n'.join(self._lines[-last:])


class DemoConfig:
    def __init__(self, logger):
        self._lock = threading.Lock()
        self._logger = logger
        self._data = {
            'admin': True,
            'sample_rate': 48000,
            'bit_depth': '16 bit',
            'file_limit': 600,
            'storage_mode': 'offline',
            'http_port': int(os.getenv('DEMO_PORT', '8080')),
            'initial_status': os.getenv('DEMO_INITIAL_STATUS', 'run'),
            'gpio_pin': 22,
            'gpio_invert': False,
            'gpio_debouncing': 30,
            'weekdays': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
            'schedule_matrix': {},
        }

        for weekday in self._data['weekdays']:
            self._data['schedule_matrix'][weekday] = [True] * 24

    def get_element(self, element):
        with self._lock:
            return self._data[element]

    def get_all(self):
        with self._lock:
            return dict(self._data)

    def get_status(self):
        with self._lock:
            return {
                'bit_depth': self._data['bit_depth'],
                'sample_rate': self._data['sample_rate'],
                'file_limit': self._data['file_limit'],
                'storage_mode': self._data['storage_mode'],
            }

    def set_element(self, element, value):
        with self._lock:
            old = self._data.get(element)
            self._data[element] = value
        if old != value:
            self._logger.log(f'config element "{element}" set to "{value}"')

    def set_all(self, data):
        with self._lock:
            self._data.update(data)
        self._logger.log('config updated')


class MockRecorder:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self._lock = threading.Lock()

        self.foldername = ''
        self.filename = ''
        self.filetime = 0
        self.actual_filetime = 0
        self.start_time = time.time()
        self.lostpackages = 0
        self.status = self.config.get_element('initial_status')

        self._stop_event = threading.Event()
        self._ticker = threading.Thread(target=self._run, daemon=True)

        if self.status == 'run':
            self._new_file('demo start')

        self._ticker.start()

    def _new_file(self, reason):
        now = dt.datetime.now()
        self.foldername = now.strftime('%Y-%m-%d_%a')
        self.filename = 'autorec_' + now.strftime('%Y-%m-%d_%H-%M-%S') + '.wav'
        self.start_time = time.time()
        self.filetime = 0
        self.actual_filetime = 0
        self.logger.log(f'demo file created ({reason}): {self.foldername}/{self.filename}')

    def _run(self):
        while not self._stop_event.is_set():
            with self._lock:
                if self.status == 'run':
                    self.filetime = int(time.time() - self.start_time)
                    self.actual_filetime = self.filetime
                    limit = max(1, int(self.config.get_element('file_limit')))
                    if self.actual_filetime >= limit:
                        self._new_file('filelimit reached')
                else:
                    self.filetime = 0
                    self.actual_filetime = 0
            time.sleep(0.2)

    def get_sw(self):
        with self._lock:
            return 1 if self.status == 'run' else 0

    def get_fileinfo(self):
        with self._lock:
            return {
                'foldername': self.foldername,
                'filename': self.filename,
                'filetime': _fmt_hms(self.filetime),
                'actual_filetime': _fmt_hms(self.actual_filetime),
                'filelimit': _fmt_hms(self.config.get_element('file_limit')),
            }

    def get_status(self):
        with self._lock:
            limit = max(1, int(self.config.get_element('file_limit')))
            progress = round((self.filetime / limit) * 100, 2)
            return {
                'status': self.status,
                'lostpackages': self.lostpackages,
                'fileprogressbar': progress,
            }

    def split(self):
        with self._lock:
            if self.status == 'run':
                self._new_file('manual split')
                return True
            return False


def ip_check(ip_address):
    if ip_address in ('127.0.0.1', '::1', None):
        return True

    local_subnets = [
        ipaddress.IPv4Network('10.0.0.0/8'),
        ipaddress.IPv4Network('172.16.0.0/12'),
        ipaddress.IPv4Network('192.168.0.0/16'),
    ]
    try:
        ip_addr = ipaddress.IPv4Address(ip_address)
    except ipaddress.AddressValueError:
        return False

    return any(ip_addr in subnet for subnet in local_subnets)


def require_local_ip(func):
    def wrapper(*args, **kwargs):
        if os.getenv('DEMO_DISABLE_IP_CHECK', '0') == '1':
            return func(*args, **kwargs)

        requester_ip = request.remote_addr
        if not ip_check(requester_ip):
            return json.dumps({'error': 'Access denied. Only local IP addresses are allowed.'}), 403
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def require_admin(func):
    def wrapper(*args, **kwargs):
        if not config.get_element('admin'):
            return json.dumps({'error': 'Access denied. Admin functions are disabled.'}), 403
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def get_schedule_payload():
    weekdays = config.get_element('weekdays')
    schedule_matrix = config.get_element('schedule_matrix')

    indexed_matrix = {}
    for key, value in schedule_matrix.items():
        indexed_matrix[weekdays.index(key)] = value

    year = dt.datetime.now().year
    holidays = {
        f'01.01.{year}': 'Neujahrstag',
        f'01.05.{year}': 'Tag_der_Arbeit',
        f'03.10.{year}': 'Tag_der_Deutschen_Einheit',
        f'24.12.{year}': 'Heilig Abend',
        f'25.12.{year}': '1. Weihnachtstag',
        f'26.12.{year}': '2. Weihnachtstag',
        f'31.12.{year}': 'Silvester',
    }

    return weekdays, holidays, indexed_matrix


def check_power_supply():
    return ['Demo mode: no Raspberry Pi power telemetry available']


@app.route('/')
def main():
    return render_template('index.html')


@app.route('/get_all_data', methods=['GET', 'POST'])
def export_data():
    data = {
        'fileinfo': autorecorder.get_fileinfo(),
        'gpio': autorecorder.get_sw(),
        'status': autorecorder.get_status(),
        'powersupply': check_power_supply(),
        'config': config.get_status(),
    }
    return json.dumps(data, indent=4)


@app.route('/get_schedule', methods=['GET'])
def get_schedule():
    weekdays, holidays, schedule_matrix = get_schedule_payload()
    data = {
        'weekdays': weekdays,
        'holidays': holidays,
        'schedule_matrix': schedule_matrix,
    }
    return json.dumps(data, indent=4)


@app.route('/get_log', methods=['GET'])
def get_log():
    return Response(logger.get_log(), content_type='text/plain')


@app.route('/set_config', methods=['POST'])
@require_local_ip
@require_admin
def set_config():
    data = dict(request.json)

    if 'sample_rate' in data:
        data['sample_rate'] = int(data['sample_rate'])
    if 'file_limit' in data:
        data['file_limit'] = int(data['file_limit'])

    merged = config.get_all()
    merged.update(data)
    config.set_all(merged)

    logger.log(f'demo config updated via API: {data}')
    return json.dumps(config.get_all())


@app.route('/exit', methods=['POST'])
@require_local_ip
def exit_recorder():
    logger.log('demo exit called (no process restart in demo mode)')
    return {'status': 'OK', 'return_code': 0, 'note': 'demo mode does not restart process'}


@app.route('/reboot', methods=['POST'])
@require_local_ip
def reboot():
    logger.log('demo reboot called (no system reboot in demo mode)')
    return {'status': 'OK', 'return_code': 0, 'note': 'demo mode does not reboot host'}


@app.route('/call_split', methods=['POST'])
@require_local_ip
def call_split():
    if autorecorder.split():
        logger.log('manual file split')
    else:
        logger.log('manual file split ignored (wrong status)')
    return {'status': 'OK'}


@app.route('/matrix', methods=['GET'])
def send_matrix():
    new_matrix = {}
    weekdays = config.get_element('weekdays')
    for key, value in config.get_element('schedule_matrix').items():
        index = weekdays.index(key)
        new_matrix[index] = value
    return json.dumps(new_matrix), 200


@app.route('/matrix', methods=['POST'])
@require_local_ip
@require_admin
def receive_matrix():
    new_matrix = {}
    weekdays = config.get_element('weekdays')
    for key, value in request.get_json().items():
        new_matrix[weekdays[int(key)]] = value
    config.set_element('schedule_matrix', new_matrix)
    logger.log('demo schedule matrix updated')
    return '', 200


if __name__ == '__main__':
    logger = DemoLogger()
    config = DemoConfig(logger)
    autorecorder = MockRecorder(config, logger)

    port = config.get_element('http_port')
    logger.log(f'starting autorecord demo UI on port {port}')
    app.run(host='0.0.0.0', debug=True, use_reloader=False, port=port)
