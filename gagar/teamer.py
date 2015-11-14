#!/usr/bin/python3.4
import sys
import configparser
import socket
from time import time, sleep
import sched
import threading
import hashlib
import random

from agarnet.buffer import BufferStruct
from agarnet.dispatcher import Dispatcher
from tagar.session import Session
from tagar.player import Player
from tagar.opcodes import *


class Teamer:
    def __init__(self, client):
        self.client = client
        self.dispatcher = Dispatcher(packet_s2c, self)
        self.player_list = []
        self.last_world_buf = None
        self.session = None

        config = configparser.ConfigParser({'address': 'localhost',
                                            'port': '5000',
                                            'password': '',
                                            'update_rate': '0.1'})
        config.read('tagar_client.cfg')

        self.update_rate = config.getfloat('Settings', 'update_rate')

        self.scheduler = sched.scheduler(time, sleep)
        self.scheduler.enter(self.update_rate, 1, self.recv_update)
        self.scheduler.enter(self.update_rate, 1, self.send_update)
        thread = threading.Thread(target=self.scheduler.run)
        thread.setDaemon(True)
        thread.start()

        address = config.get('Server', 'address')
        port = config.getint('Server', 'port')
        password = config.get('Server', 'password')

        self.connect(address, port, password)

    def connect(self, addr, port, password):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, True)

        # try to connect to server
        try:
            # Connect to server and send data
            sock.connect((addr, port))

            buf = BufferStruct(opcode=100)

            # create challenge
            rand = random.randint(1, 254)
            m = hashlib.md5()
            m.update(password.encode('utf-16'))
            m.update(str(rand).encode('utf-8'))

            # send login challenge
            buf.push_null_str8(m.hexdigest())
            buf.push_uint8(rand)
            sock.send(buf.buffer)

            # Receive data from the server
            msg = sock.recv(1024)
            if msg is None or len(msg) == 0:
                print("Connection to team server rejected!")
                return

            buf = BufferStruct(msg)

            opcode = buf.pop_uint8()

            if opcode != 200:
                sock.close()
                return

            print("Connected to tagar server: %s:%d" % (addr, port))

            self.session = Session(buf.pop_null_str8(), sock)

        except socket.error:
            pass
        finally:
            pass

    def disconnect(self):
        self.session.disconnect()

    def recv_update(self):
        self.scheduler.enter(self.update_rate, 1, self.recv_update)

        if not self.session or not self.session.is_connected:
            return

        while 1:
            msg = self.session.pop_msg()
            if msg is None:
                return

            buf = BufferStruct(msg)
            while len(buf.buffer) > 0:
                self.dispatcher.dispatch(buf)

    def send_update(self):
        self.scheduler.enter(self.update_rate, 1, self.send_update)

        if not self.session or not self.session.is_connected:
            return

        # collect player info
        p = Player(self.session)
        p.nick = self.client.player.nick
        p.position_x, p.position_y = self.client.player.center
        p.mass = self.client.player.total_mass
        p.is_alive = self.client.player.is_alive
        p.party_token = self.client.server_token if len(self.client.server_token) == 5 else 'FFA'

        # send update
        try:
            buf = BufferStruct(opcode=110)
            p.pack_player_update(buf)
            self.session.sendall(buf.buffer)
        except socket.error:
            self.disconnect()

    def parse_player_list_update(self, buf):
        list_length = buf.pop_uint32()

        self.player_list = []
        for i in range(0, list_length):
            p = Player()
            p.parse_player_update(buf)
            if str(self.session.id) != p.id:
                self.player_list.append(p)
