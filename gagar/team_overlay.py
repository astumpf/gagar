from agarnet.vec import Vec
from agarnet.utils import get_party_address

from .subscriber import Subscriber
from .drawutils import *
from .draw_cells import *
from .skins import *

TEAM_OVERLAY_PADDING = 50
INFO_SIZE = 14


class TeamOverlay(Subscriber):
    def __init__(self, tagar_client):
        self.tagar_client = tagar_client

    def is_in_screen(self, w, screen_pos, radius=0.0):
        if screen_pos.x < -radius or screen_pos.y < -radius:
            return False
        if screen_pos.x > w.win_size.x+radius or screen_pos.y > w.win_size.y+radius:
            return False
        return True

    def on_draw_cells(self, c, w):
        def nick_size(cell, w):
            return max(14, w.world_to_screen_size(.3 * cell.draw_size))

        own_min_mass = min(c.mass for c in w.player.own_cells) if w.player.is_alive else 0
        own_max_mass = max(c.mass for c in w.player.own_cells) if w.player.is_alive else 0

        # reverse to show small over large cells
        cells = [c for c in list(self.tagar_client.team_world.cells.values()) if c.cid not in self.tagar_client.player.world.cells]
        for cell in sorted(cells, reverse=True):
            pos = w.world_to_screen_pos(cell.pos)

            # don't draw cells outside of visible area
            if not self.is_in_screen(w, pos, cell.draw_size):
                continue

            # draw cell itself
            CellsDrawer.draw(c, w, cell, pos, 0.5)

            # draw cell skin
            CellSkins.draw(c, w, cell)

            # draw names
            CellNames.draw(c, w, cell, pos)

            # draw cell mass
            CellMasses.draw(c, w, cell, pos)

            # draw hostility
            CellHostility.draw(c, w, cell, pos, own_min_mass, own_max_mass, 0.5)

    def on_draw_minimap(self, c, w):
        if w.world.size:
            minimap_w = w.win_size.x / 5
            minimap_size = Vec(minimap_w, minimap_w)
            minimap_scale = minimap_size.x / w.world.size.x
            minimap_offset = w.win_size - minimap_size

            def world_to_map(world_pos):
                pos_from_top_left = world_pos - w.world.top_left
                return minimap_offset + pos_from_top_left * minimap_scale

            # draw cells
            cells = self.tagar_client.team_world.cells.copy()
            for cell in cells.values():
                if cell.cid not in w.world.cells:
                    if cell.cid in self.tagar_client.team_cids:
                        c.fill_circle(world_to_map(cell.pos),
                                      cell.size * minimap_scale,
                                      color=to_rgba(cell.color, 0.7))
                    else:
                        alpha = .66 if cell.mass > (self.tagar_client.player.total_mass * 0.66) else 0.33
                        c.stroke_circle(world_to_map(cell.pos),
                                        cell.size * minimap_scale,
                                        color=to_rgba(cell.color, alpha))

            # draw lines to team members
            if self.tagar_client.player.is_alive:
                for i, player in enumerate(list(self.tagar_client.player_list.values())):
                    if player.is_alive:
                        c.draw_line(world_to_map(w.player.center),
                                    world_to_map(Vec(player.position_x, player.position_y)),
                                    width=1, color=GREEN)

            # draw names
            for i, player in enumerate(list(self.tagar_client.player_list.values())):
                if player.is_alive:
                    c.draw_text(world_to_map(Vec(player.position_x, player.position_y)), player.nick,
                                align='center', color=WHITE, outline=(BLACK, 2), size=8)

    def on_draw_hud(self, c, w):
        c.draw_text((10, 30), 'Team', align='left', color=WHITE, outline=(BLACK, 2), size=27)

        # draw player position in main view
        for i, player in enumerate(list(self.tagar_client.player_list.values())):
            c.draw_text((10, 60 + TEAM_OVERLAY_PADDING * i), player.nick,
                        align='left', color=WHITE, outline=(BLACK, 2), size=18)

            if player.total_mass > 0:
                mass_color = GRAY
                mass_text = 'Mass: ' + str('%.2f' % player.total_mass)
            else:
                mass_text = 'Dead'
                mass_color = RED

            c.draw_text((10, 75 + TEAM_OVERLAY_PADDING * i), mass_text,
                        align='left', color=mass_color, outline=(BLACK, 2), size=12)

            c.draw_text((10, 88 + TEAM_OVERLAY_PADDING * i), '#' + player.party_token,
                        align='left', color=GRAY, outline=(BLACK, 2), size=12)

            button = Button(90, 75 - 12 + TEAM_OVERLAY_PADDING * i, 50, 25, "JOIN")
            button.id = player
            w.register_button(button)
            c.draw_button(button)

            if self.tagar_client.player.is_alive and player.is_alive:
                # draw lines to team members
                client_pos = w.world_to_screen_pos(w.player.center)
                pos = w.world_to_screen_pos(Vec(player.position_x, player.position_y))
                c.draw_line(client_pos, pos, width=2, color=GREEN)

                # TODO draw names
                text_size = 12
                border_x = border_y = text_size

                if not border_x < pos.x < w.win_size.x-border_x or not border_y < pos.y < w.win_size.x-border_x:
                    side_out = abs(pos.x/pos.y) > w.win_size.x/w.win_size.y
                    alignment = 'left' if pos.x < w.win_size.x/2 else 'right'

                    if side_out and abs(pos.x-client_pos.x) > 0.0:
                        x = min(max(pos.x, border_x), w.win_size.x-border_x)
                        pos.y -= client_pos.y
                        pos.y *= abs((x-client_pos.x)/(pos.x-client_pos.x))
                        pos.y += client_pos.y
                        pos.x = x
                    elif abs(pos.y-client_pos.y) > 0.0:
                        y = min(max(pos.y, border_y), w.win_size.y-border_y)
                        pos.x -= client_pos.x
                        pos.x *= abs((y-client_pos.y)/(pos.y-client_pos.y))
                        pos.x += client_pos.x
                        pos.y = y

                    dist = ((w.player.center.x-player.position_x)**2 + (w.player.center.y-player.position_y)**2)**0.5

                    c.draw_text(pos, "%s (%.1f / %.1f)" % (player.nick, player.total_mass, dist), align=alignment, color=WHITE, outline=(BLACK, 2), size=text_size)


    @staticmethod
    def on_button_hover(button, pos):
        button.highlight = True

    def on_button_pressed(self, button, pos):
        player = button.id
        if player.party_token == 'FFA':
            return

        print("Joining player", player.nick)
        self.tagar_client.agar_client.disconnect()
        token = player.party_token
        address = get_party_address(token)
        self.tagar_client.agar_client.connect(address, token)
