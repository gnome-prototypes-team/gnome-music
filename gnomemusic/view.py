# Copyright (c) 2013 Vadim Rutkovsky <vrutkovs@redhat.com>
# Copyright (c) 2013 Eslam Mostafa <cseslam@gmail.com>
# Copyright (c) 2013 Sai Suman Prayaga <suman.sai14@gmail.com>
# Copyright (c) 2013 Arnel A. Borja <kyoushuu@yahoo.com>
# Copyright (c) 2013 Shivani Poddar <shivani.poddar92@gmail.com>
# Copyright (c) 2013 Seif Lotfy <seif@lotfy.com>
# Copyright (c) 2013 Giovanni Campagna <scampa.giovanni@gmail.com>
# Copyright (c) 2013 Jackson Isaac <jacksonisaac2008@gmail.com>
# Copyright (c) 2013 Guillaume Quintard <guillaume.quintard@gmail.com>
#
# GNOME Music is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# GNOME Music is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with GNOME Music; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# The GNOME Music authors hereby grant permission for non-GPL compatible
# GStreamer plugins to be used and distributed together with GStreamer
# and GNOME Music.  This permission is above and beyond the permissions
# granted by the GPL license by which GNOME Music is covered.  If you
# modify this code, you may extend this exception to your version of the
# code, but you are not obligated to do so.  If you do not wish to do so,
# delete this exception statement from your version.


from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gd
from gi.repository import Grl
from gi.repository import Pango
from gi.repository import GLib
from gi.repository import GdkPixbuf
from gi.repository import Tracker

from gettext import gettext as _, ngettext
from gnomemusic.grilo import grilo
from gnomemusic.query import Query
from gnomemusic.toolbar import ToolbarState
import gnomemusic.widgets as Widgets
from gnomemusic.playlists import Playlists
from gnomemusic.albumArtCache import AlbumArtCache as albumArtCache
from gnomemusic import log
import logging
logger = logging.getLogger(__name__)

try:
    tracker = Tracker.SparqlConnection.get(None)
except Exception as e:
    from sys import exit
    logger.error("Cannot connect to tracker, error '%s'\Exiting" % str(e))
    exit(1)

playlists = Playlists.get_default()


class ViewContainer(Gtk.Stack):
    nowPlayingIconName = 'media-playback-start-symbolic'
    errorIconName = 'dialog-error-symbolic'
    starIconName = 'starred-symbolic'

    @log
    def __init__(self, name, title, window, view_type, use_sidebar=False):
        Gtk.Stack.__init__(self,
                           transition_type=Gtk.StackTransitionType.CROSSFADE)
        self._grid = Gtk.Grid(orientation=Gtk.Orientation.HORIZONTAL)
        self._iconWidth = 128
        self._iconHeight = 128
        self._offset = 0
        self._adjustmentValueId = 0
        self._adjustmentChangedId = 0
        self._scrollbarVisibleId = 0
        self.old_vsbl_range = None
        self._model = Gtk.ListStore(
            GObject.TYPE_STRING,
            GObject.TYPE_STRING,
            GObject.TYPE_STRING,
            GObject.TYPE_STRING,
            GdkPixbuf.Pixbuf,
            GObject.TYPE_OBJECT,
            GObject.TYPE_BOOLEAN,
            GObject.TYPE_INT,
            GObject.TYPE_STRING,
            GObject.TYPE_BOOLEAN,
            GObject.TYPE_BOOLEAN
        )
        self.view = Gd.MainView(
            shadow_type=Gtk.ShadowType.NONE
        )
        self.view.set_view_type(view_type)
        self.view.set_model(self._model)
        self.vadjustment = self.view.get_vadjustment()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.pack_start(self.view, True, True, 0)
        if use_sidebar:
            self.stack = Gtk.Stack(
                transition_type=Gtk.StackTransitionType.SLIDE_RIGHT,
            )
            dummy = Gtk.Frame(visible=False)
            self.stack.add_named(dummy, 'dummy')
            self.stack.add_named(box, 'sidebar')
            self.stack.set_visible_child_name('dummy')
            self._grid.add(self.stack)
        else:
            self._grid.add(box)

        self.view.connect('item-activated', self._on_item_activated)
        self.view.connect('selection-mode-request', self._on_selection_mode_request)
        self._cursor = None
        self.window = window
        self.header_bar = window.toolbar
        self.selection_toolbar = window.selection_toolbar
        self.header_bar._select_button.connect(
            'toggled', self._on_header_bar_toggled)
        self.header_bar._cancel_button.connect(
            'clicked', self._on_cancel_button_clicked)

        self.name = name
        self.title = title
        self.add(self._grid)

        self.show_all()
        self._items = []
        self._connect_view()
        self.cache = albumArtCache.get_default()
        self._symbolicIcon = self.cache.get_default_icon(self._iconHeight,
                                                         self._iconWidth)

        self._init = False
        grilo.connect('ready', self._on_grilo_ready)
        self.header_bar.header_bar.connect('state-changed',
                                           self._on_state_changed)
        self.header_bar.connect('selection-mode-changed',
                                self._on_selection_mode_changed)
        self.view.connect('view-selection-changed',
                          self._on_view_selection_changed)

        self._discovering_urls = {}
        grilo.connect('changes-pending', self._on_changes_pending)

    @log
    def _on_changes_pending(self, data=None):
        pass

    @log
    def _on_header_bar_toggled(self, button):
        if button.get_active():
            self.view.set_selection_mode(True)
            self.header_bar.set_selection_mode(True)
            self.player.actionbar.set_visible(False)
            self.selection_toolbar.actionbar.set_visible(True)
            self.selection_toolbar._add_to_playlist_button.set_sensitive(False)
            self.selection_toolbar._remove_from_playlist_button.set_sensitive(False)
        else:
            self.view.set_selection_mode(False)
            self.header_bar.set_selection_mode(False)
            self.player.actionbar.set_visible(self.player.currentTrack is not None)
            self.selection_toolbar.actionbar.set_visible(False)

    @log
    def _on_cancel_button_clicked(self, button):
        self.view.set_selection_mode(False)
        self.header_bar.set_selection_mode(False)

    @log
    def _on_grilo_ready(self, data=None):
        if (self.header_bar.get_stack().get_visible_child() == self
                and not self._init):
            self._populate()
        self.header_bar.get_stack().connect('notify::visible-child',
                                            self._on_headerbar_visible)

    @log
    def _on_headerbar_visible(self, widget, param):
        if self == widget.get_visible_child() and not self._init:
            self._populate()

    @log
    def _on_view_selection_changed(self, widget):
        items = self.view.get_selection()
        self.selection_toolbar._add_to_playlist_button.\
            set_sensitive(len(items) > 0)
        self.selection_toolbar._remove_from_playlist_button.\
            set_sensitive(len(items) > 0)
        if len(items) > 0:
            self.header_bar._selection_menu_label.set_text(
                ngettext("Selected %d item", "Selected %d items", len(items)) % len(items))
        else:
            self.header_bar._selection_menu_label.set_text(_("Click on items to select them"))

    @log
    def _populate(self, data=None):
        self._init = True
        self.populate()

    @log
    def _on_state_changed(self, widget, data=None):
        pass

    @log
    def _on_selection_mode_changed(self, widget, data=None):
        pass

    @log
    def _connect_view(self):
        if self.view.get_view_type() == Gd.MainViewType.ICON:
            self.view.connect_after('draw', self._on_view_draw)
            self.view.add_events(Gdk.EventMask.EXPOSURE_MASK)

    @log
    def _on_view_draw(self, widget, cr):
        vsbl_range = widget.get_children()[0].get_visible_range()
        if not vsbl_range or self.old_vsbl_range == vsbl_range:
            return
        self.old_vsbl_range = vsbl_range
        GLib.idle_add(self.on_scroll_event, self.view)

    @log
    def on_scroll_event(self, widget, event=None):
        vsbl_range = widget.get_children()[0].get_visible_range()
        if not vsbl_range:
            return

        def load_album_art_for(path):
            try:
                _iter = self._model.get_iter(path)
                item = self._model.get_value(_iter, 5)
                if not item:
                    return
                title = self._model.get_value(_iter, 2)
                artist = self._model.get_value(_iter, 3)
                thumbnail = self._model.get_value(_iter, 4)
                if thumbnail == self._symbolicIcon:
                    albumArtCache.get_default().lookup(
                        item, self._iconWidth, self._iconHeight, self._on_lookup_ready,
                        _iter, artist, title)
            except Exception:
                pass

        # Load thumbnails
        path = vsbl_range[0]
        while path <= vsbl_range[1]:
            load_album_art_for(path)
            path.next()

        # Add 10 more albums to avoid visible thumbnail loading
        for i in range(0, 10):
            try:
                path.next()
                load_album_art_for(path)
            except ValueError:
                # No such path
                break

    @log
    def populate(self):
        print('populate')

    @log
    def _on_discovered(self, info, error, _iter):
        if error:
            print("Info %s: error: %s" % (info, error))
            self._model.set(_iter, [8, 10], [self.errorIconName, True])

    @log
    def _add_item(self, source, param, item, remaining=0, data=None):
        if not item:
            return
        self._offset += 1
        artist = item.get_string(Grl.METADATA_KEY_ARTIST)\
            or item.get_author()\
            or _("Unknown Artist")
        title = albumArtCache.get_media_title(item)
        item.set_title(title)

        def add_new_item():
            _iter = self._model.append(None)
            icon_name = self.nowPlayingIconName
            if item.get_url():
                try:
                    self.player.discoverer.discover_uri(item.get_url())
                except:
                    print('failed to discover url ' + item.get_url())
                    icon_name = self.errorIconName
            self._model.set(_iter,
                            [0, 1, 2, 3, 4, 5, 7, 8, 9, 10],
                            [str(item.get_id()), '', title,
                             artist, self._symbolicIcon, item,
                             0, icon_name, False, icon_name == self.errorIconName])
        GLib.idle_add(add_new_item)

    @log
    def _on_lookup_ready(self, icon, path, _iter):
        if icon:
            self._model.set_value(_iter, 4, icon)
            self.view.queue_draw()

    @log
    def _add_list_renderers(self):
        pass

    @log
    def _on_item_activated(self, widget, id, path):
        pass

    @log
    def _on_selection_mode_request(self, *args):
        self.header_bar._select_button.clicked()

    @log
    def get_selected_tracks(self, callback):
        callback([])


# Class for the Empty View
class Empty(Gtk.Stack):
    @log
    def __init__(self, window, player):
        Gtk.Stack.__init__(self,
                           transition_type=Gtk.StackTransitionType.CROSSFADE)
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Music/NoMusic.ui')
        widget = builder.get_object('container')
        self.add(widget)
        self.show_all()


class Albums(ViewContainer):
    @log
    def __init__(self, window, player):
        ViewContainer.__init__(self, 'albums', _("Albums"), window, Gd.MainViewType.ICON)
        self._albumWidget = Widgets.AlbumWidget(player)
        self.player = player
        self.add(self._albumWidget)
        self.albums_selected = []
        self.items_selected = []
        self.items_selected_callback = None

    @log
    def _on_changes_pending(self, data=None):
        if (self._init and self.header_bar._selectionMode is False):
            self._offset = 0
            self._model.clear()
            self.populate()
            grilo.changes_pending['Albums'] = False

    @log
    def _on_selection_mode_changed(self, widget, data=None):
        if self.header_bar._selectionMode is False and grilo.changes_pending['Albums'] is True:
            self._on_changes_pending()

    @log
    def _back_button_clicked(self, widget, data=None):
        self.set_visible_child(self._grid)

    @log
    def _on_item_activated(self, widget, id, path):
        _iter = self._model.get_iter(path)
        title = self._model.get_value(_iter, 2)
        artist = self._model.get_value(_iter, 3)
        item = self._model.get_value(_iter, 5)
        self._albumWidget.update(artist, title, item,
                                 self.header_bar, self.selection_toolbar)
        self.header_bar.set_state(ToolbarState.CHILD_VIEW)
        escaped_title = albumArtCache.get_media_title(item)
        self.header_bar.header_bar.set_title(escaped_title)
        self.header_bar.header_bar.sub_title = artist
        self.set_visible_child(self._albumWidget)

    @log
    def populate(self):
        if grilo.tracker:
            GLib.idle_add(grilo.populate_albums, self._offset, self._add_item)

    @log
    def get_selected_tracks(self, callback):
        if self.header_bar._state == ToolbarState.CHILD_VIEW:
            items = []
            for path in self._albumWidget.view.get_selection():
                _iter = self._albumWidget.model.get_iter(path)
                items.append(self._albumWidget.model.get_value(_iter, 5))
            callback(items)
        else:
            self.items_selected = []
            self.items_selected_callback = callback
            self.albums_index = 0
            self.albums_selected = [self._model.get_value(self._model.get_iter(path), 5)
                                    for path in self.view.get_selection()]
            if len(self.albums_selected):
                self._get_selected_album_songs()

    @log
    def _get_selected_album_songs(self):
        grilo.populate_album_songs(
            self.albums_selected[self.albums_index],
            self._add_selected_item)
        self.albums_index += 1

    @log
    def _add_selected_item(self, source, param, item, remaining=0, data=None):
        if item:
            self.items_selected.append(item)
        if remaining == 0:
            if self.albums_index < len(self.albums_selected):
                self._get_selected_album_songs()
            else:
                self.items_selected_callback(self.items_selected)


class Songs(ViewContainer):
    @log
    def __init__(self, window, player):
        ViewContainer.__init__(self, 'songs', _("Songs"), window, Gd.MainViewType.LIST)
        self._items = {}
        self.isStarred = None
        self.iter_to_clean = None
        self.view.get_generic_view().get_style_context()\
            .add_class('songs-list')
        self._iconHeight = 32
        self._iconWidth = 32
        self.cache = albumArtCache.get_default()
        self._symbolicIcon = self.cache.get_default_icon(self._iconHeight,
                                                         self._iconWidth)
        self._add_list_renderers()
        self.player = player
        self.player.connect('playlist-item-changed', self.update_model)

    @log
    def _on_changes_pending(self, data=None):
        if (self._init and self.header_bar._selectionMode is False):
            self._model.clear()
            self._offset = 0
            self.populate()
            grilo.changes_pending['Songs'] = False

    @log
    def _on_selection_mode_changed(self, widget, data=None):
        if self.header_bar._selectionMode is False and grilo.changes_pending['Songs'] is True:
            self._on_changes_pending()

    @log
    def _on_item_activated(self, widget, id, path):
        _iter = self._model.get_iter(path)
        if self._model.get_value(_iter, 8) != self.errorIconName:
            self.player.set_playlist('Songs', None, self._model, _iter, 5)
            self.player.set_playing(True)

    @log
    def update_model(self, player, playlist, currentIter):
        if self.iter_to_clean:
            self._model.set_value(self.iter_to_clean, 10, False)
        if playlist != self._model:
            return False

        self._model.set_value(currentIter, 10, True)
        path = self._model.get_path(currentIter)
        self.view.get_generic_view().scroll_to_path(path)
        if self._model.get_value(currentIter, 8) != self.errorIconName:
            self.iter_to_clean = currentIter.copy()
        return False

    def _add_item(self, source, param, item, remaining=0, data=None):
        if not item:
            return
        self._offset += 1
        item.set_title(albumArtCache.get_media_title(item))
        artist = item.get_string(Grl.METADATA_KEY_ARTIST)\
            or item.get_author()\
            or _("Unknown Artist")
        if item.get_url() is None:
            return
        _iter = self._model.insert_with_valuesv(
            -1,
            [2, 3, 5, 8, 9, 10],
            [albumArtCache.get_media_title(item),
             artist, item, self.nowPlayingIconName, False, False])
        self.player.discover_item(item, self._on_discovered, _iter)

    @log
    def _add_list_renderers(self):
        list_widget = self.view.get_generic_view()
        cols = list_widget.get_columns()
        cells = cols[0].get_cells()
        cells[2].set_visible(False)
        now_playing_symbol_renderer = Gtk.CellRendererPixbuf(xalign=1.0)

        column_now_playing = Gtk.TreeViewColumn()
        column_now_playing.set_property('fixed_width', 24)
        column_now_playing.pack_start(now_playing_symbol_renderer, False)
        column_now_playing.add_attribute(now_playing_symbol_renderer,
                                         'visible', 10)
        column_now_playing.add_attribute(now_playing_symbol_renderer,
                                         'icon_name', 8)
        list_widget.insert_column(column_now_playing, 0)

        title_renderer = Gtk.CellRendererText(
            xpad=0,
            xalign=0.0,
            yalign=0.5,
            height=48,
            ellipsize=Pango.EllipsizeMode.END
        )
        list_widget.add_renderer(title_renderer,
                                 self._on_list_widget_title_render, None)
        cols[0].add_attribute(title_renderer, 'text', 2)

        star_renderer = Gtk.CellRendererPixbuf(
            xpad=32,
            icon_name=self.starIconName
        )
        list_widget.add_renderer(star_renderer,
                                 self._on_list_widget_star_render, None)
        cols[0].add_attribute(star_renderer, 'visible', 9)

        duration_renderer = Gd.StyledTextRenderer(
            xpad=32,
            xalign=1.0
        )
        duration_renderer.add_class('dim-label')
        list_widget.add_renderer(duration_renderer,
                                 self._on_list_widget_duration_render, None)

        artist_renderer = Gd.StyledTextRenderer(
            xpad=32,
            ellipsize=Pango.EllipsizeMode.END
        )
        artist_renderer.add_class('dim-label')
        list_widget.add_renderer(artist_renderer,
                                 self._on_list_widget_artist_render, None)
        cols[0].add_attribute(artist_renderer, 'text', 3)

        type_renderer = Gd.StyledTextRenderer(
            xpad=32,
            ellipsize=Pango.EllipsizeMode.END
        )
        type_renderer.add_class('dim-label')
        list_widget.add_renderer(type_renderer,
                                 self._on_list_widget_type_render, None)

    def _on_list_widget_title_render(self, col, cell, model, _iter, data):
        pass

    def _on_list_widget_star_render(self, col, cell, model, _iter, data):
        pass

    def _on_list_widget_duration_render(self, col, cell, model, _iter, data):
        item = model.get_value(_iter, 5)
        if item:
            seconds = item.get_duration()
            minutes = seconds // 60
            seconds %= 60
            cell.set_property('text', '%i:%02i' % (minutes, seconds))

    def _on_list_widget_artist_render(self, col, cell, model, _iter, data):
        pass

    def _on_list_widget_type_render(self, coll, cell, model, _iter, data):
        item = model.get_value(_iter, 5)
        if item:
            cell.set_property('text', item.get_string(Grl.METADATA_KEY_ALBUM) or _("Unknown Album"))

    @log
    def populate(self):
        self._init = True
        if grilo.tracker:
            GLib.idle_add(grilo.populate_songs, self._offset, self._add_item)

    @log
    def get_selected_tracks(self, callback):
        callback([self._model.get_value(self._model.get_iter(path), 5)
                  for path in self.view.get_selection()])


class Artists (ViewContainer):
    @log
    def __init__(self, window, player):
        ViewContainer.__init__(self, 'artists', _("Artists"),
                               window, Gd.MainViewType.LIST, True)
        self.artists_counter = 0
        self.player = player
        self._artists = {}
        self.albums_selected = []
        self.items_selected = []
        self.items_selected_callback = None
        self.artistAlbumsStack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
        )
        self._artistAlbumsWidget = Gtk.Frame(
            shadow_type=Gtk.ShadowType.NONE,
            hexpand=True
        )
        self.artistAlbumsStack.add_named(self._artistAlbumsWidget, "sidebar")
        self.artistAlbumsStack.set_visible_child_name("sidebar")
        self.view.set_hexpand(False)
        self.view.get_style_context().add_class('artist-panel')
        self.view.get_generic_view().get_selection().set_mode(
            Gtk.SelectionMode.SINGLE)
        self._grid.attach(self.artistAlbumsStack, 2, 0, 2, 2)
        self._add_list_renderers()
        if (Gtk.Settings.get_default().get_property(
                'gtk_application_prefer_dark_theme')):
            self.view.get_generic_view().get_style_context().\
                add_class('artist-panel-dark')
        else:
            self.view.get_generic_view().get_style_context().\
                add_class('artist-panel-white')
        self.show_all()

    @log
    def _on_changes_pending(self, data=None):
        if (self._init and self.header_bar._selectionMode is False):
            self._model.clear()
            self._artists.clear()
            self._offset = 0
            self._populate()
            grilo.changes_pending['Artists'] = False

    @log
    def _populate(self, data=None):
        selection = self.view.get_generic_view().get_selection()
        if not selection.get_selected()[1]:
            self._allIter = self._model.insert_with_valuesv(-1, [2], [_("All Artists")])
            self._last_selection = self._allIter
            self._artists[_("All Artists").casefold()] =\
                {'iter': self._allIter, 'albums': [], 'widget': None}
            selection.select_path(self._model.get_path(self._allIter))
        self._init = True
        self.populate()
        self.view.emit('item-activated', '0',
                       self._model.get_path(self._allIter))

    @log
    def _add_list_renderers(self):
        list_widget = self.view.get_generic_view()

        cols = list_widget.get_columns()
        cells = cols[0].get_cells()
        cells[1].set_visible(False)
        cells[2].set_visible(False)
        self.text_renderer = Gd.StyledTextRenderer(
            xpad=16,
            ypad=16,
            ellipsize=Pango.EllipsizeMode.END,
            xalign=0.0,
            width=220
        )
        list_widget.add_renderer(self.text_renderer, lambda *args: None, None)
        cols[0].clear_attributes(self.text_renderer)
        cols[0].add_attribute(self.text_renderer, 'text', 2)

    @log
    def _on_item_activated(self, widget, item_id, path):
        _iter = self._model.get_iter(path)
        self._last_selection = _iter
        artist = self._model.get_value(_iter, 2)
        albums = self._artists[artist.casefold()]['albums']

        widget = self._artists[artist.casefold()]['widget']
        if widget:
            if widget.model == self.player.running_playlist('Artist', widget.artist):
                self._artistAlbumsWidget = widget.get_parent()
                GLib.idle_add(self.artistAlbumsStack.set_visible_child,
                              self._artistAlbumsWidget)
                return
            elif widget.get_parent() == self._artistAlbumsWidget:
                return
            else:
                widget.get_parent().destroy()

        # Prepare a new artistAlbumsWidget here
        new_artistAlbumsWidget = Gtk.Frame(
            shadow_type=Gtk.ShadowType.NONE,
            hexpand=True
        )
        self.artistAlbumsStack.add(new_artistAlbumsWidget)

        artistAlbums = None
        if (self._model.get_string_from_iter(_iter) ==
                self._model.get_string_from_iter(self._allIter)):
            artistAlbums = Widgets.AllArtistsAlbums(
                self.player, self.header_bar, self.selection_toolbar
            )
        else:
            artistAlbums = Widgets.ArtistAlbums(
                artist, albums, self.player,
                self.header_bar, self.selection_toolbar
            )
        self._artists[artist.casefold()]['widget'] = artistAlbums
        new_artistAlbumsWidget.add(artistAlbums)
        new_artistAlbumsWidget.show()

        # Replace previous widget
        self._artistAlbumsWidget = new_artistAlbumsWidget
        GLib.idle_add(self.artistAlbumsStack.set_visible_child, new_artistAlbumsWidget)

    @log
    def _add_item(self, source, param, item, remaining=0, data=None):
        if item is None:
            return
        self._offset += 1
        artist = item.get_string(Grl.METADATA_KEY_ARTIST)\
            or item.get_author()\
            or _("Unknown Artist")
        if not artist.casefold() in self._artists:
            _iter = self._model.insert_with_valuesv(-1, [2], [artist])
            self._artists[artist.casefold()] = {'iter': _iter, 'albums': [], 'widget': None}

        self._artists[artist.casefold()]['albums'].append(item)

    @log
    def populate(self):
        if grilo.tracker:
            GLib.idle_add(grilo.populate_artists, self._offset, self._add_item)

    @log
    def _on_header_bar_toggled(self, button):
        ViewContainer._on_header_bar_toggled(self, button)

        if button.get_active():
            self.text_renderer.set_fixed_size(178, -1)
            self._last_selection =\
                self.view.get_generic_view().get_selection().get_selected()[1]
            self.view.get_generic_view().get_selection().set_mode(
                Gtk.SelectionMode.NONE)
        else:
            self.text_renderer.set_fixed_size(220, -1)
            self.view.get_generic_view().get_selection().set_mode(
                Gtk.SelectionMode.SINGLE)
            if self._last_selection is not None:
                self.view.get_generic_view().get_selection().select_iter(
                    self._last_selection)

    @log
    def _on_selection_mode_changed(self, widget, data=None):
        self.artistAlbumsStack.set_sensitive(not self.header_bar._selectionMode)
        if self.header_bar._selectionMode is False and grilo.changes_pending['Artists'] is True:
            self._on_changes_pending()

    @log
    def get_selected_tracks(self, callback):
        self.items_selected = []
        self.items_selected_callback = callback
        self.albums_index = 0
        self.albums_selected = []

        for path in self.view.get_selection():
            _iter = self._model.get_iter(path)
            artist = self._model.get_value(_iter, 2)
            albums = self._artists[artist.casefold()]['albums']
            if (self._model.get_string_from_iter(_iter) !=
                    self._model.get_string_from_iter(self._allIter)):
                self.albums_selected.extend(albums)

        if len(self.albums_selected):
            self._get_selected_album_songs()

    @log
    def _get_selected_album_songs(self):
        grilo.populate_album_songs(
            self.albums_selected[self.albums_index],
            self._add_selected_item)
        self.albums_index += 1

    @log
    def _add_selected_item(self, source, param, item, remaining=0, data=None):
        if item:
            self.items_selected.append(item)
        if remaining == 0:
            if self.albums_index < len(self.albums_selected):
                self._get_selected_album_songs()
            else:
                self.items_selected_callback(self.items_selected)


class Playlist(ViewContainer):

    @log
    def __init__(self, window, player):
        ViewContainer.__init__(self, 'playlists', _("Playlists"), window,
                               Gd.MainViewType.LIST, True)

        self.view.set_view_type(Gd.MainViewType.LIST)
        self.view.set_hexpand(False)
        self.view.get_style_context().add_class('artist-panel')
        self.view.get_generic_view().get_selection().set_mode(
            Gtk.SelectionMode.SINGLE)
        self._add_list_renderers()

        self._playlistWidget = Widgets.PlaylistWidget(
            player, self.header_bar, self.selection_toolbar
        )
        self._grid.attach(self._playlistWidget, 2, 0, 2, 2)

        if (Gtk.Settings.get_default().get_property(
                'gtk_application_prefer_dark_theme')):
            self.view.get_generic_view().get_style_context().\
                add_class("artist-panel-dark")
        else:
            self.view.get_generic_view().get_style_context().\
                add_class("artist-panel-white")

        self.player = player
        self.playlist = None

        playlists.connect('playlist-created', self._on_playlist_created)
        playlists.connect('playlist-deleted', self._on_playlist_deleted)

        self.show_all()

    @log
    def _add_list_renderers(self):
        list_widget = self.view.get_generic_view()

        cols = list_widget.get_columns()
        cells = cols[0].get_cells()
        cells[1].set_visible(False)
        cells[2].set_visible(False)
        nameRenderer = Gd.StyledTextRenderer(
            xpad=16,
            ypad=16,
            ellipsize=Pango.EllipsizeMode.END,
            xalign=0.0,
            width=220
        )
        list_widget.add_renderer(nameRenderer, lambda *args: None, None)
        cols[0].clear_attributes(nameRenderer)
        cols[0].add_attribute(nameRenderer, "text", 2)

    @log
    def _populate(self):
        self._init = True
        self.populate()

    @log
    def populate(self):
        if grilo.tracker:
            GLib.idle_add(grilo.populate_playlists, self._offset,
                          self._add_item)

    @log
    def _add_item(self, source, param, item, remaining=0, data=None):
        self._add_item_to_model(item)

    @log
    def _add_item_to_model(self, item):
        if not item:
            return
        _iter = self._model.insert_with_valuesv(
            -1,
            [2, 5],
            [albumArtCache.get_media_title(item), item])
        if self._model.iter_n_children(None) == 1:
            _iter = self._model.get_iter_first()
            selection = self.view.get_generic_view().get_selection()
            selection.select_iter(_iter)
            self.view.emit('item-activated', '0',
                           self._model.get_path(_iter))

    @log
    def _on_item_activated(self, widget, item_id, path):
        _iter = self._model.get_iter(path)
        self.playlist = self._model.get_value(_iter, 5)
        self._playlistWidget.update(self.playlist)

    @log
    def _on_selection_mode_changed(self, widget, data=None):
        self.view.set_sensitive(not self.header_bar._selectionMode)
        self._playlistWidget.set_selection_mode(self.header_bar._selectionMode)

    @log
    def _on_selection_mode_request(self, *args):
        pass

    @log
    def _on_view_selection_changed(self, widget):
        self._playlistWidget._on_view_selection_changed(widget)

    @log
    def _on_header_bar_toggled(self, button):
        pass

    @log
    def _on_cancel_button_clicked(self, button):
        pass

    @log
    def _on_playlist_created(self, playlists, item):
        self._add_item_to_model(item)
        if self._model.iter_n_children(None) == 1:
            _iter = self._model.get_iter_first()
            selection = self.view.get_generic_view().get_selection()
            selection.select_iter(_iter)
            self.view.emit('item-activated', '0',
                           self._model.get_path(_iter))

    @log
    def _on_playlist_deleted(self, playlists, item):
        _iter = None
        for row in self._model:
            if row[5].get_id() == item.get_id():
                _iter = row.iter
                break

        if not _iter:
            return

        iter_next = self._model.iter_next(_iter)\
            or self._model.iter_previous(_iter)
        if iter_next:
            selection = self.view.get_generic_view().get_selection()
            selection.select_iter(iter_next)
            self.view.emit('item-activated', '0',
                           self._model.get_path(iter_next))

        self._model.remove(_iter)

    @log
    def get_selected_tracks(self, callback):
        self._playlistWidget.get_selected_tracks(callback)


class Search(ViewContainer):
    @log
    def __init__(self, window, player):
        ViewContainer.__init__(self, 'search', None, window, Gd.MainViewType.LIST)
        self.view.set_halign(Gtk.Align.CENTER)
        self.view.set_size_request(530, -1)
        self._items = {}
        self.isStarred = None
        self.iter_to_clean = None
        self._iconHeight = 48
        self._iconWidth = 48
        self.cache = albumArtCache.get_default()
        self._symbolicIcon = self.cache.get_default_icon(self._iconHeight,
                                                         self._iconWidth)
        self._add_list_renderers()
        self.player = player
        self.head_iters = [None, None, None, None]
        self.songs_model = self._model

        self.albums_selected = []
        self._albums = {}
        self._albumWidget = Widgets.AlbumWidget(player)
        self.add(self._albumWidget)

        self.artists_albums_selected = []
        self._artists = {}
        self._artistAlbumsWidget = None

        self.view.get_generic_view().set_show_expanders(False)
        self.items_selected = []
        self.items_selected_callback = None

    @log
    def _back_button_clicked(self, widget, data=None):
        if self.get_visible_child() == self._artistAlbumsWidget:
            self._artistAlbumsWidget.destroy()
            self._artistAlbumsWidget = None
        self.set_visible_child(self._grid)

    @log
    def _on_item_activated(self, widget, id, path):
        child_path = self.filter_model.convert_path_to_child_path(path)
        _iter = self._model.get_iter(child_path)
        if self._model[_iter][11] == 'album':
            title = self._model.get_value(_iter, 2)
            artist = self._model.get_value(_iter, 3)
            item = self._model.get_value(_iter, 5)
            self._albumWidget.update(artist, title, item,
                                     self.header_bar, self.selection_toolbar)
            self.header_bar.set_state(ToolbarState.SEARCH_VIEW)
            escaped_title = albumArtCache.get_media_title(item)
            self.header_bar.header_bar.set_title(escaped_title)
            self.header_bar.header_bar.sub_title = artist
            self.set_visible_child(self._albumWidget)
            self.header_bar.searchbar.show_bar(False)
        elif self._model[_iter][11] == 'artist':
            artist = self._model.get_value(_iter, 2)
            albums = self._artists[artist.casefold()]['albums']

            self._artistAlbumsWidget = Widgets.ArtistAlbums(
                artist, albums, self.player,
                self.header_bar, self.selection_toolbar, True
            )
            self.add(self._artistAlbumsWidget)

            self.header_bar.set_state(ToolbarState.SEARCH_VIEW)
            self.header_bar.header_bar.set_title(artist)
            self.set_visible_child(self._artistAlbumsWidget)
            self.header_bar.searchbar.show_bar(False)
        elif self._model[_iter][11] == 'song':
            if self._model.get_value(_iter, 8) != self.errorIconName:
                child_iter = self.songs_model.convert_child_iter_to_iter(_iter)[1]
                self.player.set_playlist('Search Results', None, self.songs_model, child_iter, 5)
                self.player.set_playing(True)
        else:  # Headers
            if self.view.get_generic_view().row_expanded(path):
                self.view.get_generic_view().collapse_row(path)
            else:
                self.view.get_generic_view().expand_row(path, False)

    @log
    def _on_selection_mode_changed(self, widget, data=None):
        if self._artistAlbumsWidget is not None and self.get_visible_child() == self._artistAlbumsWidget:
            self._artistAlbumsWidget.set_selection_mode(self.header_bar._selectionMode)

    @log
    def _add_search_item(self, source, param, item, remaining=0, data=None):
        if not item or data != self._model:
            return

        artist = item.get_string(Grl.METADATA_KEY_ARTIST) \
            or item.get_author() \
            or _("Unknown Artist")
        album = item.get_string(Grl.METADATA_KEY_ALBUM) \
            or _("Unknown Album")

        key = '%s-%s' % (artist, album)
        if key not in self._albums:
            self._albums[key] = Grl.MediaBox()
            self._albums[key].set_title(album)
            self._albums[key].add_author(artist)
            self._albums[key].set_source(source.get_id())
            self._albums[key].tracks = []
            self._add_item(source, None, self._albums[key], 0, [self._model, 'album'])
            self._add_item(source, None, self._albums[key], 0, [self._model, 'artist'])

        self._albums[key].tracks.append(item)
        self._add_item(source, None, item, 0, [self._model, 'song'])

    @log
    def _add_item(self, source, param, item, remaining=0, data=None):
        if data is None:
            return

        model, category = data
        if not item or model != self._model:
            return

        self._offset += 1
        title = albumArtCache.get_media_title(item)
        item.set_title(title)
        artist = item.get_string(Grl.METADATA_KEY_ARTIST) \
            or item.get_author() \
            or _("Unknown Artist")

        group = 3
        try:
            group = {'album': 0, 'artist': 1, 'song': 2}[category]
        except:
            pass

        _iter = None
        if category == 'album' or category == 'song':
            _iter = self._model.insert_with_values(
                self.head_iters[group], -1,
                [0, 2, 3, 4, 5, 8, 9, 10, 11],
                [str(item.get_id()), title, artist,
                 self._symbolicIcon, item, self.nowPlayingIconName,
                 False, False, category])
        else:
            if not artist.casefold() in self._artists:
                _iter = self._model.insert_with_values(
                    self.head_iters[group], -1,
                    [0, 2, 4, 5, 8, 9, 10, 11],
                    [str(item.get_id()), artist,
                     self._symbolicIcon, item, self.nowPlayingIconName,
                     False, False, category])
                self._artists[artist.casefold()] = {'iter': _iter, 'albums': []}

            self._artists[artist.casefold()]['albums'].append(item)

        if _iter:
            albumArtCache.get_default().lookup(
                item, self._iconWidth, self._iconHeight, self._on_lookup_ready,
                _iter, artist, title)

        if category == 'song':
            self.player.discover_item(item, self._on_discovered, _iter)

        if self._model.iter_n_children(self.head_iters[group]) == 1:
            path = self._model.get_path(self.head_iters[group])
            self.view.get_generic_view().expand_row(path, False)

    @log
    def _add_list_renderers(self):
        list_widget = self.view.get_generic_view()
        cols = list_widget.get_columns()

        title_renderer = Gtk.CellRendererText(
            xpad=12,
            xalign=0.0,
            yalign=0.5,
            height=32,
            ellipsize=Pango.EllipsizeMode.END,
            weight=Pango.Weight.BOLD
        )
        list_widget.add_renderer(title_renderer,
                                 self._on_list_widget_title_render, None)
        cols[0].add_attribute(title_renderer, 'text', 2)

        cells = cols[0].get_cells()
        cols[0].reorder(cells[0], -1)
        cols[0].set_cell_data_func(cells[0], self._on_list_widget_selection_render, None)

    def _on_list_widget_selection_render(self, col, cell, model, _iter, data):
        cell.set_visible(self.view.get_selection_mode() and model.iter_parent(_iter) is not None)

    def _on_list_widget_title_render(self, col, cell, model, _iter, data):
        cells = col.get_cells()
        cells[0].set_visible(model.iter_parent(_iter) is not None)
        cells[1].set_visible(model.iter_parent(_iter) is not None)
        cells[2].set_visible(model.iter_parent(_iter) is None)

    @log
    def populate(self):
        self.header_bar.set_state(ToolbarState.MAIN)

    @log
    def get_selected_tracks(self, callback):
        if self.get_visible_child() == self._albumWidget:
            items = []
            for path in self._albumWidget.view.get_selection():
                _iter = self._albumWidget.model.get_iter(path)
                items.append(self._albumWidget.model.get_value(_iter, 5))
            callback(items)
        elif self.get_visible_child() == self._artistAlbumsWidget:
            items = []
            for row in self._artistAlbumsWidget.model:
                if row[6]:
                    items.append(row[5])
            callback(items)
        else:
            self.items_selected = []
            self.items_selected_callback = callback
            self._get_selected_albums()

    @log
    def _get_selected_albums(self):
        self.albums_index = 0
        self.albums_selected = [self._model[child_path][5]
                                for child_path in [self.filter_model.convert_path_to_child_path(path)
                                                   for path in self.view.get_selection()]
                                if self._model[child_path][11] == 'album']
        if len(self.albums_selected):
            self._get_selected_albums_songs()
        else:
            self._get_selected_artists()

    @log
    def _get_selected_albums_songs(self):
        grilo.populate_album_songs(
            self.albums_selected[self.albums_index],
            self._add_selected_albums_songs)
        self.albums_index += 1

    @log
    def _add_selected_albums_songs(self, source, param, item, remaining=0, data=None):
        if item:
            self.items_selected.append(item)
        if remaining == 0:
            if self.albums_index < len(self.albums_selected):
                self._get_selected_albums_songs()
            else:
                self._get_selected_artists()

    @log
    def _get_selected_artists(self):
        self.artists_albums_index = 0
        self.artists_selected = [self._artists[self._model[child_path][2].casefold()]
                                 for child_path in [self.filter_model.convert_path_to_child_path(path)
                                                    for path in self.view.get_selection()]
                                 if self._model[child_path][11] == 'artist']

        self.artists_albums_selected = []
        for artist in self.artists_selected:
            self.artists_albums_selected.extend(artist['albums'])

        if len(self.artists_albums_selected):
            self._get_selected_artists_albums_songs()
        else:
            self._get_selected_songs()

    @log
    def _get_selected_artists_albums_songs(self):
        grilo.populate_album_songs(
            self.artists_albums_selected[self.artists_albums_index],
            self._add_selected_artists_albums_songs)
        self.artists_albums_index += 1

    @log
    def _add_selected_artists_albums_songs(self, source, param, item, remaining=0, data=None):
        if item:
            self.items_selected.append(item)
        if remaining == 0:
            if self.artists_albums_index < len(self.artists_albums_selected):
                self._get_selected_artists_albums_songs()
            else:
                self._get_selected_songs()

    @log
    def _get_selected_songs(self):
        self.items_selected.extend([self._model[child_path][5]
                                    for child_path in [self.filter_model.convert_path_to_child_path(path)
                                                       for path in self.view.get_selection()]
                                    if self._model[child_path][11] == 'song'])
        self.items_selected_callback(self.items_selected)

    @log
    def _filter_visible_func(self, model, _iter, data=None):
        return model.iter_parent(_iter) is not None or model.iter_has_child(_iter)

    @log
    def set_search_text(self, search_term, fields_filter):
        query_matcher = {
            'album': {
                'search_all': Query.get_albums_with_any_match,
                'search_artist': Query.get_albums_with_artist_match,
                'search_album': Query.get_albums_with_album_match,
                'search_track': Query.get_albums_with_track_match,
                'search_playlist': Query.get_albums_with_playlist_match,
            },
            'artist': {
                'search_all': Query.get_artists_with_any_match,
                'search_artist': Query.get_artists_with_artist_match,
                'search_album': Query.get_artists_with_album_match,
                'search_track': Query.get_artists_with_track_match,
                'search_playlist': Query.get_artists_with_playlist_match,
            },
            'song': {
                'search_all': Query.get_songs_with_any_match,
                'search_artist': Query.get_songs_with_artist_match,
                'search_album': Query.get_songs_with_album_match,
                'search_track': Query.get_songs_with_track_match,
                'search_playlist': Query.get_songs_with_playlist_match,
            },
        }

        self._model = Gtk.TreeStore(
            GObject.TYPE_STRING,
            GObject.TYPE_STRING,
            GObject.TYPE_STRING,    # item title or header text
            GObject.TYPE_STRING,    # artist for albums and songs
            GdkPixbuf.Pixbuf,       # album art
            GObject.TYPE_OBJECT,    # item
            GObject.TYPE_BOOLEAN,
            GObject.TYPE_INT,
            GObject.TYPE_STRING,
            GObject.TYPE_BOOLEAN,
            GObject.TYPE_BOOLEAN,
            GObject.TYPE_STRING     # type
        )
        self.filter_model = self._model.filter_new(None)
        self.filter_model.set_visible_func(self._filter_visible_func)
        self.view.set_model(self.filter_model)

        self._albums = {}
        self._artists = {}

        if search_term == "":
            return

        albums_iter = self._model.insert_with_values(None, -1, [2], [_("Albums")])
        artists_iter = self._model.insert_with_values(None, -1, [2], [_("Artists")])
        songs_iter = self._model.insert_with_values(None, -1, [2], [_("Songs")])
        playlists_iter = self._model.insert_with_values(None, -1, [2], [_("Playlists")])

        self.head_iters = [albums_iter, artists_iter, songs_iter, playlists_iter]
        self.songs_model = self._model.filter_new(self._model.get_path(songs_iter))

        # Use queries for Tracker
        if not grilo.search_source or \
           grilo.search_source.get_id() == 'grl-tracker-source':
            for category in ('album', 'artist', 'song'):
                query = query_matcher[category][fields_filter](search_term)
                grilo.populate_custom_query(query, self._add_item, -1, [self._model, category])
        if not grilo.search_source or \
           grilo.search_source.get_id() != 'grl-tracker-source':
            # nope, can't do - reverting to Search
            grilo.search(search_term, self._add_search_item, self._model)
