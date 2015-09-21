from .subscriber import Subscriber
from .drawutils import *
from agarnet.vec import Vec
import sched
import time
import math
import threading

from datetime import datetime, timedelta
from functools import wraps


def potential_to_color(p, max_p, min_p):
    """
    Highest potential: white, lowest: black
    :param p: Potential to be transformed to a color
    :param max_p: Maximum potential in the current view
    :param min_p: Minimum potential
    :return: Returs a color representing the potential p
    """

    diff_p = max_p - min_p
    pct = (p - min_p) / diff_p

    return pct, pct, pct


def last_element(list):
    if len(list) == 1:
        return list[0]
    else:
        return last_element(list[1])


class Throttle(object):
    """
    Decorator that prevents a function from being called more than once every
    time period.
    To create a function that cannot be called more than once a minute:
    @Throttle(minutes=1)
    def my_fun():
        pass
    """

    def __init__(self, seconds=0, minutes=0, hours=0):
        self.throttle_period = timedelta(
            seconds=seconds, minutes=minutes, hours=hours
        )
        self.time_of_last_call = datetime.min

    def __call__(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            now = datetime.now()
            time_since_last_call = now - self.time_of_last_call

            if time_since_last_call > self.throttle_period:
                self.time_of_last_call = now
                return fn(*args, **kwargs)

        return wrapper


class GradientBot(Subscriber):
    def __init__(self, client, world_viewer):
        self.client = client
        self.world_viewer = world_viewer
        self.mouse_pos = Vec(0, 0)
        self.target_path = (Vec(0, 0),)

        self.p_dict = dict()
        self.max_p = 0
        self.min_p = 0

        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.current_event = None
        self.running = False

        self.iterations = 70
        self.gradient_raster = 30

    def toggle_bot(self):
        if not self.running:
            self.start_bot()
        else:
            self.stop_bot()

    def start_bot(self):
        print("Bot started")
        self.running = True
        self.current_event = self.scheduler.enter(0.01, 1, self.main_loop)
        thread = threading.Thread(target=self.scheduler.run)
        thread.setDaemon(True)
        thread.start()

    def stop_bot(self):
        print("Bot stopped")
        self.running = False
        self.scheduler.cancel(self.current_event)

    def main_loop(self):
        if self.client.player.is_alive:
            current_pos = self.world_viewer.player.center
            self.target_path = self.calc_next_target(current_pos, self.iterations)
            next_target = last_element(self.target_path)
            self.client.send_target(next_target.x, next_target.y)
        self.current_event = self.scheduler.enter(0.01, 1, self.main_loop)

    def calc_next_target(self, current_pos, iterations=1):
        directions = (Vec(0, 1), Vec(0, -1), Vec(1, 0), Vec(-1, 0))
        possible_positions = [current_pos + direction for direction in directions]
        result = sorted(possible_positions, key=self.potential)[0]
        if iterations == 1:
            return result,
        else:
            iterations -= 1
            return result, self.calc_next_target(result, iterations)

    def on_world_update_post(self):
        pass

    def on_draw_hud(self, c, w):
        self.update_potential()
        if self.client.player.is_alive:
            self.draw_target_path(c, self.target_path)

        if self.max_p == self.min_p == 0:
            return
        for pos, p in self.p_dict.copy().items():
            c.set_pixel(w.world_to_screen_pos(pos), potential_to_color(p, self.max_p, self.min_p))

        p = self.potential(self.mouse_pos)
        text_pos = Vec(self.world_viewer.win_size.x / 2, self.world_viewer.win_size.y-10)
        c.draw_text(text_pos, "Potential: " + str(math.floor(p)),
                    anchor_x='center', anchor_y='center', color=WHITE, outline=(BLACK, 2), size=18)

    def on_mouse_moved(self, pos, pos_world):
        self.mouse_pos = pos_world

    def draw_target_path(self, c, path):
        # print("Drawing path:", path)
        if len(path) > 0:
            c.set_pixel(self.world_viewer.world_to_screen_pos(path[0]), RED)
            if len(path) > 1:
                self.draw_target_path(c, path[1])

    @Throttle(seconds=1)
    def update_potential(self):
        self.p_dict = dict()
        for x in range(0, math.floor(self.world_viewer.win_size.x), self.gradient_raster):
            for y in range(0, math.floor(self.world_viewer.win_size.y), self.gradient_raster):
                pos = Vec(x, y)
                world_pos = self.world_viewer.screen_to_world_pos(pos)
                potential = self.potential(world_pos)
                self.p_dict[world_pos] = potential

        self.max_p = max(self.p_dict.values())
        self.min_p = min(self.p_dict.values())

    def potential(self, pos):
        h = (self.food_potential,)
        p = 0

        for f in h:
            p += f(pos)

        return p

    def food_potential(self, pos):
        min_cell_dist = 99999
        for cell in list(self.world_viewer.world.cells.values()):
            if cell.is_food:
                dist = abs((pos - cell.pos).len())
                if dist < min_cell_dist:
                    min_cell_dist = dist

        if min_cell_dist == 99999:
            min_cell_dist = 0

        factor = 1

        return factor * min_cell_dist

    def enemy_potential(self, pos):
        p = 0
        factor = 1

        if self.client.player.is_alive:
            own_max_mass = max(c.mass for c in self.world_viewer.player.own_cells)
        else:
            own_max_mass = 0
        for cell in list(self.world_viewer.world.cells.values()):
            dist = abs((pos - cell.pos).len())
            if cell.is_food or cell.is_ejected_mass:
                continue  # no threat
            if cell.cid in self.world_viewer.player.own_ids:
                continue  # own cell, also no threat lol
            if cell.is_virus:
                if own_max_mass > cell.mass:
                    continue
                    # p += cell.mass / (dist ** 2)
                else:
                    continue  # no threat, do not mark
            else:
                p += 1 /dist
        return p
