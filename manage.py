import json
import alsaaudio as aa
from datetime import datetime as dt, timedelta as td


class manage_config:

    def __init__(self):
        """load configuration from json file"""
        self.fileNamePath = '/audio/settings.json'
        try:
            log(self.config_data)
        except:
            pass

        try:
            with open(self.fileNamePath) as f:
                self.config_data = json.load(f)
        except Exception as error:
            log('error: could not read config file')
            log(error)
            self.config_data = {}
        else:
            log('loading config file succeeded')

        if self.config_data is None:
            self.config_data = {}

        self.__load__('recpath_online' , '/mnt/autorecord')
        self.__load__('recpath_offline', '/mnt/autorecord-offline')
        self.__load__('network_path'   , '/volume1/autorecord')
        self.__load__('network_ip'     , '10.1.0.11')

        self.__load__('num_channels', 2)
        self.__load__('bit_depth', '16 bit')
        self.__load__('sample_rate', 48000)
        self.__load__('file_limit', 600)
        self.__load__('device', 'sysdefault:CARD=sndrpihifiberry')

        self.__load__('http_port', 80)
        self.__load__('gpio_pin', 22)
        self.__load__('gpio_invert', False)
        self.__load__('gpio_debouncing', 30) # time in seconds
        
        # always default
        self.config_data['recpath'] = ''
        self.config_data['storage_mode'] = 'offline'
        self.config_data['initial_status'] = 'standby' # standby -> start -> run -> stop -> standby


        if self.config_data['bit_depth'] == '16 bit':
            self.config_data['audio_format'] = aa.PCM_FORMAT_S16_LE
            self.config_data['byte_depth'] = 2 # 2 bytes -> 16 bit
        if self.config_data['bit_depth'] == '24 bit':
            self.config_data['audio_format'] = aa.PCM_FORMAT_S24_LE
            self.config_data['byte_depth'] = 3 # 3 bytes -> 24 bit

        # calculate rest of the configuration
        self.config_data['period_size'] = int(self.config_data['sample_rate'] * 2 * 0.1)
        self.config_data['latency']     = int(self.config_data['period_size'] * 1000 / self.config_data['sample_rate'])
        self.config_data['check_in_time'] = self.config_data['period_size'] / self.config_data['sample_rate'] * 0.25 # get data after buffer filled about 50%

        # global weekdays
        if 'weekdays' not in self.config_data:
            self.config_data['weekdays'] = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        # make a empty schedule if needed
        if 'schedule_matrix' not in self.config_data:
            self.config_data['schedule_matrix'] = {}
            for weekday in self.config_data['weekdays']:
                self.config_data['schedule_matrix'][weekday] = [True] * 24

        
    def __load__(self, element, default):
        """load element and set default if element is not available"""
        if not element in self.config_data:
            self.config_data[element] = default

    def get_element(self, element):
        return self.config_data[element]

    def get_all(self):
        return self.config_data
    
    def get_status(self):
        new_data = {}
        new_data['bit_depth']           = self.config_data['bit_depth']
        new_data['sample_rate']         = self.config_data['sample_rate']
        new_data['file_limit']          = self.config_data['file_limit']
        new_data['storage_mode']        = self.config_data['storage_mode']
        return new_data

    def set_element(self, element, config):
        if self.config_data[element] != config: # prevent regular write action
            self.config_data[element] = config
            log(f'config element "{element}" was set to "{config}"')
            with open(self.fileNamePath, 'w') as f:
                f.write(json.dumps(self.config_data, indent=4))

    def set_all(self, config):
        if self.config_data != config: # prevent regular write action
            log(f'set all with {config}')
            self.config_data = config
            with open(self.fileNamePath, 'w') as f:
                f.write(json.dumps(self.config_data, indent=4))
    

def get_log():
    try:
        with open("/audio/autorecord.log", "r") as file:
            return file.read()
    except:
        return 'unable to read logfile !!!'

def log(message):
    now = dt.now().strftime("%a, %d %b %Y %H:%M:%S")
    print(message)
    with open("/audio/autorecord.log", "a") as file:
        file.write(f"{now}: {message}\n")

def log_cleanup():
    log_file_path = '/audio/autorecord.log'

    # Calculate the date two weeks ago from the current date
    two_weeks_ago = dt.now() - td(weeks=2)

    # Read the logfile and filter lines
    with open(log_file_path, 'r') as file:
        lines = file.readlines()
        filtered_lines = []
        for line in lines:
            if parse_date(line) >= two_weeks_ago:
                filtered_lines.append(line)

    # Write the filtered lines back to the logfile
    with open(log_file_path, 'w') as file:
        file.writelines(filtered_lines)

    # Function to parse the date from a line in the logfile
    def parse_date(line):
        date_str = line[:25]  # Extract the date portion from the line
        return dt.strptime(date_str, '%a, %d %b %Y %H:%M:%S')
