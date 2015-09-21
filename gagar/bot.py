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


class Throttle(object):
    """
    Decorator that prevents a function from being called more than once every
    time period.
    To create a function that cannot be called more than once a minute:
    @throttle(minutes=1)
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

        self.p_dict = dict()
        self.max_p = 0
        self.min_p = 0

    def on_world_update_post(self):
        thread = threading.Thread(target=self.update_potential)
        thread.start()

    def on_draw_hud(self, c, w):
        if self.max_p == self.min_p == 0:
            return

        for pos, p in self.p_dict.copy().items():
            c.set_pixel(pos, potential_to_color(p, self.max_p, self.min_p))

    @Throttle(seconds=1)
    def update_potential(self):
        self.p_dict = dict()
        for x in range(0, math.floor(self.world_viewer.win_size.x), 10):
            for y in range(0, math.floor(self.world_viewer.win_size.y), 10):
                pos = Vec(x, y)
                world_pos = self.world_viewer.screen_to_world_pos(pos)
                potential = self.potential(world_pos)
                self.p_dict[pos] = potential

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

        return min_cell_dist