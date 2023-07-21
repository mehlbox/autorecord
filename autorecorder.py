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


@app.route('/')
def main():
    return render_template('index.html')

@app.route('/get_all_data', methods=['GET', 'POST'])
def export_data():
    data = {
        'fileinfo' : wavefile.get_fileinfo(),
        'storage_mode' : config.get_element('storage_mode'),
        'gpio' : wavefile.get_sw(),
        'status' : wavefile.get_status(),
        'powersupply' : f.check_power_supply(),
        'config' : config.get_all()
    }
    return json.dumps(data, indent=4)


@app.route('/feiertage', methods=['GET'])
def feiertage():
    return f.is_allowed(config, True)

@app.route('/get_log', methods=['GET'])
def get_log():
    return Response(m.get_log(), content_type='text/plain')

@app.route('/set_config', methods=['POST'])
def set_config(): # config applies on reboot
    data = dict(request.json)
    data['sample_rate'] = int(data['sample_rate'])
    data['file_limit'] = int(data['file_limit'])
    temp = dict(config.get_all())
    temp.update(data)
    config.set_all(temp)
    #exit_recorder()
    return json.dumps(config.get_all())

@app.route('/exit', methods=['POST'])
def exit_recorder():
    m.log("called exit")
    wavefile.status = 'exit'
    try:
        wavefile.write_file()
        wavefile.close_file()
    except Exception as error:
        m.log('warning: could not close file')
        m.log(error)

    pid = str(os.getpid())
    pid_web = str(webserver.native_id)
    #os.system("kill " + pid_web)
    #os.system("kill " + pid)
    os.system(f'/audio/restart.py {pid} {pid_web}')
    return {'status':'OK'}

@app.route('/reboot', methods=['POST'])
def reboot():
    m.log('system reboot called')
    os.system("reboot")
    return {'status':'OK'}

@app.route('/call_split', methods=['POST'])
def call_split():
    m.log('file split called')
    wavefile.write_file()
    wavefile.close_file()
    wavefile.new_file()
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
        wavefile = c.filemaker(config)
        wavefile.autowrite()
