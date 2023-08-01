import os
from time import time, sleep
import datetime as dt
import subprocess
import ipaddress
import manage as m

def timer_func(func):
    """use this function to decorate another function to time it"""
    def wrap_func(*args, **kwargs):
        t1 = time()
        result = func(*args, **kwargs)
        t2 = time()
        print(f'Function {func.__name__!r} executed in {(t2-t1):.4f}s')
        return result
    return wrap_func

def ip_check(ip_address):
    # Define local subnet IP ranges
    local_subnets = [
        ipaddress.IPv4Network('10.0.0.0/8'),
        ipaddress.IPv4Network('172.16.0.0/12'),
        ipaddress.IPv4Network('192.168.0.0/16'),
    ]

    # Convert the IP address to an IPv4Address object
    try:
        ip_addr = ipaddress.IPv4Address(ip_address)
    except ipaddress.AddressValueError:
        return False

    # Check if the IP address is within any of the local subnets
    for subnet in local_subnets:
        if ip_addr in subnet:
            return True

    return False


def check_power_supply():
    """readout status from raspberry pi hardware"""
    with open('/sys/devices/platform/soc/soc:firmware/get_throttled', 'r') as f:
        status = int(f.read().strip(), 16)
    result = []

    if bool(status & 0x1):
        result.append('Spannung zu tief')
    if bool(status & 0x2):
        result.append('CPU Frequenz begrenzt')
    if bool(status & 0x4):
        result.append('CPU Frequenz gedrosselt')
    if bool(status & 0x8):
        result.append('Temperaturlimit erreicht')

    if len(result) == 0:
        result.append('Spannungsversorgung stabil')

    return result

def cc_folder(folder):
    """create a folder"""
    try:
        os.makedirs(folder)
        m.log(f'folder {folder} created')
    except:
        pass

def online_write_check(config):
    """test if online path is available"""
    
    if os.path.ismount(config.get_element('recpath_online') ):
        try: # try to write
            tempfile = f"""{config.get_element('recpath_online')}/autorecord_write_check.tmp"""
            with open(tempfile, "w"):
                pass
            os.remove(tempfile)
        except IOError:
            config.set_element('storage_mode', 'offline')
            return False
        else:
            config.set_element('storage_mode', 'online')
            return True
    config.set_element('storage_mode', 'offline')
    return False

def setup_record_path(config, express = False):
    """prepare path for writing"""

    online_write_check(config)

    if not express:
        if config.get_element('storage_mode') == 'offline':
            m.log('try to mount all mountpoints')
            cc_folder(config.get_element('recpath_online') )
            subprocess.Popen('mount -t nfs '+config.get_element('network_ip')+':'+config.get_element('network_path')+' '+config.get_element('recpath_online'), shell=True)
            sleep(1)
            online_write_check(config)
    else:
        express = False # reset to default

    if config.get_element('storage_mode') == 'offline':
        config.set_element('recpath', config.get_element('recpath_offline'))
    else:
        config.set_element('recpath', config.get_element('recpath_online'))

    return config.get_element('recpath')

def deltree(target):
    """delete a folder recursively"""
    for d in os.listdir(target):
        try:
            deltree(target + '/' + d)
        except OSError:
            os.remove(target + '/' + d)
    try:
        os.rmdir(target)
    except:
        return False
    else:
        m.log(f'folder {target} deleted')
        return True


def cleanup(recpath):
    """delete folder older than 14 days"""

    if recpath != '':
        m.log('cleanup...')
        folder_list = os.listdir(recpath)

        # remove aditional folder from list
        for i in folder_list:
            try:
                dt.strptime(i, "%Y-%m-%d_%a")
            except:
                folder_list.remove(i)

        # sort list
        folder_list.sort(key=lambda date: dt.datetime.strptime(date, "%Y-%m-%d_%a"))

        #delete oldest folder fist
        while len(folder_list) > 14:
            try:
                deltree(recpath + '/' + folder_list[0])
            except:
                m.log(f'unable to delete folder {folder_list[0]}')
                break
            else:
                folder_list.remove(folder_list[0])


def maintenance(config):
    """move files and folders created during a offline session"""
    m.log(f'maintenance start')

    if config.get_element('storage_mode') == 'offline':
        m.log('try to mount all mountpoints')
        cc_folder(config.get_element('recpath_online'))
        subprocess.Popen('mount -t nfs '+config.get_element('network_ip')+':'+config.get_element('network_path')+' '+config.get_element('recpath_online'), shell=True)
        sleep(1)
        online_write_check(config)

    if os.path.isdir(config.get_element('recpath_offline')):
        m.log('syncronize offline files to online path')
        if config.get_element('storage_mode') == 'online':
            m.log('moving offline files to online path')
            o = subprocess.Popen('rsync -a ' + config.get_element('recpath_offline') + '/* ' + config.get_element('recpath') + '/', shell=True, stdout=subprocess.PIPE)
            o.communicate()[0]
            if o.returncode == 0:
                deltree(config.get_element('recpath_offline'))
    cleanup(config.get_element('recpath'))
    m.log(f'maintenance finished')


def is_allowed(config, liste=False):
    
    def berechne_ostern(jahr):
        a = jahr % 19
        b = jahr // 100
        c = jahr % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        ostern = dt.date(jahr, (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1)
        return ostern

    
    today = dt.datetime.now().date()
    jahr = int(today.strftime("%Y"))
    ostern = berechne_ostern(jahr)

    feiertage = {
        dt.date(jahr, 1, 1): "Neujahrstag",
        ostern - dt.timedelta(days=2): "Karfreitag",
        ostern: "Ostersonntag",
        ostern + dt.timedelta(days=1): "Ostermontag",
        dt.date(jahr, 5, 1): "Tag_der_Arbeit",
        ostern + dt.timedelta(days=39): "Christi_Himmelfahrt",
        ostern + dt.timedelta(days=49): "Pfingstsonntag",
        ostern + dt.timedelta(days=50): "Pfingstmontag",
        ostern + dt.timedelta(days=60): "Fronleichnam",
        dt.date(jahr, 10, 3): "Tag_der_Deutschen_Einheit",
        dt.date(jahr, 11, 1): "Allerheiligen",
        dt.date(jahr, 12, 24): "Heilig Abend",
        dt.date(jahr, 12, 25): "1. Weihnachtstag",
        dt.date(jahr, 12, 26): "2. Weihnachtstag",
        dt.date(jahr, 12, 31): "Silvester",
    }

    def is_feiertag():
        if today in feiertage:
            return True
        return False

    schedule_matrix = config.get_element('schedule_matrix')
    weekdays = config.get_element('weekdays')
    
    if liste: # print whole list
        new_matrix = {}
        for key, value in config.get_element('schedule_matrix').items():
            index = weekdays.index(key)
            new_matrix[index] = value
            
        holidays = {}
        for key, value in feiertage.items():
            holidays[key.strftime('%d.%m.%Y')] = value
        return weekdays, holidays, new_matrix
    else: # print false/true
        now = dt.datetime.now()
        wd = int(now.weekday())
        hour = int(now.strftime("%H"))
        
        return schedule_matrix[weekdays[wd]][hour] or is_feiertag()