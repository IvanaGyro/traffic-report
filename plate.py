import json
import sys

from openalpr import Alpr

CONFIG = '/etc/openalpr/openalpr.conf' # linux default setting
RUNTIME = '/usr/share/openalpr/runtime_data' # linux default setting

_alpr = None

def init_alpr():
    global _alpr
    do_init = False
    if _alpr is None:
        _alpr = Alpr('us', CONFIG, RUNTIME)
        do_init = True
    if not _alpr.is_loaded():
        raise Exception('Error loading OpenALPR')
    return do_init

def unload_alpr():
    if _alpr is not None:
        _alpr.unload()

def recognize(filename):
    do_init = init_alpr()
    result = _alpr.recognize_file(filename)['results']
    if do_init:
        unload_alpr()
    return format_car_plate(result[0]['plate']) if result else ''

def format_car_plate(plate):
    l = len(plate)
    if l == 5:
        if plate[:3].isnumeric():
            return f'{plate[:3]}-{plate[3:]}'
        else:
            return f'{plate[:2]}-{plate[2:]}'
    if l >= 6:
        return f'{plate[:3]}-{plate[3:]}'
    return plate
