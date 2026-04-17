import datetime as dt
import os
import select
import shutil
import threading
import wave

import RPi.GPIO as GPIO
import alsaaudio as aa
from time import gmtime, sleep, strftime, time

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
        self.audio = bytearray()
        self.audio_lock = threading.Lock()
        self.file_lock = threading.RLock()
        self.express = ''
        self.do_maintenance = True
        self.audiocard = None
        self._capture_poll = None
        self._capture_poll_timeout_ms = max(50, int(self.check_in_time * 1000))
        self._capture_poll_failed = False

        self.sw = debouncePin(
            self.config.get_element('gpio_pin'),
            self.config.get_element('gpio_debouncing'),
            self.config.get_element('gpio_invert'),
        )
        self.sw.check_forever()

        self.start_capture()

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

    def start_capture(self):
        """Call this once after opening the device to start the background loop."""
        t = threading.Thread(target=self._capture_loop, daemon=True)
        t.start()

    def _setup_capture_poll(self):
        """Prepare poll descriptors for event-driven capture."""
        self._capture_poll = None
        self._capture_poll_failed = False
        try:
            descriptors = self.audiocard.polldescriptors()
            if not descriptors:
                m.log('warning: ALSA did not provide poll descriptors, fallback to timed reads')
                return

            poller = select.poll()
            for fd, eventmask in descriptors:
                poller.register(fd, eventmask)
            self._capture_poll = poller
        except Exception as error:
            m.log('warning: failed to setup ALSA poll descriptors, fallback to timed reads')
            m.log(error)
            self._capture_poll_failed = True

    def _close_audiocard(self):
        """Close capture device and clear poll resources."""
        self._capture_poll = None
        self._capture_poll_failed = False
        if self.audiocard is not None:
            try:
                self.audiocard.close()
            except Exception as error:
                m.log('error: could not close audiocard')
                m.log(error)
        self.audiocard = None

    def _append_audio(self, data):
        with self.audio_lock:
            self.audio.extend(data)

    def _snapshot_audio(self):
        with self.audio_lock:
            if not self.audio:
                return b''
            chunk = bytes(self.audio)
            self.audio.clear()
            return chunk

    def _capture_loop(self):
        """Runs in its own thread forever."""
        while True:
            if self.status != 'run' or self.audiocard is None:
                sleep(self.check_in_time)
                continue

            # Event-driven wakeup if ALSA poll descriptors are available.
            if self._capture_poll is not None:
                try:
                    events = self._capture_poll.poll(self._capture_poll_timeout_ms)
                except Exception as error:
                    if not self._capture_poll_failed:
                        m.log('warning: ALSA poll failed, fallback to timed reads')
                        m.log(error)
                        self._capture_poll_failed = True
                    self._capture_poll = None
                    events = []
                # Some ALSA/driver combos do not report POLLIN reliably via
                # polldescriptors_revents(); still attempt timed reads.
                if events:
                    for _, eventmask in events:
                        if eventmask & (select.POLLERR | select.POLLHUP | select.POLLNVAL):
                            m.log(f'warning: ALSA poll event mask={eventmask}, trying recovery read')

            # Read all currently available periods before sleeping again.
            had_data = False
            while self.status == 'run' and self.audiocard is not None:
                try:
                    length, data = self.audiocard.read()
                except aa.ALSAAudioError as error:
                    self.lostpackages += 1
                    m.log(f'warning: capture xrun/read error, recovering: {error}')
                    try:
                        self.audiocard.prepare()
                    except Exception as prepare_error:
                        m.log('error: audiocard recovery failed')
                        m.log(prepare_error)
                    break

                self.buffer = length

                if length == -32:
                    self.lostpackages += 1
                    m.log('warning: lost an audio package')
                    try:
                        self.audiocard.prepare()
                    except Exception as prepare_error:
                        m.log('error: audiocard prepare failed after lost package')
                        m.log(prepare_error)
                    break

                if length > 0:
                    had_data = True
                    self._append_audio(data)
                    if self.empty_readings:
                        m.log(f'warning: cleared {self.empty_readings} empty reads')
                        self.empty_readings = 0
                    continue

                # length == 0 on non-blocking reads means no more buffered periods right now
                break

            if not had_data:
                self.empty_readings += 1
                if self.empty_readings == 1:
                    m.log('warning: empty read from audiocard')
                elif self.empty_readings % 200 == 0:
                    m.log(f'error: {self.empty_readings} consecutive empty reads — capture device is delivering no audio data (check S/PDIF input signal and PLL lock)')
                if self._capture_poll is None:
                    sleep(self.check_in_time)

    def autowrite(self):
        """handle command written in status. do this forever."""
        previous_storage_mode = self.config.get_element('storage_mode')
        f.online_write_check(self.config)

        if self.status == 'run':
            self.filetime = int(time() - self.start_time)
        else:
            self.filetime = 0

        # change of online/offline status during recording
        if self.status == 'run' and previous_storage_mode == 'online' and self.config.get_element('storage_mode') == 'offline':
            self.write_file()
            self.close_file()
            self._close_audiocard()
            self.express = True
            self.status = 'start'
            m.log('express switch from online to offline')

        # change of online/offline status during recording
        if self.status == 'run' and previous_storage_mode == 'offline' and self.config.get_element('storage_mode') == 'online':
            self.write_file()
            self.close_file()
            self._close_audiocard()
            self.express = True
            self.status = 'start'
            m.log('express switch from offline to online')

        if self.status == 'standby' and self.sw.get_status() == 'on' and f.is_allowed(self.config):
            self.status = 'start'
            m.log('switch standby to start')

        if self.status == 'start':
            self.do_maintenance = False
            m.log('open audiocard')
            try:
                self.audiocard = aa.PCM(
                    aa.PCM_CAPTURE,
                    aa.PCM_NONBLOCK,
                    device=self.config.get_element('device'),
                    channels=self.config.get_element('num_channels'),
                    rate=self.config.get_element('sample_rate'),
                    format=self.config.get_element('audio_format'),
                    periodsize=self.config.get_element('period_size'),
                )
            except Exception as error:
                m.log('error: could not open audiocard')
                m.log(error)
                self.status = 'standby'
                self.do_maintenance = True
            else:
                self._setup_capture_poll()
                try:
                    m.log(f'ALSA realized capture config: {self.audiocard.info()}')
                except Exception:
                    pass

                self.new_file()
                if hasattr(self, 'file'):
                    self.status = 'run'
                    m.log('switch start to run')
                else:
                    m.log('warning: no file opened, close audiocard and retry')
                    self._close_audiocard()
                    self.status = 'standby'
                    self.do_maintenance = True

        if self.status == 'run':
            self.write_file()

        if self.status == 'run' and (self.sw.get_status() == 'off' or not f.is_allowed(self.config)):
            self.stop()
            m.log('switch run to stop')

        if self.status == 'stop':
            self.write_file()
            self.close_file()
            m.log('close audiocard')
            self._close_audiocard()
            self.status = 'standby'
            m.log('switch stop to standby')
            self.do_maintenance = True

        if self.do_maintenance:
            self.do_maintenance = False
            threading.Thread(target=lambda: f.maintenance(self.config)).start()

        # Flush every second while running to keep cut points tight and buffers small.
        callagain = 1
        threading.Timer(callagain, self.autowrite).start()

    def new_file(self):
        """create new file if there's enough disk space"""
        with self.file_lock:
            # required bytes: sample_rate * channels * bytes_per_sample * seconds
            sample_rate = self.config.get_element('sample_rate')
            channels = self.config.get_element('num_channels')
            byte_depth = self.config.get_element('byte_depth')
            seconds = self.config.get_element('file_limit')
            required_bytes = sample_rate * channels * byte_depth * seconds

            # ensure destination path exists
            self.destination = f.setup_record_path(self.config)
            os.makedirs(self.destination, exist_ok=True)

            # check free space
            st = shutil.disk_usage(self.destination)
            free = st.free
            if free < required_bytes:
                m.log(f'error: insufficient disk space ({free} bytes free, need ~{required_bytes} bytes)')
                return

            # everything is ok, proceed
            self.foldername = dt.datetime.now().strftime('%Y-%m-%d_%a')
            f.cc_folder(os.path.join(self.destination, self.foldername))
            self.filename = 'autorec_' + dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S') + '.wav'
            self.fullpath = os.path.join(self.destination, self.foldername, self.filename)

            # open the WAV and set header params
            self.file = wave.open(self.fullpath, 'wb')
            self.file.setframerate(sample_rate)
            self.file.setnchannels(channels)
            self.file.setsampwidth(byte_depth)

            self.start_time = time()
            self.filetime = 0
            self.actual_filetime = 0
            m.log(f'File: "{self.fullpath}" created')

    def write_file(self):
        """write audio from ram to file"""
        chunk = self._snapshot_audio()
        if not chunk:
            return

        with self.file_lock:
            if not hasattr(self, 'file'):
                m.log('warning: write_file() called but no opened file available.')
                return

            sample_rate = self.config.get_element('sample_rate')
            file_limit = self.config.get_element('file_limit')
            max_frames = sample_rate * file_limit
            bytes_per_frame = self.config.get_element('num_channels') * self.config.get_element('byte_depth')

            if bytes_per_frame <= 0:
                m.log('error: invalid bytes_per_frame value')
                return

            remainder = len(chunk) % bytes_per_frame
            if remainder:
                m.log(f'warning: dropping {remainder} trailing bytes (partial frame)')
                chunk = chunk[:-remainder]

            while chunk:
                if not hasattr(self, 'file'):
                    self.new_file()
                    if not hasattr(self, 'file'):
                        m.log('error: cannot open a new file while writing, dropping remaining audio chunk')
                        break

                frames_in_file = self.file.tell()
                frames_left = max_frames - frames_in_file

                if frames_left <= 0:
                    self.close_file()
                    self.new_file()
                    m.log('filelimit reached')
                    continue

                bytes_left = frames_left * bytes_per_frame
                part = chunk if len(chunk) <= bytes_left else chunk[:bytes_left]

                try:
                    self.file.writeframesraw(part)
                except Exception as error:
                    m.log('error: could not write into audio file')
                    m.log(error)
                    break
                try:
                    self.file._file.flush()
                except Exception:
                    pass

                chunk = chunk[len(part):]

                if self.file.tell() >= max_frames:
                    self.close_file()
                    self.new_file()
                    m.log('filelimit reached')

            if hasattr(self, 'file'):
                self.actual_filetime = int(self.file.tell() / sample_rate)

    def close_file(self):
        """close file, header will be written"""
        with self.file_lock:
            self.filename = ''
            self.filetime = 0
            self.actual_filetime = 0
            if hasattr(self, 'file'):
                try:
                    self.file.close()
                except Exception as error:
                    m.log('error: could not close file')
                    m.log(error)
                finally:
                    try:
                        del self.file
                    except AttributeError:
                        pass
            else:
                m.log('warning: close_file() called but no opened file available.')

    def get_fileinfo(self):
        """return dictionary with fileinfos"""
        if self.status == 'run':
            self.filetime = int(time() - self.start_time)
        else:
            self.filetime = 0

        data = {
            'foldername': self.foldername,
            'filename': self.filename,
            'filetime': strftime('%H:%M:%S', gmtime(self.filetime)),
            'actual_filetime': strftime('%H:%M:%S', gmtime(self.actual_filetime)),
            'filelimit': strftime('%H:%M:%S', gmtime(self.config.get_element('file_limit'))),
        }
        return data

    def get_status(self):
        """return dictionary with general status information"""
        with self.audio_lock:
            sizeofaudio = len(self.audio)
        if sizeofaudio > self.maxaudiochunk:
            self.maxaudiochunk = sizeofaudio
        data = {
            'status': self.status,
            # 'buffer' : int(self.buffer / self.config.get_element('period_size') * 100),
            # 'audiochunk' : sizeofaudio / self.maxaudiochunk * 100,
            'lostpackages': self.lostpackages,
            'fileprogressbar': round(self.filetime / self.config.get_element('file_limit') * 100, 2),
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
