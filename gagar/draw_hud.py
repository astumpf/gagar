from collections import deque
from time import time, sleep, monotonic
import sched
import threading
from agarnet.utils import get_party_address

from agarnet.vec import Vec

from .drawutils import *
from .subscriber import Subscriber
from .teamer import AgarioTeamer, State, Player

TEAM_UPDATE_RATE = 0.1
TEAM_OVERLAY_PADDING = 50


class TeamOverlay(Subscriber):
    def __init__(self, client):
        self.client = client

        self.teamer = AgarioTeamer()
        self.state = None

        self.scheduler = sched.scheduler(time, sleep)
        self.scheduler.enter(TEAM_UPDATE_RATE, 1, self.send_state)
        thread = threading.Thread(target=self.scheduler.run)
        thread.setDaemon(True)
        thread.start()

        #self._test()

    def get_state(self, world):
        x, y = world.player.center
        token = self.client.server_token if len(self.client.server_token) == 5 else 'FFA'
        state = State(world.player.nick, x, y, token, world.player.total_mass)

        return state

    def send_state(self):
        # print("Sending current state!")
        if len(self.teamer.team_list) > 0 and self.state is not None:
            self.teamer.send_state_to_all(self.state)
        self.scheduler.enter(TEAM_UPDATE_RATE, 1, self.send_state)

    def on_draw_hud(self, c, w):
        state = self.get_state(w)
        if self.state is None:
            self.teamer.send_discover(state)
        self.state = state

        c.draw_text((10, 30), 'Team',
                    align='left', color=WHITE, outline=(BLACK, 2), size=27)

        for i, peer in enumerate(self.teamer.team_list.values()):
            c.draw_text((10, 60 + TEAM_OVERLAY_PADDING * i), peer.last_state.name,
                        align='left', color=WHITE, outline=(BLACK, 2), size=18)
            if peer.last_state.mass > 0:
                mass_color = GRAY
                mass_text = 'Mass: ' + str(peer.last_state.mass)
            else:
                mass_text = 'Dead'
                mass_color = RED
            c.draw_text((10, 75 + TEAM_OVERLAY_PADDING * i), mass_text,
                        align='left', color=mass_color, outline=(BLACK, 2), size=12)

            c.draw_text((10, 88 + TEAM_OVERLAY_PADDING * i), '#' + peer.last_state.server,
                        align='left', color=GRAY, outline=(BLACK, 2), size=12)
            button = Button(90, 75 - 12 + TEAM_OVERLAY_PADDING * i, 50, 25, "JOIN")
            button.id = peer
            w.register_button(button)
            c.draw_button(button)
            if self.client.player.is_alive:
                c.draw_line(w.world_to_screen_pos(w.player.center),
                            w.world_to_screen_pos(Vec(peer.last_state.x, peer.last_state.y)),
                            width=2, color=GREEN)

        self.teamer.check_conn_timeout()

        # print('Nick:', w.player.nick, 'Current mass:', w.player.total_mass, 'Pos:', x, '|', y, 'Token:', self.client.server_token)

    def on_button_hover(self, button, pos):
        button.highlight = True

    def on_button_pressed(self, button, pos):
        player = button.id
        print("Joining player", player.last_state.name)
        self.client.disconnect()
        token = player.last_state.server
        address = get_party_address(token)
        self.client.connect(address, token)

    def _test(self):
        state1 = State("Peter", 100, 200, "R38BQ", 0)
        player1 = Player(("192.168.2.1", 55555))
        player1.check_timeout = False
        player1.last_state = state1
        player1.last_state_time = monotonic()
        player1.online = True

        self.teamer.team_list[("192.168.2.1", 55555)] = player1

        state2 = State("Hans", -100, -200, "TTTTT", 1200)
        player2 = Player(("192.168.2.2", 55555))
        player2.check_timeout = False
        player2.last_state = state2
        player2.last_state_time = monotonic()
        player2.online = True

        self.teamer.team_list[("192.168.2.2", 55555)] = player2


class Minimap(Subscriber):
    def on_draw_hud(self, c, w):
        if w.world.size:
            minimap_w = w.win_size.x / 5
            minimap_size = Vec(minimap_w, minimap_w)
            minimap_scale = minimap_size.x / w.world.size.x
            minimap_offset = w.win_size - minimap_size

            def world_to_map(world_pos):
                pos_from_top_left = world_pos - w.world.top_left
                return minimap_offset + pos_from_top_left * minimap_scale

            # minimap background
            c.fill_rect(minimap_offset, size=minimap_size,
                        color=to_rgba(DARK_GRAY, .8))

            # outline the area visible in window
            c.stroke_rect(world_to_map(w.screen_to_world_pos(Vec(0, 0))),
                          world_to_map(w.screen_to_world_pos(w.win_size)),
                          width=1, color=BLACK)

            for cell in w.world.cells.values():
                c.stroke_circle(world_to_map(cell.pos),
                                cell.size * minimap_scale,
                                color=to_rgba(cell.color, .8))


class Leaderboard(Subscriber):
    def on_draw_hud(self, c, w):
        c.draw_text((w.win_size.x - 10, 30), 'Leaderboard',
                    align='right', color=WHITE, outline=(BLACK, 2), size=27)

        player_cid = min(c.cid for c in w.player.own_cells) \
            if w.player and w.player.own_ids else -1

        for rank, (cid, name) in enumerate(w.world.leaderboard_names):
            rank += 1  # start at rank 1
            name = name or 'An unnamed cell'
            text = '%s (%i)' % (name, rank)
            if cid == player_cid:
                color = RED
            elif cid in w.world.cells:
                color = LIGHT_GRAY
            else:
                color = WHITE
            c.draw_text((w.win_size.x - 10, 40 + 23 * rank), text,
                        align='right', color=color, outline=(BLACK, 2), size=18)


class MassGraph(Subscriber):
    def __init__(self, client):
        self.client = client
        self.graph = []

    def on_respawn(self):
        self.graph.clear()

    def on_world_update_post(self):
        player = self.client.player
        if not player.is_alive:
            return
        sample = (
            player.total_mass,
            sorted((c.cid, c.mass) for c in player.own_cells)
        )
        self.graph.append(sample)

    def on_draw_hud(self, c, w):
        if not self.graph:
            return
        scale_x = w.INFO_SIZE / len(self.graph)
        scale_y = w.INFO_SIZE / (max(self.graph)[0] or 10)
        points = [(w.INFO_SIZE, 0), (0, 0)]
        for i, (total_mass, masses) in enumerate(reversed(self.graph)):
            points.append((i * scale_x, total_mass * scale_y))
        c.fill_polygon(*points, color=to_rgba(BLUE, .3))


class ExperienceMeter(Subscriber):
    def __init__(self):
        self.level = 0
        self.current_xp = 0
        self.next_xp = 0

    def on_experience_info(self, level, current_xp, next_xp):
        self.level = level
        self.current_xp = current_xp
        self.next_xp = next_xp

    def on_draw_hud(self, c, w):
        if self.level == 0:
            return
        if w.player.is_alive:
            return
        bar_width = 200
        level_height = 30
        x = (w.win_size.x - bar_width - level_height) / 2
        # bar progress
        bar_progress = bar_width * self.current_xp / self.next_xp
        c.fill_rect((x, 0), size=(bar_progress, level_height),
                    color=to_rgba(GREEN, .3))
        # bar outline
        c.stroke_rect((x, 0), size=(bar_width, level_height),
                      width=2, color=to_rgba(GREEN, .7))
        # current level
        radius = level_height / 2
        center = (x + bar_width + radius, radius)
        c.fill_circle(center, radius, color=to_rgba(YELLOW, .8))
        c.draw_text(center, '%s' % self.level,
                    align='center', color=BLACK, size=radius)


class FpsMeter(Subscriber):
    def __init__(self, queue_len):
        self.draw_last = self.world_last = time()
        self.draw_times = deque([0] * queue_len, queue_len)
        self.world_times = deque([0] * queue_len, queue_len)

    def on_world_update_post(self):
        now = time()
        dt = now - self.world_last
        self.world_last = now
        self.world_times.appendleft(dt)

    def on_draw_hud(self, c, w):
        for i, t in enumerate(self.draw_times):
            c.draw_line(w.win_size - Vec(4 * i - 2, 0), relative=(0, -t * 1000),
                        width=2, color=to_rgba(RED, .3))

        for i, t in enumerate(self.world_times):
            c.draw_line(w.win_size - Vec(4 * i, 0), relative=(0, -t * 1000),
                        width=2, color=to_rgba(YELLOW, .3))

        # 25, 30, 60 FPS marks
        graph_width = 4 * len(self.draw_times)
        for fps, color in ((25, ORANGE), (30, GREEN), (60, BLUE)):
            c.draw_line(w.win_size - Vec(graph_width, 1000 / fps),
                        relative=(graph_width, 0),
                        width=.5, color=to_rgba(color, .3))

        now = time()
        dt = now - self.draw_last
        self.draw_last = now
        self.draw_times.appendleft(dt)
