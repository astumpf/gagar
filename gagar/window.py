import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

from agarnet.vec import Vec
from .drawutils import *
import time
import threading


class WorldViewer(object):
    """
    Draws one world and handles keys/mouse.
    Does not poll for events itself.
    Calls input_subscriber.on_{key_pressed|mouse_moved}() methods on key/mouse input.
    Calls draw_subscriber.on_draw_{background|cells|hud}() methods when drawing.
    """

    INFO_SIZE = 300

    MIN_SCREEN_SCALE = 0.075
    MAX_SCREEN_SCALE = 1

    def __init__(self, world):
        self.world = world
        self.player = None  # the focused player, or None to show full world

        # the class instance on which to call on_key_pressed and on_mouse_moved
        self.input_subscriber = None
        # same for draw_background, draw_cells, draw_hud
        self.draw_subscriber = None
        self.button_subscriber = None

        self.buttons = []

        self.win_size = Vec(1000, 1000 * 9 / 16)
        self.screen_center = self.win_size / 2
        self.screen_scale = 1
        self.screen_zoom_scale = 1
        self.world_center = Vec(0, 0)
        self.mouse_pos = Vec(0, 0)

        window = Gtk.Window()
        window.set_title('agar.io')
        window.set_default_size(self.win_size.x, self.win_size.y)
        window.connect('delete-event', Gtk.main_quit)

        self.drawing_area = Gtk.DrawingArea()
        window.add(self.drawing_area)

        window.set_events(Gdk.EventMask.KEY_PRESS_MASK |
                          Gdk.EventMask.POINTER_MOTION_MASK |
                          Gdk.EventMask.BUTTON_PRESS_MASK |
                          Gdk.EventMask.SCROLL_MASK)
        window.connect('key-press-event', self.key_pressed)
        window.connect('motion-notify-event', self.mouse_moved)
        window.connect('button-press-event', self.mouse_pressed)
        window.connect('scroll-event', self.mouse_wheel_moved)

        self.drawing_area.connect('draw', self.draw)

        window.show_all()
        #draw_thread = threading.Thread(target=self.draw_loop)
        #draw_thread.daemon = True
        #draw_thread.start()

    def draw_loop(self):
        while True:
            self.drawing_area.queue_draw()
            time.sleep(0.003)

    def focus_player(self, player):
        """Follow this client regarding center and zoom."""
        self.player = player
        self.world = player.world

    def show_full_world(self, world=None):
        """
        Show the full world view instead of one client.
        :param world: optionally update the drawn world
        """
        self.player = None
        if world:
            self.world = world

    def key_pressed(self, _, event):
        """Called by GTK. Set input_subscriber to handle this."""
        if not self.input_subscriber:
            return
        val = event.keyval
        try:
            char = chr(val)
        except ValueError:
            char = ''
        self.input_subscriber.on_key_pressed(val=val, char=char)

    def mouse_moved(self, _, event):
        """Called by GTK. Set input_subscriber to handle this."""
        if not self.input_subscriber:
            return
        self.mouse_pos = Vec(event.x, event.y)
        pos_world = self.screen_to_world_pos(self.mouse_pos)
        self.input_subscriber.on_mouse_moved(pos=self.mouse_pos, pos_world=pos_world)

    def mouse_pressed(self, _, event):
        """Called by GTK. Set input_subscriber to handle this."""
        if not self.input_subscriber:
            return
        self.input_subscriber.on_mouse_pressed(button=event.button)
        if event.button == 1:
            for button in self.buttons:
                if button.contains_point(self.mouse_pos):
                    self.button_subscriber.on_button_pressed(button, self.mouse_pos)

    def mouse_wheel_moved(self, _, event):
        """Called by GTK. Set input_subscriber to handle this."""
        if event.direction == Gdk.ScrollDirection.UP and self.screen_zoom_scale < self.MAX_SCREEN_SCALE:
            self.screen_zoom_scale = min(self.screen_zoom_scale * 1.5, self.MAX_SCREEN_SCALE)
        if event.direction == Gdk.ScrollDirection.DOWN and self.screen_zoom_scale > self.MIN_SCREEN_SCALE:
            self.screen_zoom_scale = max(self.screen_zoom_scale * 0.75, self.MIN_SCREEN_SCALE)

    def register_button(self, button):
        self.buttons.append(button)
        if button.contains_point(self.mouse_pos):
            self.button_subscriber.on_button_hover(button, self.mouse_pos)

    def world_to_screen_pos(self, world_pos):
        return (world_pos - self.world_center) \
            .imul(self.screen_scale).iadd(self.screen_center)

    def screen_to_world_pos(self, screen_pos):
        return (screen_pos - self.screen_center) \
            .idiv(self.screen_scale).iadd(self.world_center)

    def world_to_screen_size(self, world_size):
        return world_size * self.screen_scale

    def recalculate(self):
        alloc = self.drawing_area.get_allocation()
        self.win_size.set(alloc.width, alloc.height)
        self.screen_center = self.win_size / 2
        if self.player:  # any client is focused
            # if self.player.is_alive or (self.player.center.x == 0 and self.player.center.y == 0) or not self.player.scale == 1.0: # HACK due to bug: player scale is sometimes wrong (sent by server?) in spectate mode
            window_scale = max(self.win_size.x / 1920, self.win_size.y / 1080)
            new_screen_scale = self.player.scale * window_scale * self.screen_zoom_scale
            self.screen_scale = lerp_smoothing(self.screen_scale, new_screen_scale, 0.1, 0.0001)

            smoothing_factor = 0.1
            if self.player.is_alive:
                smoothing_factor = 0.3

            self.world_center.x = lerp_smoothing(self.world_center.x, self.player.center.x, smoothing_factor, 0.01)
            self.world_center.y = lerp_smoothing(self.world_center.y, self.player.center.y, smoothing_factor, 0.01)

            self.world = self.player.world
        elif self.world.size:
            new_screen_scale = min(self.win_size.x / self.world.size.x, self.win_size.y / self.world.size.y) * self.screen_zoom_scale
            self.screen_scale = lerp_smoothing(self.screen_scale, new_screen_scale, 0.1, 0.0001)
            self.world_center = self.world.center
        else:
            # happens when the window gets drawn before the world got updated
            self.screen_scale = self.screen_zoom_scale
            self.world_center = Vec(0, 0)

    def draw(self, widget, cairo_context):
        self.buttons = []
        c = Canvas(cairo_context)
        if self.draw_subscriber:
            self.recalculate()
            self.draw_subscriber.on_draw_background(c, self)
            self.draw_subscriber.on_draw_cells(c, self)
            self.draw_minimap_backgound(c, self)
            self.draw_subscriber.on_draw_minimap(c, self)
            self.draw_subscriber.on_draw_hud(c, self)

    def draw_minimap_backgound(self, c, w):
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


class Timer:
    measurements = dict()

    def __init__(self):
        self.start_time = None
        self.counter = 1

    def start(self):
        self.start_time = time.monotonic()

    def stop(self):
        duration = time.monotonic() - self.start_time
        print("Measurement", self.counter, ":", duration)
        if self.counter in Timer.measurements:
            Timer.measurements[self.counter].append(duration)
        else:
            Timer.measurements[self.counter] = [duration]
        self.counter += 1

    def __del__(self):
        print("Timer Statistics:")
        for m in Timer.measurements:
            print("Measurement", m, "count:", len(Timer.measurements[m]), "average:",
                  sum(Timer.measurements[m]) / len(Timer.measurements[m]), "max:", max(Timer.measurements[m]))
