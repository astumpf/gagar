import io
from threading import Thread
import urllib.request

import cairo

from agarnet.utils import default_headers, special_names
from .drawutils import TWOPI
from .subscriber import Subscriber


skin_cache = {}  # raw PNG data
skin_surface_cache = {}  # images in cairo format


def get_skin(name):
    if name not in skin_cache:
        # load in separate thread, return None for now
        skin_cache[name] = None

        def loader():
            try:
                if name[0] is '%': # new gen skins from official agario server
                    skin_url = 'http://agar.io/skins/premium/%s.png' % urllib.request.quote(name[1].upper() + name[2:])
                elif name in special_names: # old default skins from agario server
                    skin_url = 'http://agar.io/skins/%s.png' % urllib.request.quote(name)
                    #TODO: some premium skins have different url
                else: # try agariomods
                    skin_url = 'http://skins.agariomods.com/i/c/%s.png' % urllib.request.quote(name + " (Custom)")
                opener = urllib.request.build_opener()
                opener.addheaders = default_headers

                skin_cache[name] = opener.open(skin_url).read()
            except UnicodeEncodeError:  # tried lookup invalid chars
                pass
            except urllib.error.HTTPError as e:
                #print("Error while loading skin from: " + skin_url)
                #print(e)
                pass

        t = Thread(target=loader)
        t.setDaemon(True)
        t.start()
    return skin_cache[name]


class CellSkins(Subscriber):
    @staticmethod
    def draw(c, w, cell):
        c = c._cairo_context

        if cell.skin:
            name = cell.skin
        else:
            name = cell.name

        if not name:
            return

        name = name.lower()

        skin_data = get_skin(name)

        if not skin_data:  # image is still being loaded or not available
            return  # TODO fancy loading circle animation
        if name not in skin_surface_cache:
            skin_surface_cache[name] = cairo.ImageSurface.create_from_png(io.BytesIO(skin_data))

        skin_surface = skin_surface_cache[name]
        skin_radius = skin_surface.get_width() / 2
        try:
            c.save()
            c.translate(*w.world_to_screen_pos(cell.pos))
            scale = w.world_to_screen_size(cell.draw_size / skin_radius)
            c.scale(scale, scale)
            c.translate(-skin_radius, -skin_radius)
            c.set_source_surface(skin_surface, 0, 0)
            c.new_sub_path()
            c.arc(skin_radius, skin_radius, skin_radius, 0, TWOPI)
            c.fill()
            c.restore()
        except SystemError:
            print("Error while drawing skin: " + name)
            pass

    def on_draw_cells(self, c, w):
        for cell in w.world.cells.values():
            self.draw(c, w, cell)
