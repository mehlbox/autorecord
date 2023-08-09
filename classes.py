import sys
import datetime as dt
import threading
import RPi.GPIO as GPIO
import wave
import alsaaudio as aa
from time import time, strftime, gmtime

import functions as f
import manage as m

class filemaker:

    def __init__(self, config):
        self.config = config
        self.buffer = 0
        self.destination = ''
        self.foldername = ''
        self.filename = ''
        self.fullpath = ''
        self.filetime = 0
        self.actual_filetime = 0
        self.start_time = 0
        self.lostpackages = 0
        self.empty_readings = 0
        self.status = self.config.get_element('initial_status')
        self.check_in_time = self.config.get_element('check_in_time')
        self.maxaudiochunk = 0
        self.audio = b''
        self.express = ''
        self.do_maintenance = True

        self.sw = debouncePin(self.config.get_element('gpio_pin'), self.config.get_element('gpio_debouncing'), self.config.get_element('gpio_invert'))
        self.sw.check_forever()

        self.read_forever()

    def get_sw(self):
        return self.sw.read()

    def start(self):
        self.status = 'start'

    def stop(self):
        self.status = 'stop'
        self.lostpackages = 0
        if self.empty_readings != 0:
            m.log(f'warning: count of empty readings after stop: {self.empty_readings}')
            self.empty_readings = 0

    def read_forever(self):
        """read from audiocard to ram, loop forever to prevent audiocard cache to fill up.
        if the cache of the audiocard is filled, audio samples will get lost"""

        new_check_in_time = self.check_in_time
        if self.status == 'run':
            try:
                l, data = self.audiocard.read()
                self.buffer = l
            except Exception as error:
                m.log('error: could not read from audiocard')
                m.log(error)

            if l == -32: # Package lost, no data
                self.lostpackages += 1
                m.log('warning: lost a audio package')
            else:
                if l: # l is not empty
                    self.audio = self.audio + data # accumulate audio stream
                    if self.empty_readings != 0:
                        m.log(f'warning: count of empty readings during recording: {self.empty_readings}')
                        self.empty_readings = 0
                else: # l is empty
                    new_check_in_time = 0.5
                    self.empty_readings += 1
                    if self.empty_readings == 1:
                        m.log('warning: reading from empty audiocard.') # this might crash the audiocard

        threading.Timer(new_check_in_time, self.read_forever).start()

    def autowrite(self):
        """handle command written in status. do this forever."""
        previous_storage_mode = self.config.get_element('storage_mode')
        f.online_write_check(self.config)

        if self.status == 'run':
            self.filetime = int(time() - self.start_time)
        else:
            self.filetime = 0

        # change of online/offline status during recording
        if self.status == 'run' and previous_storage_mode == 'online' and self.config.get_element('storage_mode') == 'offline': # from online to offline
            self.close_file()
            self.express = True
            self.status = 'start'
            m.log('express switch from online to offline')

        # change of online/offline status during recording
        if self.status == 'run' and previous_storage_mode == 'offline' and self.config.get_element('storage_mode') == 'online': # from offline to online
            self.close_file()
            self.express = True
            self.status = 'start'
            m.log('express switch from offline to online')

        if self.status == 'standby' and self.sw.get_status() == 'on' and f.is_allowed(self.config):
            self.status = 'start'
            m.log('switch standby to start')

        if self.status == 'start': # and self.audio != b'':
            self.do_maintenance = False # During boot it is set to True. Don't do maintenance when recording.
            m.log('open audiocard')
            self.audiocard = aa.PCM(aa.PCM_CAPTURE, aa.PCM_NONBLOCK ,
                                    device = self.config.get_element('device'),
                                    channels = self.config.get_element('num_channels'),
                                    rate = self.config.get_element('sample_rate'),
                                    format = self.config.get_element('audio_format'),
                                    periodsize=self.config.get_element('period_size'))
            self.new_file()
            self.status = 'run'
            m.log('switch start to run')

        if self.status == 'run':
            self.write_file()

        if self.status == 'run' and (self.sw.get_status() == 'off' or not f.is_allowed(self.config)):
            self.stop()
            m.log('switch run to stop')

        if self.status == 'stop':
            self.close_file()
            m.log('close audiocard')
            self.audiocard.close()
            self.status = 'standby'
            m.log('switch stop to standby')
            self.do_maintenance = True

        if self.actual_filetime >= self.config.get_element('file_limit'):
            self.close_file()
            self.new_file()
            m.log('filelimit reached')

        if self.do_maintenance:
            self.do_maintenance = False
            threading.Thread(target=lambda: f.maintenance(self.config)).start()

        if self.status == 'run':
            callagain = 10
        else:
            callagain = 1
        threading.Timer(callagain, self.autowrite).start()

    def new_file(self):
        """create new file"""
        self.destination = f.setup_record_path(self.config)
        self.foldername = dt.datetime.now().strftime('%Y-%m-%d_%a')
        f.cc_folder(self.destination + '/' + self.foldername)
        self.filename = 'autorec_' + dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S') + '.wav'
        self.fullpath = self.destination + '/' + self.foldername + '/' + self.filename
        self.file = wave.open(self.fullpath, "wb") # open new file
        self.file.setframerate(self.config.get_element('sample_rate'))
        self.file.setnchannels(self.config.get_element('num_channels'))
        self.file.setsampwidth(self.config.get_element('byte_depth'))
        self.start_time = time()
        self.filetime = 0
        self.actual_filetime = 0
        m.log(f'File: "{self.fullpath}" created')


    def write_file(self):
        """write audio from ram to file"""
        if hasattr(self, 'file'):
            try:
                self.file.writeframes(self.audio)
            except Exception as error:
                m.log('error: could not write into audio file')
                m.log(error)

            self.actual_filetime = int(self.file.tell()/self.config.get_element('sample_rate')) # filetime in seconds
            if self.actual_filetime >= self.config.get_element('file_limit'):
                m.log('filelimit reached"') 
                self.close_file()
                self.new_file()
            self.audio = b''
        else:
            m.log('warning: write_file() called but no opened file available.')

    def close_file(self):
        """close file, header will be written"""
        self.filename = ''
        self.filetime = 0
        self.actual_filetime = 0
        if hasattr(self, "file"):
            try:
                self.file.close()
                self.file.__del__()
            except Exception as error:
                m.log('error: could not close file')
                m.log(error)
        else:
            m.log('warning: close_file() called but no opened file available.')

    def get_fileinfo(self):
        """return dictionary with fileinfos"""
        if self.status == 'run':
            self.filetime = int(time() - self.start_time)
        else:
            self.filetime = 0

        data = {
            'foldername' : self.foldername,
            'filename'   : self.filename,
            'filetime'   : strftime("%H:%M:%S", gmtime(self.filetime)),
            'actual_filetime' : strftime("%H:%M:%S", gmtime(self.actual_filetime)),
            'filelimit'  : strftime("%H:%M:%S", gmtime(self.config.get_element('file_limit'))),
        }
        return data

    def get_status(self):
        """return dictionary with general status information"""
        sizeofaudio = sys.getsizeof(self.audio)
        if sizeofaudio > self.maxaudiochunk:
            self.maxaudiochunk = sizeofaudio
        data = {
            'status' : self.status,
            # 'buffer' : int(self.buffer / self.config.get_element('period_size') * 100),
            # 'audiochunk' : sizeofaudio / self.maxaudiochunk * 100,
            'lostpackages' : self.lostpackages,
            'fileprogressbar' : round(self.filetime / self.config.get_element('file_limit') * 100, 2)
        }
        return data
    
    def set_maintenance(self):
        self.do_maintenance = True


class debouncePin:

    def __init__(self, pin, bouncetime, invert):
        self.pin = pin
        self.bouncetime = bouncetime
        self.last_bouncing_time = time()
        self.pin_invert = invert
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.debounced_state = self.invert(GPIO.input(self.pin))
        self.set_status(self.debounced_state)

    def check_forever(self):
        actual_state = self.invert(GPIO.input(self.pin))
        if self.debounced_state == actual_state:
            self.last_bouncing_time = time()
        if time() - self.last_bouncing_time > self.bouncetime and self.debounced_state != actual_state:
            self.debounced_state = actual_state
            self.set_status(self.debounced_state)
        threading.Timer(self.bouncetime / 10, self.check_forever).start()

    def invert(self, state):
        if self.pin_invert:
            if state:
                return False
            else:
                return True
        return state

    def set_status(self, state):

        if state == 1:
            self.action_state = 'on'
        else:
            self.action_state = 'off'
        m.log(f'Set gpio state to: {self.action_state}')

    def get_status(self):
        return self.action_state

    def read(self):
        return self.debounced_state


