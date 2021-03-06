from collections import deque
from time import time

from agarnet.vec import Vec

from .drawutils import *
from .subscriber import Subscriber


class SplitCounter(Subscriber):
    @staticmethod
    def on_draw_hud(c, w):
        if w.player.is_alive:
            if len(w.player.own_ids) <= 1:
                return

            c.fill_circle((w.win_size.x/2-18, 22), 18.0, color=to_rgba(LIGHT_GRAY, .8))
            c.fill_circle((w.win_size.x/2+15, 22), 15.0, color=to_rgba(GRAY, .8))
            split_text = '%d / 16' % len(w.player.own_ids)
            c.draw_text((w.win_size.x/2, 67), split_text, align='center', color=WHITE, outline=(BLACK, 3), size=30)

            now = time()
            ttr_list = []
            for cell in w.player.own_cells:
                split_for = now - cell.spawn_time

                # formula by DebugMonkey
                ttr = w.player.total_mass * 0.02 + 30 - split_for
                if ttr > 0.0:
                    ttr_list.append(ttr)

            if len(ttr_list) > 0:
                ttr_text = 'Min: %.1fs / Max: %.1fs' % (min(ttr_list), max(ttr_list))
                c.draw_text((w.win_size.x/2, 90), ttr_text, align='center', color=WHITE, outline=(BLACK, 1), size=15)


class FieldOfView(Subscriber):
    @staticmethod
    def on_draw_hud(c, w):
        if w.player.is_alive and w.screen_zoom_scale != 1.0:
            window_scale = max(w.win_size.x / 1920, w.win_size.y / 1080)
            screen_scale_no_zoom = w.player.scale * window_scale

            def screen_to_world_pos(screen_pos):
                return (screen_pos - w.screen_center) \
                    .idiv(screen_scale_no_zoom).iadd(w.world_center)

            # outline the area visible in window
            c.stroke_rect(w.world_to_screen_pos(screen_to_world_pos(Vec(0, 0))),
                          w.world_to_screen_pos(screen_to_world_pos(w.win_size)),
                          width=1, color=LIGHT_GRAY)


class Minimap(Subscriber):
    @staticmethod
    def on_draw_minimap(c, w):
        if w.world.size:
            minimap_w = w.win_size.x / 5
            minimap_size = Vec(minimap_w, minimap_w)
            minimap_scale = minimap_size.x / w.world.size.x
            minimap_offset = w.win_size - minimap_size

            def world_to_map(world_pos):
                pos_from_top_left = world_pos - w.world.top_left
                return minimap_offset + pos_from_top_left * minimap_scale

            for cell in w.world.cells.values():
                c.stroke_circle(world_to_map(cell.pos),
                                cell.size * minimap_scale,
                                color=to_rgba(cell.color, .8))


class Leaderboard(Subscriber):
    @staticmethod
    def on_draw_hud(c, w):
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
