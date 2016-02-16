from time import time

from agarnet.vec import Vec
from .subscriber import Subscriber
from .drawutils import *

info_size = 14


def nick_size(cell, w):
    return max(14, w.world_to_screen_size(.3 * cell.draw_size))


class CellsDrawer(Subscriber):
    @staticmethod
    def draw(c, w, cell, pos=None, alpha=1.0):
        if not pos:
            pos = w.world_to_screen_pos(cell.pos)
        c.fill_circle(pos, w.world_to_screen_size(cell.draw_size), color=to_rgba(cell.color, min(cell.draw_alpha, alpha)))

    def on_draw_cells(self, c, w):
        # reverse to show small over large cells
        for cell in sorted(w.world.cells.values(), reverse=True):
            self.draw(c, w, cell, alpha=0.9)


class CellNames(Subscriber):
    @staticmethod
    def draw(c, w, cell, pos=None):
        if cell.name:
            if not pos:
                pos = w.world_to_screen_pos(cell.pos)
            size = nick_size(cell, w)
            c.draw_text(pos, '%s' % cell.name, align='center', outline=(BLACK, 2), size=size)

    def on_draw_cells(self, c, w):
        for cell in w.world.cells.values():
            self.draw(c, w, cell)


class RemergeTimes(Subscriber):
    def on_draw_cells(self, c, w):
        if len(w.player.own_ids) <= 1:
            return  # dead or only one cell, no re-merge time to display

        now = time()
        for cell in w.player.own_cells:
            split_for = now - cell.spawn_time
            # formula by HungryBlob
            ttr = max(30, cell.size // 5) - split_for
            if ttr < 0:
                continue
            pos = w.world_to_screen_pos(cell.pos)
            pos.isub(Vec(0, (info_size + nick_size(cell, w)) / 2))
            c.draw_text(pos, 'TTR %.1fs after %.1fs' % (ttr, split_for),
                        align='center', outline=(BLACK, 2), size=info_size)


class CellMasses(Subscriber):
    @staticmethod
    def draw(c, w, cell, pos=None):
        if cell.is_food or cell.is_ejected_mass:
            return
        text_pos = Vec(pos) if pos else w.world_to_screen_pos(cell.pos)

        # draw cell's mass
        if cell.name:
            text_pos.iadd(Vec(0, (info_size + nick_size(cell, w)) / 2))
        c.draw_text(text_pos, '%i' % cell.mass, align='center', outline=(BLACK, 2), size=info_size)

        # draw needed mass to eat it splitted
        text_pos.iadd(Vec(0, info_size))
        c.draw_text(text_pos, '(%i)' % ((cell.mass*2*1.33)-w.player.total_mass), align='center', outline=(BLACK, 2), size=info_size/1.5)

    def on_draw_cells(self, c, w):
        for cell in w.world.cells.values():
            self.draw(c, w, cell)


class CellHostility(Subscriber):
    @staticmethod
    def draw(c, w, cell, pos=None, own_min_mass=None, own_max_mass=None, alpha=1.0):
        if not w.player.is_alive:
            return  # nothing to be hostile against
        if cell.is_food or cell.is_ejected_mass:
            return  # no threat
        if cell.cid in w.player.own_ids:
            return  # own cell, also no threat lol

        if not pos:
            pos = w.world_to_screen_pos(cell.pos)
        if not own_min_mass:
            own_min_mass = min(c.mass for c in w.player.own_cells)
        if not own_max_mass:
            own_max_mass = max(c.mass for c in w.player.own_cells)

        color = YELLOW
        if cell.is_virus:
            if own_max_mass >= cell.mass * 1.33:
                color = RED
            else:
                return  # no threat, do not mark
        elif own_min_mass > cell.mass * 1.33 * 2:
            color = PURPLE
        elif own_min_mass > cell.mass * 1.33:
            color = GREEN
        elif cell.mass > own_min_mass * 1.33 * 2:
            color = RED
        elif cell.mass > own_min_mass * 1.33:
            color = ORANGE
        c.stroke_circle(pos, w.world_to_screen_size(cell.draw_size),
                        width=5, color=to_rgba(color, min(cell.draw_alpha, alpha)))

    def on_draw_cells(self, c, w):
        if not w.player.is_alive:
            return  # nothing to be hostile against

        own_min_mass = min(c.mass for c in w.player.own_cells)
        own_max_mass = max(c.mass for c in w.player.own_cells)
        for cell in w.world.cells.values():
            self.draw(c, w, cell, own_min_mass=own_min_mass, own_max_mass=own_max_mass)


class ForceFields(Subscriber):
    def on_draw_cells(self, c, w):
        if not w.player.is_alive:
            return
        split_dist = 760
        for cell in w.player.own_cells:
            pos = w.world_to_screen_pos(cell.pos)
            radius = split_dist + cell.size * .7071
            c.stroke_circle(pos, w.world_to_screen_size(radius),
                            width=3, color=to_rgba(PURPLE, min(cell.draw_alpha, 0.5)))

        if w.player.is_alive:
            own_max_size = max(c.size for c in w.player.own_cells)
            own_min_mass = max(min(c.mass for c in w.player.own_cells), own_max_size/2) # prevent confusing force fields due to many small cells
        else:  # spectating or dead, still draw some lines
            own_max_size = own_min_mass = 0

        for cell in w.world.cells.values():
            if cell.size < 60:
                continue  # cannot split
            if cell.cid in w.player.own_ids:
                continue  # own cell, not hostile
            pos = w.world_to_screen_pos(cell.pos)
            if cell.is_virus:
                if own_max_size > cell.size:  # dangerous virus
                    c.stroke_circle(pos, w.world_to_screen_size(own_max_size),
                                    width=3, color=to_rgba(RED, min(cell.draw_alpha, 0.5)))
            elif cell.mass > own_min_mass * 1.33 * 2:  # can split+kill me
                radius = max(split_dist + cell.draw_size * .7071, cell.draw_size)
                c.stroke_circle(pos, w.world_to_screen_size(radius),
                                width=3, color=to_rgba(RED, min(cell.draw_alpha, 0.5)))


class MovementLines(Subscriber):
    def on_draw_cells(self, c, w):
        for cell in w.player.own_cells:
            c.draw_line(w.world_to_screen_pos(cell.pos), w.mouse_pos,
                        width=1, color=to_rgba(BLACK, 0.3))
