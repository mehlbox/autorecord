#!/usr/bin/env python3
# requirements: flask, pyalsaaudio

from flask import Flask, render_template, request, Response

import os
import threading
import json
import logging
import socket

log_control = logging.getLogger('werkzeug')
log_control.setLevel(logging.ERROR)

app = Flask(__name__)

# decorator function
def require_local_ip(func):
    def wrapper(*args, **kwargs):
        requester_ip = request.remote_addr

        # Check if the requester's IP is local
        if not f.ip_check(requester_ip):
            return json.dumps({'error': 'Access denied. Only local IP addresses are allowed.'}), 403

        # Call the original function
        return func(*args, **kwargs)

    # Preserve the name and docstring of the original function
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__

    return wrapper

@app.route('/')
def main():
    return render_template('index.html')

@app.route('/get_all_data', methods=['GET', 'POST'])
def export_data():
    data = {
        'fileinfo' : autorecorder.get_fileinfo(),
        'gpio' : autorecorder.get_sw(),
        'status' : autorecorder.get_status(),
        'powersupply' : f.check_power_supply(),
        'config' : config.get_status()
    }
    return json.dumps(data, indent=4)


@app.route('/get_schedule', methods=['GET'])
def get_schedule():
    data = {}
    data['weekdays'], data['holidays'], data['schedule_matrix'] = f.is_allowed(config, True)
    return json.dumps(data, indent=4)


@app.route('/get_log', methods=['GET'])
def get_log():
    return Response(m.get_log(), content_type='text/plain')


@app.route('/set_config', methods=['POST'])
@require_local_ip
def set_config(): # config applies on reboot
    data = dict(request.json)
    data['sample_rate'] = int(data['sample_rate'])
    data['file_limit'] = int(data['file_limit'])
    temp = dict(config.get_all())
    temp.update(data)
    config.set_all(temp)
    return json.dumps(config.get_all())


@app.route('/exit', methods=['POST'])
@require_local_ip
def exit_recorder():
    try:
        m.log("called exit")
        autorecorder.status = 'exit'
        
        if hasattr(autorecorder, 'file'):
            autorecorder.write_file()
            autorecorder.close_file()

        pid = str(os.getpid())
        pid_web = str(webserver.native_id)
        r = os.system(f'/audio/restart.py {pid} {pid_web}')
        return {'status':'OK', 'return_code': r}
    except Exception as e:
        return {'status':'error', 'error_message':e}

@app.route('/reboot', methods=['POST'])
@require_local_ip
def reboot():
    try:
        m.log('system reboot called')
        r = os.system("/sbin/reboot")
        return {'status':'OK', 'return_code': r}
    except Exception as e:
        return {'status':'error', 'error_message':e}

@app.route('/call_split', methods=['POST'])
@require_local_ip
def call_split():
    m.log('file split called')
    autorecorder.write_file()
    autorecorder.close_file()
    autorecorder.new_file()
    return {'status':'OK'}

@app.route('/matrix', methods=['get'])
def send_matrix():
    new_matrix = {}
    weekdays = config.get_element('weekdays')
    for key, value in config.get_element('schedule_matrix').items():
        index = weekdays.index(key)
        new_matrix[index] = value
    return json.dumps(new_matrix), 200

@app.route('/matrix', methods=['POST'])
@require_local_ip
def receive_matrix():
    new_matrix = {}
    weekdays = config.get_element('weekdays')
    for key, value in request.get_json().items():
        new_matrix[weekdays[int(key)]] = value
    config.set_element('schedule_matrix', new_matrix)
    return '', 200


def is_port_in_use(port: int) -> bool:
    """check if given port is already in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

if __name__ == '__main__':

    # make this better, (not by port)
    port = 80
    if is_port_in_use(port):
        print('port ' + str(port) + ' already in use')

    else:
        import functions as f
        import classes as c
        import manage as m

        config = m.manage_config()
        
        # webserver
        webserver = threading.Thread(target=lambda: app.run(host='0.0.0.0', debug=True, use_reloader=False, port=config.get_element('http_port')))
        webserver.start()

        # filemaker
        autorecorder = c.filemaker(config)
        autorecorder.autowrite()
