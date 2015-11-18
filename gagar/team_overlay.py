from agarnet.vec import Vec
from agarnet.utils import get_party_address

from .drawutils import *
from .subscriber import Subscriber

TEAM_OVERLAY_PADDING = 50
INFO_SIZE = 14


class TeamOverlay(Subscriber):
    def __init__(self, tagar_client):
        self.tagar_client = tagar_client

    def on_draw_cells(self, c, w):
        def nick_size(cell, w):
            return max(14, w.world_to_screen_size(.3 * cell.draw_size))

        # reverse to show small over large cells
        cells = [c for c in list(self.tagar_client.team_world.cells.values()) if c.cid not in self.tagar_client.player.world.cells]
        for cell in sorted(cells, reverse=True):
            pos = w.world_to_screen_pos(cell.pos)

            # draw cell itself
            c.fill_circle(pos, w.world_to_screen_size(cell.draw_size),
                          color=to_rgba(cell.color, .5))

            if cell.is_food or cell.is_ejected_mass:
                continue

            # draw names
            if cell.name:
                size = nick_size(cell, w)
                c.draw_text(pos, '%s' % cell.name,
                            align='center', outline=(BLACK, 2), size=size)
            # draw cell mass
            pos.iadd(Vec(0, (INFO_SIZE + nick_size(cell, w)) / 2))
            c.draw_text(pos, '%i' % cell.mass,
                    align='center', outline=(BLACK, 2), size=INFO_SIZE)

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
                    alpha = .66 if cell.mass > (self.tagar_client.player.total_mass * 0.66) else 0.33
                    c.stroke_circle(world_to_map(cell.pos),
                                    cell.size * minimap_scale,
                                    color=to_rgba(cell.color, alpha))

            # draw lines to team members
            for i, player in enumerate(list(self.tagar_client.player_list.values())):
                if self.tagar_client.player.is_alive and player.is_alive:
                    c.draw_line(world_to_map(w.player.center),
                                world_to_map(Vec(player.position_x, player.position_y)),
                                width=1, color=GREEN)

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

            # draw lines to team members
            if self.tagar_client.player.is_alive and player.is_alive:
                c.draw_line(w.world_to_screen_pos(w.player.center),
                            w.world_to_screen_pos(Vec(player.position_x, player.position_y)),
                            width=2, color=GREEN)

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