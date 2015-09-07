#!/usr/bin/python3.4
import socket
import threading
import time

PORT = 55555
TIMEOUT = 2


class State():
    def __init__(self, name, x, y, server, mass):
        self.name = name
        self.x = x
        self.y = y
        self.server = server
        self.mass = mass

    @classmethod
    def from_data(cls, data):
        array = data.decode('utf8').split("|")
        if len(array) == 5:
            return cls(array[0], float(array[1]), float(array[2]), array[3], float(array[4]))
        else:
            return None

    def to_data(self):
        s = "|".join((self.name, str(self.x), str(self.y), self.server, str(self.mass)))
        return bytes(s, 'utf8')

    def __str__(self):
        return "|".join((self.name, str(self.x), str(self.y), self.server, str(self.mass)))


class Player():
    def __init__(self, address):
        self.address = address
        self.last_state = None
        self.last_state_time = None
        self.check_timeout = True
        self.online = False


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 0))  # connecting to a UDP address doesn't send packets
    return s.getsockname()[0]


class AgarioTeamer():
    def __init__(self):
        self.local_ip = get_local_ip()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.socket.bind(("", PORT))
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
        print("Local ip:", self.local_ip)
        self.team_list = dict()

        self.state_server = UDPServer(self._received_new_state, self.socket)
        self.state_server.start()

    def add_player(self, ip):
        player = Player((ip, PORT))
        player.check_timeout = False
        self.team_list[(ip, PORT)] = player

    def send_discover(self, state):
        print("Sending discover with state:", state)
        self.send_state_to(("<broadcast>", PORT), state)

    def send_state_to(self, address, state):
        self.socket.sendto(state.to_data(), address)

    def send_state_to_all(self, state):
        for address in [online for online in self.team_list if self.team_list[online].online is True]:
            self.send_state_to(address, state)

    def check_conn_timeout(self):
        for player in list(self.team_list.values()):
            diff = time.monotonic() - player.last_state_time
            if (player.last_state_time is None or diff > TIMEOUT) and player.online is True:
                if player.check_timeout:
                    print("Player", player.address, "timed out. Inactive for", diff, "seconds.")
                    del self.team_list[player.address]
                else:
                    print("Player", player.address, "marked as offline")
                    player.online = False

    def _received_new_state(self, source_addr, data):
        try:
            host_name = socket.gethostbyaddr(source_addr[0])[0]
        except socket.herror:
            host_name = source_addr[0]
        addr_tuple = (host_name, source_addr[1])
        if host_name in (self.local_ip, "127.0.0.1", "localhost", socket.gethostname()):
            pass
            print("Ignored data from own socket.")
            return
        state = State.from_data(data)
        if state is None:
            print("Received invalid data")
            return
        # print("Received new state:", source_addr, data)
        if addr_tuple not in self.team_list:
            print("Found new player:", addr_tuple)
            self.team_list[addr_tuple] = Player(addr_tuple)
        player = self.team_list[addr_tuple]
        player.last_state = state
        player.last_state_time = time.monotonic()
        player.online = True


class UDPServer(threading.Thread):
    def __init__(self, cb=None, sock=None):
        super().__init__()
        self.setDaemon(True)
        self.cb = cb
        if sock is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.socket.bind(("", PORT))
        else:
            self.socket = sock

    def run(self):
        print("Started UDP Server")
        while True:
            data, addr = self.socket.recvfrom(1024)
            if self.cb is not None:
                self.cb(addr, data)


if __name__ == "__main__":
    teamer = AgarioTeamer()
    own_state = State("test_name", 0, 0, "XCVR", 512)
    print([x for x in dir(own_state) if x not in dir(State)])
    teamer.send_discover(own_state)

    while True:
        time.sleep(1)
        teamer.check_conn_timeout()
