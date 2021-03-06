import array
import os
import socket
import struct
from contextlib import closing
from datetime import datetime
from os.path import dirname
from subprocess import Popen

from .lib.appdirs import user_log_dir
from .messages import hash_message_dict, symbol_message_dict, Slice
from .settings import read_configuration, fdmprinterfile

# _exec_file = '/Applications/Ultimaker Cura.app/Contents/MacOS/CuraEngine'
# _settings_file = '/Applications/Ultimaker Cura.app/Contents/MacOS/resources/definitions/fdmprinter.def.json'

TIME_KEYS = ['float time_none', 'time_inset_0', 'time_inset_x', 'time_skin', 'time_support',
             'time_skirt =', 'time_infill', 'time_support_infill', 'time_travel', 'time_retract',
             'time_support_interface']

engine_log_file = os.path.join(user_log_dir('FusedCura', 'nraynaud'), 'engine.log')
os.makedirs(dirname(engine_log_file), exist_ok=True)
print(engine_log_file)

_SIGNATURE = 0x2BAD << 16 | 1 << 8
_CLOSE_SOCKET = 0xf0f0f0f0


def recvall(sock, n):
    # Helper function to recv n bytes or return None if EOF is hit
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data


def run_engine(slice_message: Slice, event_handler, child_started_handler=None, keep_alive_handler=None):
    with open(engine_log_file, 'a+') as log_file:
        print(datetime.now(), file=log_file, flush=True)
        encoded_message = Slice.dumps(slice_message)
        config = read_configuration()
        print(dict(config), file=log_file, flush=True)
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as server_socket:
            server_socket.bind(('127.0.0.1', 0))
            server_socket.listen(5)
            name = server_socket.getsockname()
            extra_params = {}
            if os.name == 'nt':
                from subprocess import STARTUPINFO, STARTF_USESHOWWINDOW
                info = STARTUPINFO()
                info.dwFlags |= STARTF_USESHOWWINDOW
                extra_params['startupinfo'] = info
            cmd = ' '.join(['"' + config['curaengine'] + '"', 'connect', "%s:%s" % name, '-j',
                            '"' + fdmprinterfile + '"'])
            print(cmd, file=log_file, flush=True)
            child_process = Popen(cmd, stdout=log_file, stderr=log_file, **extra_params, shell=True)
            if child_started_handler:
                child_started_handler(child_process)
            try:
                print(child_process, file=log_file, flush=True)
                print(child_process.poll(), file=log_file, flush=True)
                (client_socket, address) = server_socket.accept()
                client_socket.send(struct.pack("I", socket.htonl(_SIGNATURE)))
                client_socket.send(struct.pack("!I", len(encoded_message)))
                client_socket.send(struct.pack("!I", symbol_message_dict['cura.proto.Slice'].hash))
                client_socket.send(encoded_message)
                while 1:
                    process = client_socket.recv(4)
                    if len(process) == 4:
                        unpacked = struct.unpack('>I', process)[0]
                        if unpacked == 0:
                            if keep_alive_handler:
                                keep_alive_handler()
                            continue
                        if unpacked == _CLOSE_SOCKET:
                            print('_CLOSE_SOCKET')
                            return
                        if unpacked == _SIGNATURE:
                            size = struct.unpack('>I', client_socket.recv(4))[0]
                            type_id = struct.unpack('>I', client_socket.recv(4))[0]
                            type_def = hash_message_dict[type_id]
                            res3 = recvall(client_socket, size) if size else b''
                            event_handler(res3, type_def)
                            continue
                        break
                    else:
                        break
            finally:
                print(child_process.communicate(), file=log_file, flush=True)


def _2_to_3(point2d_array, height):
    for i in range(len(point2d_array) // 2 * 3):
        remainder = i % 3
        if remainder == 2:
            yield (height)
        else:
            yield (point2d_array[i // 3 * 2 + remainder])


def parse_segment(segment, height):
    floats = array.array('f', segment.points)
    if segment.point_type == 0:
        return _2_to_3(floats, height / 1000)
    else:
        return floats
