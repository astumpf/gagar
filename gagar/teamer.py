#!/usr/bin/python3.4
import sys
import socket
from time import time, sleep
import sched
import threading

from agarnet.buffer import BufferStruct
from agarnet.dispatcher import Dispatcher
from tagar.session import Session
from tagar.player import Player
from tagar.opcodes import *

PORT = 55555
TIMEOUT = 2
UPDATE_RATE = 0.04


class Teamer:
    def __init__(self, client):
        self.client = client
        self.dispatcher = Dispatcher(packet_s2c, self)
        self.player_list = []
        self.last_world_buf = None
        self.session = None

        self.scheduler = sched.scheduler(time, sleep)
        self.scheduler.enter(UPDATE_RATE, 1, self.recv_update)
        self.scheduler.enter(UPDATE_RATE, 1, self.send_update)
        thread = threading.Thread(target=self.scheduler.run)
        thread.setDaemon(True)
        thread.start()

        self.connect('127.0.0.1', 5550, "42")

    def connect(self, addr, port, password):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, True)

        # try to connect to server
        try:
            # Connect to server and send data
            sock.connect((addr, port))

            buf = BufferStruct(opcode=100)
            buf.push_null_str16(password)
            sock.send(buf.buffer)

            # Receive data from the server and shut down
            msg = sock.recv(1024)
            buf = BufferStruct(msg)

            opcode = buf.pop_uint8()

            if opcode != 200:
                sock.close()
                return

            id = buf.pop_null_str8()

            self.session = Session(id, sock)
            print("Session started with id: ", id)

        except socket.error:
            pass
        finally:
            pass

    def disconnect(self):
        self.session.disconnect()

    def recv_update(self):
        self.scheduler.enter(UPDATE_RATE, 1, self.recv_update)

        if not self.session or not self.session.is_connected:
            return

        msg = self.session.pop_msg()
        if msg is None:
            return

        buf = BufferStruct(msg)
        while len(buf.buffer) > 0:
            self.dispatcher.dispatch(buf)

    def send_update(self):
        self.scheduler.enter(UPDATE_RATE, 1, self.send_update)

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
