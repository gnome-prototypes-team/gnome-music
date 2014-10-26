# Copyright (c) 2013 Vadim Rutkovsky <vrutkovs@redhat.com>
# Copyright (c) 2013 Shivani Poddar <shivani.poddar92@gmail.com>
# Copyright (c) 2013 Arnel A. Borja <kyoushuu@yahoo.com>
# Copyright (c) 2013 Seif Lotfy <seif@lotfy.com>
# Copyright (c) 2013 Sai Suman Prayaga <suman.sai14@gmail.com>
# Copyright (c) 2013 Jackson Isaac <jacksonisaac2008@gmail.com>
# Copyright (c) 2013 Felipe Borges <felipe10borges@gmail.com>
# Copyright (c) 2013 Giovanni Campagna <scampa.giovanni@gmail.com>
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


from gi.repository import Gtk, Gdk, Gd, GLib, GObject, Pango
from gi.repository import GdkPixbuf, Grl
from gi.repository import Tracker
from gettext import gettext as _, ngettext
from gnomemusic.grilo import grilo
from gnomemusic.albumArtCache import AlbumArtCache
from gnomemusic.playlists import Playlists
from gnomemusic import log
import logging
logger = logging.getLogger(__name__)

playlists = Playlists.get_default()

try:
    tracker = Tracker.SparqlConnection.get(None)
except Exception as e:
    from sys import exit
    logger.error("Cannot connect to tracker, error '%s'\Exiting" % str(e))
    exit(1)

ALBUM_ART_CACHE = AlbumArtCache.get_default()
NOW_PLAYING_ICON_NAME = 'media-playback-start-symbolic'
ERROR_ICON_NAME = 'dialog-error-symbolic'


class AlbumWidget(Gtk.EventBox):

    tracks = []
    duration = 0
    symbolicIcon = ALBUM_ART_CACHE.get_default_icon(256, 256)

    @log
    def __init__(self, player):
        Gtk.EventBox.__init__(self)
        self.player = player
        self.iterToClean = None

        self.ui = Gtk.Builder()
        self.ui.add_from_resource('/org/gnome/Music/AlbumWidget.ui')
        self._create_model()
        self.view = Gd.MainView(
            shadow_type=Gtk.ShadowType.NONE
        )
        self.view.set_view_type(Gd.MainViewType.LIST)
        self.album = None
        self.header_bar = None
        self.view.connect('item-activated', self._on_item_activated)
        view_box = self.ui.get_object('view')
        self.ui.get_object('scrolledWindow').set_placement(Gtk.CornerType.
                                                           TOP_LEFT)
        self.view.connect('selection-mode-request', self._on_selection_mode_request)
        child_view = self.view.get_children()[0]
        child_view.set_margin_top(64)
        child_view.set_margin_bottom(64)
        child_view.set_margin_end(32)
        self.view.remove(child_view)
        view_box.add(child_view)
        self.add(self.ui.get_object('AlbumWidget'))
        self._add_list_renderers()
        # TODO: make this work
        self.get_style_context().add_class('view')
        self.get_style_context().add_class('content-view')
        self.show_all()

    @log
    def _on_selection_mode_request(self, *args):
        self.header_bar._select_button.clicked()

    @log
    def _on_item_activated(self, widget, id, path):
        _iter = self.model.get_iter(path)

        if(self.model.get_value(_iter, 7) != ERROR_ICON_NAME):
            if (self.iterToClean and self.player.playlistId == self.album):
                item = self.model.get_value(self.iterToClean, 5)
                title = AlbumArtCache.get_media_title(item)
                self.model.set_value(self.iterToClean, 0, title)
                # Hide now playing icon
                self.model.set_value(self.iterToClean, 6, False)
            self.player.set_playlist('Album', self.album, self.model, _iter, 5)
            self.player.set_playing(True)

    @log
    def _add_list_renderers(self):
        list_widget = self.view.get_generic_view()

        cols = list_widget.get_columns()
        cols[0].set_min_width(100)
        cols[0].set_max_width(200)
        cells = cols[0].get_cells()
        cells[2].set_visible(False)
        cells[1].set_visible(False)

        now_playing_symbol_renderer = Gtk.CellRendererPixbuf(xpad=0,
                                                             xalign=1.0,
                                                             yalign=0.5)

        column_now_playing = Gtk.TreeViewColumn()
        column_now_playing.set_fixed_width(24)
        column_now_playing.pack_start(now_playing_symbol_renderer, False)
        column_now_playing.add_attribute(now_playing_symbol_renderer,
                                         'visible', 9)
        column_now_playing.add_attribute(now_playing_symbol_renderer,
                                         'icon_name', 7)
        list_widget.insert_column(column_now_playing, 0)

        type_renderer = Gd.StyledTextRenderer(
            xpad=16,
            ellipsize=Pango.EllipsizeMode.END,
            xalign=0.0
        )
        list_widget.add_renderer(type_renderer, lambda *args: None, None)
        cols[0].clear_attributes(type_renderer)
        cols[0].add_attribute(type_renderer, 'markup', 0)

        durationRenderer = Gd.StyledTextRenderer(
            xpad=16,
            ellipsize=Pango.EllipsizeMode.END,
            xalign=1.0
        )
        durationRenderer.add_class('dim-label')
        list_widget.add_renderer(durationRenderer, lambda *args: None, None)
        cols[0].clear_attributes(durationRenderer)
        cols[0].add_attribute(durationRenderer, 'markup', 1)

    @log
    def _create_model(self):
        self.model = Gtk.ListStore(
            GObject.TYPE_STRING,  # title
            GObject.TYPE_STRING,
            GObject.TYPE_STRING,
            GObject.TYPE_STRING,
            GdkPixbuf.Pixbuf,    # icon
            GObject.TYPE_OBJECT,  # song object
            GObject.TYPE_BOOLEAN,  # item selected
            GObject.TYPE_STRING,
            GObject.TYPE_BOOLEAN,
            GObject.TYPE_BOOLEAN,  # icon shown
        )

    @log
    def update(self, artist, album, item, header_bar, selection_toolbar):
        self.selection_toolbar = selection_toolbar
        self.header_bar = header_bar
        self.album = album
        real_artist = item.get_string(Grl.METADATA_KEY_ARTIST)\
            or item.get_author()\
            or _("Unknown Artist")
        self.ui.get_object('cover').set_from_pixbuf(self.symbolicIcon)
        ALBUM_ART_CACHE.lookup(item, 256, 256, self._on_look_up, None, real_artist, album)

        # if the active queue has been set by self album,
        # use it as model, otherwise build the liststore
        cached_playlist = self.player.running_playlist('Album', album)
        if cached_playlist:
            self.model = cached_playlist
            currentTrack = self.player.playlist.get_iter(self.player.currentTrack.get_path())
            self.update_model(self.player, cached_playlist,
                              currentTrack)
        else:
            self.duration = 0
            self._create_model()
            GLib.idle_add(grilo.populate_album_songs, item, self.add_item)
        header_bar._select_button.connect(
            'toggled', self._on_header_select_button_toggled)
        header_bar._cancel_button.connect(
            'clicked', self._on_header_cancel_button_clicked)
        self.view.connect('view-selection-changed',
                          self._on_view_selection_changed)
        self.view.set_model(self.model)
        escaped_artist = GLib.markup_escape_text(artist)
        escaped_album = GLib.markup_escape_text(album)
        self.ui.get_object('artist_label').set_markup(escaped_artist)
        self.ui.get_object('title_label').set_markup(escaped_album)
        if (item.get_creation_date()):
            self.ui.get_object('released_label_info').set_text(
                str(item.get_creation_date().get_year()))
        else:
            self.ui.get_object('released_label_info').set_text('----')
        self.player.connect('playlist-item-changed', self.update_model)

    @log
    def _on_view_selection_changed(self, widget):
        items = self.view.get_selection()
        self.selection_toolbar\
            ._add_to_playlist_button.set_sensitive(len(items) > 0)
        if len(items) > 0:
            self.header_bar._selection_menu_label.set_text(
                ngettext("Selected %d item", "Selected %d items", len(items)) % len(items))
        else:
            self.header_bar._selection_menu_label.set_text(_("Click on items to select them"))

    @log
    def _on_header_cancel_button_clicked(self, button):
        self.view.set_selection_mode(False)
        self.header_bar.set_selection_mode(False)
        self.header_bar.header_bar.title = self.album

    @log
    def _on_header_select_button_toggled(self, button):
        if button.get_active():
            self.view.set_selection_mode(True)
            self.header_bar.set_selection_mode(True)
            self.player.actionbar.set_visible(False)
            self.selection_toolbar.actionbar.set_visible(True)
            self.selection_toolbar._add_to_playlist_button.set_sensitive(False)
            self.header_bar.header_bar.set_custom_title(self.header_bar._selection_menu_button)
        else:
            self.view.set_selection_mode(False)
            self.header_bar.set_selection_mode(False)
            self.header_bar.title = self.album
            self.selection_toolbar.actionbar.set_visible(False)
            if(self.player.get_playback_status() != 2):
                self.player.actionbar.set_visible(True)

    @log
    def _on_discovered(self, info, error, _iter):
        if error:
            self.model.set(_iter, [7, 9], [ERROR_ICON_NAME, True])

    @log
    def add_item(self, source, prefs, track, remaining, data=None):
        if track:
            self.tracks.append(track)
            self.duration = self.duration + track.get_duration()
            _iter = self.model.append()
            self.player.discover_item(track, self._on_discovered, _iter)
            escapedTitle = AlbumArtCache.get_media_title(track, True)
            self.model.set(_iter,
                           [0, 1, 2, 3, 4, 5, 7, 9],
                           [escapedTitle,
                            self.player.seconds_to_string(
                                track.get_duration()),
                            '', '', None, track, NOW_PLAYING_ICON_NAME,
                            False])
            self.ui.get_object('running_length_label_info').set_text(
                _("%d min") % (int(self.duration / 60) + 1))

    @log
    def _on_look_up(self, pixbuf, path, data=None):
        _iter = self.iterToClean
        if pixbuf:
            self.ui.get_object('cover').set_from_pixbuf(pixbuf)
            if _iter:
                self.model.set(_iter, [4], [pixbuf])

    @log
    def update_model(self, player, playlist, currentIter):
        # self is not our playlist, return
        if (playlist != self.model):
            return False
        currentSong = playlist.get_value(currentIter, 5)
        song_passed = False
        _iter = playlist.get_iter_first()
        self.duration = 0
        while _iter:
            song = playlist.get_value(_iter, 5)
            self.duration += song.get_duration()
            escapedTitle = AlbumArtCache.get_media_title(song, True)
            if (song == currentSong):
                title = '<b>%s</b>' % escapedTitle
                iconVisible = True
                song_passed = True
            elif (song_passed):
                title = '<span>%s</span>' % escapedTitle
                iconVisible = False
            else:
                title = '<span color=\'grey\'>%s</span>' % escapedTitle
                iconVisible = False
            playlist.set_value(_iter, 0, title)
            if(playlist.get_value(_iter, 7) != ERROR_ICON_NAME):
                playlist.set_value(_iter, 9, iconVisible)
            _iter = playlist.iter_next(_iter)
            self.ui.get_object('running_length_label_info').set_text(
                _("%d min") % (int(self.duration / 60) + 1))
        return False


class ArtistAlbums(Gtk.Box):

    @log
    def __init__(self, artist, albums, player,
                 header_bar, selection_toolbar, selectionModeAllowed=False):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.player = player
        self.artist = artist
        self.albums = albums
        self.selectionMode = False
        self.selectionModeAllowed = selectionModeAllowed
        self.selection_toolbar = selection_toolbar
        self.header_bar = header_bar
        self.ui = Gtk.Builder()
        self.ui.add_from_resource('/org/gnome/Music/ArtistAlbumsWidget.ui')
        self.set_border_width(0)
        self.ui.get_object('artist').set_label(self.artist)
        self.widgets = []

        self.model = Gtk.ListStore(GObject.TYPE_STRING,   # title
                                   GObject.TYPE_STRING,
                                   GObject.TYPE_STRING,
                                   GObject.TYPE_BOOLEAN,  # icon shown
                                   GObject.TYPE_STRING,   # icon
                                   GObject.TYPE_OBJECT,   # song object
                                   GObject.TYPE_BOOLEAN
                                   )
        self.model.connect('row-changed', self._model_row_changed)

        self._hbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._albumBox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                 spacing=48)
        self._scrolledWindow = Gtk.ScrolledWindow()
        self._scrolledWindow.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC)
        self._scrolledWindow.add(self._hbox)
        self._hbox.pack_start(self.ui.get_object('ArtistAlbumsWidget'),
                              False, False, 0)
        self._hbox.pack_start(self._albumBox, False, False, 16)
        self.pack_start(self._scrolledWindow, True, True, 0)

        for album in albums:
            self.add_album(album)

        self.show_all()
        self.player.connect('playlist-item-changed', self.update_model)

    @log
    def add_album(self, album):
        widget = ArtistAlbumWidget(
            self.artist, album, self.player, self.model,
            self.header_bar, self.selectionModeAllowed
        )
        self._albumBox.pack_start(widget, False, False, 0)
        self.widgets.append(widget)

    @log
    def update_model(self, player, playlist, currentIter):
        # this is not our playlist, return
        if playlist != self.model:
            # TODO, only clean once, but that can wait util we have clean
            # the code a bit, and until the playlist refactoring.
            # the overhead is acceptable for now
            self.clean_model()
            return False

        currentSong = playlist.get_value(currentIter, 5)
        song_passed = False
        itr = playlist.get_iter_first()

        while itr:
            song = playlist.get_value(itr, 5)
            song_widget = song.song_widget

            if not song_widget.can_be_played:
                itr = playlist.iter_next(itr)
                continue

            escapedTitle = AlbumArtCache.get_media_title(song, True)
            if (song == currentSong):
                song_widget.now_playing_sign.show()
                song_widget.title.set_markup('<b>%s</b>' % escapedTitle)
                song_passed = True
            elif (song_passed):
                song_widget.now_playing_sign.hide()
                song_widget.title.set_markup('<span>%s</span>' % escapedTitle)
            else:
                song_widget.now_playing_sign.hide()
                song_widget.title\
                    .set_markup('<span color=\'grey\'>%s</span>' % escapedTitle)
            itr = playlist.iter_next(itr)
        return False

    @log
    def clean_model(self):
        itr = self.model.get_iter_first()
        while itr:
            song = self.model.get_value(itr, 5)
            song_widget = song.song_widget
            escapedTitle = AlbumArtCache.get_media_title(song, True)
            if song_widget.can_be_played:
                song_widget.now_playing_sign.hide()
            song_widget.title.set_markup('<span>%s</span>' % escapedTitle)
            itr = self.model.iter_next(itr)
        return False

    @log
    def set_selection_mode(self, selectionMode):
        if self.selectionMode == selectionMode:
            return
        self.selectionMode = selectionMode
        for widget in self.widgets:
            widget.set_selection_mode(selectionMode)

    @log
    def _model_row_changed(self, model, path, _iter):
        if not self.selectionMode:
            return
        selected_items = 0
        for row in model:
            if row[6]:
                selected_items += 1
        self.selection_toolbar\
            ._add_to_playlist_button.set_sensitive(selected_items > 0)
        if selected_items > 0:
            self.header_bar._selection_menu_label.set_text(
                ngettext("Selected %d item", "Selected %d items", selected_items) % selected_items)
        else:
            self.header_bar._selection_menu_label.set_text(_("Click on items to select them"))


class AllArtistsAlbums(ArtistAlbums):

    @log
    def __init__(self, player, header_bar, selection_toolbar, selectionModeAllowed=False):
        ArtistAlbums.__init__(self, _("All Artists"), [], player,
                              header_bar, selection_toolbar, selectionModeAllowed)
        self._offset = 0
        self._populate()

    @log
    def _populate(self, data=None):
        if grilo.tracker:
            GLib.idle_add(grilo.populate_albums,
                          self._offset, self.add_item, -1)

    @log
    def add_item(self, source, param, item, remaining=0, data=None):
        if item:
            self._offset += 1
            self.add_album(item)


class ArtistAlbumWidget(Gtk.Box):

    pixbuf = AlbumArtCache.get_default().get_default_icon(128, 128)

    @log
    def __init__(self, artist, album, player, model, header_bar, selectionModeAllowed):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)
        self.player = player
        self.album = album
        self.artist = artist
        self.model = model
        self.model.connect('row-changed', self._model_row_changed)
        self.header_bar = header_bar
        self.selectionMode = False
        self.selectionModeAllowed = selectionModeAllowed
        self.songs = []
        self.ui = Gtk.Builder()
        self.ui.add_from_resource('/org/gnome/Music/ArtistAlbumWidget.ui')

        GLib.idle_add(self._update_album_art)

        self.ui.get_object('cover').set_from_pixbuf(self.pixbuf)
        self.ui.get_object('title').set_label(album.get_title())
        if album.get_creation_date():
            self.ui.get_object('year').set_markup(
                '<span color=\'grey\'>(%s)</span>' %
                str(album.get_creation_date().get_year())
            )
        self.tracks = []
        GLib.idle_add(grilo.populate_album_songs, album, self.add_item)
        self.pack_start(self.ui.get_object('ArtistAlbumWidget'), True, True, 0)
        self.show_all()

    @log
    def _on_discovered(self, info, error, song_widget):
        if error:
            self.model.set(song_widget._iter, [4], [ERROR_ICON_NAME])
            song_widget.now_playing_sign.set_from_icon_name(
                ERROR_ICON_NAME,
                Gtk.IconSize.SMALL_TOOLBAR)
            song_widget.now_playing_sign.show()
            song_widget.can_be_played = False

    @log
    def add_item(self, source, prefs, track, remaining, data=None):
        if track:
            self.tracks.append(track)
        else:
            for i, track in enumerate(self.tracks):
                ui = Gtk.Builder()
                ui.add_from_resource('/org/gnome/Music/TrackWidget.ui')
                song_widget = ui.get_object('eventbox1')
                self.songs.append(song_widget)
                ui.get_object('num')\
                    .set_markup('<span color=\'grey\'>%d</span>'
                                % len(self.songs))
                title = AlbumArtCache.get_media_title(track)
                ui.get_object('title').set_text(title)
                ui.get_object('title').set_alignment(0.0, 0.5)
                self.ui.get_object('grid1').attach(
                    song_widget,
                    int(i / (len(self.tracks) / 2)),
                    int(i % (len(self.tracks) / 2)), 1, 1
                )
                track.song_widget = song_widget
                itr = self.model.append(None)
                song_widget._iter = itr
                song_widget.model = self.model
                song_widget.title = ui.get_object('title')
                song_widget.checkButton = ui.get_object('select')
                song_widget.checkButton.set_visible(self.selectionMode)
                song_widget.checkButton.connect(
                    'toggled', self._check_button_toggled, song_widget
                )
                self.player.discover_item(track, self._on_discovered, song_widget)
                self.model.set(itr,
                               [0, 1, 2, 3, 4, 5],
                               [title, '', '', False,
                                NOW_PLAYING_ICON_NAME, track])
                song_widget.now_playing_sign = ui.get_object('image1')
                song_widget.now_playing_sign.set_from_icon_name(
                    NOW_PLAYING_ICON_NAME,
                    Gtk.IconSize.SMALL_TOOLBAR)
                song_widget.now_playing_sign.set_no_show_all('True')
                song_widget.now_playing_sign.set_alignment(1, 0.6)
                song_widget.can_be_played = True
                song_widget.connect('button-release-event',
                                    self.track_selected)
            self.ui.get_object('grid1').show_all()

    @log
    def _update_album_art(self):
        real_artist = self.album.get_string(Grl.METADATA_KEY_ARTIST)\
            or self.album.get_author()\
            or _("Unknown Artist")
        ALBUM_ART_CACHE.lookup(
            self.album, 128, 128, self._get_album_cover, None,
            real_artist, self.album.get_title())

    @log
    def _get_album_cover(self, pixbuf, path, data=None):
        if pixbuf:
            self.ui.get_object('cover').set_from_pixbuf(pixbuf)

    @log
    def track_selected(self, widget, event):
        if not widget.can_be_played:
            return

        if not self.selectionMode and \
            (event.button == Gdk.BUTTON_SECONDARY or
                (event.button == 1 and event.state & Gdk.ModifierType.CONTROL_MASK)):
            if self.selectionModeAllowed:
                self.header_bar._select_button.set_active(True)
            else:
                return

        if self.selectionMode:
            self.model[widget._iter][6] = not self.model[widget._iter][6]
            return

        self.player.stop()
        self.player.set_playlist('Artist', self.artist,
                                 widget.model, widget._iter, 5)
        self.player.set_playing(True)

    @log
    def set_selection_mode(self, selectionMode):
        if self.selectionMode == selectionMode:
            return
        self.selectionMode = selectionMode
        for songWidget in self.songs:
            songWidget.checkButton.set_visible(selectionMode)
            if not selectionMode:
                songWidget.model[songWidget._iter][6] = False

    @log
    def _check_button_toggled(self, button, songWidget):
        if songWidget.model[songWidget._iter][6] != button.get_active():
            songWidget.model[songWidget._iter][6] = button.get_active()

    @log
    def _model_row_changed(self, model, path, _iter):
        if not self.selectionMode:
            return
        if not model[_iter][5]:
            return
        songWidget = model[_iter][5].song_widget
        selected = model[_iter][6]
        if selected != songWidget.checkButton.get_active():
            songWidget.checkButton.set_active(selected)


class PlaylistWidget(Gtk.Box):
    if Gtk.Widget.get_default_direction() is not Gtk.TextDirection.RTL:
        nowPlayingIconName = 'media-playback-start-symbolic'
    else:
        nowPlayingIconName = 'media-playback-start-rtl-symbolic'
    errorIconName = 'dialog-error-symbolic'
    starIconName = 'starred-symbolic'

    @log
    def __init__(self, player, header_bar, selection_toolbar):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        self.model = Gtk.ListStore(
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
        self.view.set_view_type(Gd.MainViewType.LIST)
        self.view.set_model(self.model)
        self.view.get_generic_view().get_style_context()\
            .add_class('songs-list')
        self.view.connect('item-activated', self._on_item_activated)
        self.view.connect('selection-mode-request',
                          self._on_selection_mode_request)
        self.view.connect('view-selection-changed',
                          self._on_view_selection_changed)
        self._add_list_renderers()

        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Music/PlaylistControls.ui')

        self.headerbar = builder.get_object('grid')
        self.nameLabel = builder.get_object('playlist_name')
        self.songsCountLabel = builder.get_object('songs_count')
        self.menubutton = builder.get_object('playlist_menubutton')

        self.playMenuitem = builder.get_object('menuitem_play')
        self.playMenuitem.connect('activate', self._on_play_activate)
        self.deleteMenuitem = builder.get_object('menuitem_delete')
        self.deleteMenuitem.connect('activate', self._on_delete_activate)

        self.add(self.headerbar)
        self.add(self.view)

        self.playlist = None
        self.player = player
        self.header_bar = header_bar
        self.selection_toolbar = selection_toolbar
        self.iterToClean = None
        self.iterToCleanModel = None
        self.songsCount = 0

        playlists.connect('song-added-to-playlist', self._on_song_added_to_playlist)
        playlists.connect('song-removed-from-playlist', self._on_song_removed_from_playlist)

        self.player.connect('playlist-item-changed', self.update_model)

    @log
    def update(self, playlist):
        if self.playlist == playlist:
            return

        playlistName = AlbumArtCache.get_media_title(playlist)
        self.playlist = playlist
        self.nameLabel.set_text(playlistName)

        # if the active queue has been set by this playlist,
        # use it as model, otherwise build the liststore
        cachedPlaylist = self.player.running_playlist('Playlist', playlist.get_id())
        if cachedPlaylist:
            self.model = cachedPlaylist
            currentTrack = self.player.playlist.get_iter(self.player.currentTrack.get_path())
            self.update_model(self.player, cachedPlaylist,
                              currentTrack)
            self.view.set_model(self.model)
            self.songsCount = self.model.iter_n_children(None)
            self._update_songs_count()
        else:
            self.model = Gtk.ListStore(
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
            self.view.set_model(self.model)
            GLib.idle_add(grilo.populate_playlist_songs, playlist, self._add_item)
            self.songsCount = 0
            self._update_songs_count()

    @log
    def _add_list_renderers(self):
        list_widget = self.view.get_generic_view()
        cols = list_widget.get_columns()
        cells = cols[0].get_cells()
        cells[2].set_visible(False)
        now_playing_symbol_renderer = Gtk.CellRendererPixbuf(xalign=1.0)

        columnNowPlaying = Gtk.TreeViewColumn()
        columnNowPlaying.set_property('fixed_width', 24)
        columnNowPlaying.pack_start(now_playing_symbol_renderer, False)
        columnNowPlaying.add_attribute(now_playing_symbol_renderer,
                                       'visible', 10)
        columnNowPlaying.add_attribute(now_playing_symbol_renderer,
                                       'icon_name', 8)
        list_widget.insert_column(columnNowPlaying, 0)

        titleRenderer = Gtk.CellRendererText(
            xpad=0,
            xalign=0.0,
            yalign=0.5,
            height=48,
            ellipsize=Pango.EllipsizeMode.END
        )
        list_widget.add_renderer(titleRenderer, lambda *args: None, None)
        cols[0].add_attribute(titleRenderer, 'text', 2)

        starRenderer = Gtk.CellRendererPixbuf(
            xpad=32,
            icon_name=self.starIconName
        )
        list_widget.add_renderer(starRenderer, lambda *args: None, None)
        cols[0].add_attribute(starRenderer, 'visible', 9)

        durationRenderer = Gd.StyledTextRenderer(
            xpad=32,
            xalign=1.0
        )
        durationRenderer.add_class('dim-label')
        list_widget.add_renderer(durationRenderer,
                                 self._on_list_widget_duration_render, None)

        artistRenderer = Gd.StyledTextRenderer(
            xpad=32,
            ellipsize=Pango.EllipsizeMode.END
        )
        artistRenderer.add_class('dim-label')
        list_widget.add_renderer(artistRenderer, lambda *args: None, None)
        cols[0].add_attribute(artistRenderer, 'text', 3)

        albumRenderer = Gd.StyledTextRenderer(
            xpad=32,
            ellipsize=Pango.EllipsizeMode.END
        )
        albumRenderer.add_class('dim-label')
        list_widget.add_renderer(albumRenderer,
                                 self._on_list_widget_album_render, None)

    def _on_list_widget_duration_render(self, col, cell, model, _iter, data):
        item = model.get_value(_iter, 5)
        if item:
            seconds = item.get_duration()
            minutes = seconds // 60
            seconds %= 60
            cell.set_property('text', '%i:%02i' % (minutes, seconds))

    def _on_list_widget_album_render(self, coll, cell, model, _iter, data):
        item = model.get_value(_iter, 5)
        if item:
            cell.set_property(
                'text',
                item.get_string(Grl.METADATA_KEY_ALBUM) or _("Unknown Album")
            )

    @log
    def update_model(self, player, playlist, currentIter):
        if self.iterToClean:
            self.iterToCleanModel.set_value(self.iterToClean, 10, False)
        if playlist != self.model:
            return False

        self.model.set_value(currentIter, 10, True)
        if self.model.get_value(currentIter, 8) != self.errorIconName:
            self.iterToClean = currentIter.copy()
            self.iterToCleanModel = self.model
        return False

    @log
    def _on_item_activated(self, widget, id, path):
        _iter = self.model.get_iter(path)
        if self.model.get_value(_iter, 8) != self.errorIconName:
            self.player.set_playlist(
                'Playlist', self.playlist.get_id(),
                self.model, _iter, 5
            )
            self.player.set_playing(True)

    @log
    def _add_item(self, source, param, item, remaining=0, data=None):
        self._add_item_to_model(item, self.model)

    @log
    def _add_item_to_model(self, item, model):
        if not item:
            return
        title = AlbumArtCache.get_media_title(item)
        item.set_title(title)
        artist = item.get_string(Grl.METADATA_KEY_ARTIST)\
            or item.get_author()\
            or _("Unknown Artist")
        _iter = model.insert_with_valuesv(
            -1,
            [2, 3, 5, 8, 9, 10],
            [title, artist, item, self.nowPlayingIconName, False, False])
        self.player.discover_item(item, self._on_discovered, _iter)
        self.songsCount += 1
        self._update_songs_count()

    @log
    def _on_discovered(self, info, error, _iter):
        if error:
            print("Info %s: error: %s" % (info, error))
            self.model.set(_iter, [8, 10], [self.errorIconName, True])

    @log
    def _update_songs_count(self):
        self.songsCountLabel.set_text(
            ngettext("%d Song", "%d Songs", self.songsCount)
            % self.songsCount)

    @log
    def set_selection_mode(self, selectionMode):
        self.menubutton.set_sensitive(not selectionMode)
        self.view.set_selection_mode(selectionMode)

    @log
    def _on_selection_mode_request(self, *args):
        self.header_bar._select_button.clicked()

    @log
    def _on_view_selection_changed(self, widget):
        items = self.view.get_selection()
        self.selection_toolbar\
            ._remove_from_playlist_button.set_sensitive(len(items) > 0)
        if len(items) > 0:
            self.header_bar._selection_menu_label.set_text(
                ngettext("Selected %d item", "Selected %d items", len(items)) % len(items))
        else:
            self.header_bar._selection_menu_label.set_text(_("Click on items to select them"))

    @log
    def _on_play_activate(self, menuitem, data=None):
        _iter = self.model.get_iter_first()
        if not _iter:
            return

        self.view.get_generic_view().get_selection().\
            select_path(self.model.get_path(_iter))
        self.view.emit('item-activated', '0',
                       self.model.get_path(_iter))

    @log
    def _on_delete_activate(self, menuitem, data=None):
        self.model.clear()
        playlists.delete_playlist(self.playlist)

    @log
    def _on_song_added_to_playlist(self, playlists, playlist, item):
        if self.playlist and \
           playlist.get_id() == self.playlist.get_id():
            self._add_item_to_model(item, self.model)
        else:
            cachedPlaylist = self.player.running_playlist(
                'Playlist', playlist.get_id()
            )
            if cachedPlaylist and cachedPlaylist != self.model:
                self._add_item_to_model(item, cachedPlaylist)

    @log
    def _on_song_removed_from_playlist(self, playlists, playlist, item):
        cachedPlaylist = self.player.running_playlist(
            'Playlist', playlist.get_id()
        )
        if self.playlist and \
           playlist.get_id() == self.playlist.get_id():
            model = self.model
        elif cachedPlaylist and cachedPlaylist != self.model:
            model = cachedPlaylist
        else:
            return

        update_playing_track = False
        for row in model:
            if row[5].get_id() == item.get_id():
                # Is the removed track now being played?
                if self.playlist and \
                   playlist.get_id() == self.playlist.get_id() and \
                   cachedPlaylist == model:
                    if self.player.currentTrack is not None:
                        currentTrackpath = self.player.currentTrack.get_path().to_string()
                        if row.path is not None and row.path.to_string() == currentTrackpath:
                            update_playing_track = True

                nextIter = model.iter_next(row.iter)
                model.remove(row.iter)

                # Reload the model and switch to next song
                if update_playing_track:
                    if nextIter is None:
                        # Get first track if next track is not valid
                        nextIter = model.get_iter_first()
                        if nextIter is None:
                            # Last track was removed
                            return

                    self.iterToClean = None
                    self.update_model(self.player, model, nextIter)
                    self.player.set_playlist('Playlist', playlist.get_id(), model, nextIter, 5)
                    self.player.set_playing(True)

                # Update songs count
                self.songsCount -= 1
                self._update_songs_count()
                return

    @log
    def get_selected_tracks(self, callback):
        callback([self.model.get_value(self.model.get_iter(path), 5)
                  for path in self.view.get_selection()])


class PlaylistDialog():
    @log
    def __init__(self, parent):
        self.ui = Gtk.Builder()
        self.ui.add_from_resource('/org/gnome/Music/PlaylistDialog.ui')
        self.dialogBox = self.ui.get_object('dialog1')
        self.dialogBox.set_transient_for(parent)

        self.list = self.ui.get_object('listbox')
        self.list.connect('row-activated', self._on_row_activated)

        self.addNewRow = self.ui.get_object('listboxrow-new')
        self.addNewRow.media = None
        self.addNewRow.label = self.ui.get_object('label-new')
        self.addNewRow.entry = self.ui.get_object('entry-new')
        self.addNewRow.entry.connect('activate', self._on_entry_activated)

        self.populate()

        headerBar = self.ui.get_object('headerbar1')
        self.dialogBox.set_titlebar(headerBar)

        self.cancelButton = self.ui.get_object('cancel-button')
        self.cancelButton.connect('clicked', self._on_cancel)
        self.selectButton = self.ui.get_object('select-button')
        self.selectButton.connect('clicked', self._on_select)

        playlists.connect('playlist-created', self._on_playlist_created)

    @log
    def get_selected(self):
        row = self.list.get_selected_row()
        return row and row.media

    @log
    def populate(self):
        if grilo.tracker:
            GLib.idle_add(grilo.populate_playlists, 0, self._add_item)

    @log
    def _add_item(self, source, param, item, remaining=0, data=None):
        if not item:
            return

        newRow = self._add_row(item)
        if self.addNewRow.get_index() == 1:
            self.list.select_row(newRow)

    @log
    def _add_row(self, item):
        row = Gtk.ListBoxRow()
        row.media = item
        row.show()
        self.list.insert(row, self.addNewRow.get_index())

        row.label = Gtk.Label(margin_start=20, margin_end=20,
                              margin_top=6, margin_bottom=6,
                              xalign=0,
                              label=AlbumArtCache.get_media_title(item))
        row.label.show()
        row.add(row.label)

        return row

    @log
    def _on_select(self, select_button):
        self.dialogBox.response(Gtk.ResponseType.ACCEPT)

    @log
    def _on_cancel(self, cancel_button):
        self.dialogBox.response(Gtk.ResponseType.REJECT)

    @log
    def _on_row_activated(self, listbox, row):
        self.selectButton.set_sensitive(row.media is not None)
        self.addNewRow.label.set_visible(row.media is not None)
        self.addNewRow.entry.set_visible(row.media is None)
        if row.media is None:
            self.addNewRow.entry.grab_focus()

    @log
    def _on_entry_activated(self, entry, data=None):
        playlistName = entry.get_text()
        if playlistName == '':
            return

        existsRow = None
        for row in self.list.get_children():
            if row.media and \
                    AlbumArtCache.get_media_title(row.media) == playlistName:
                existsRow = row
                break

        if existsRow:
            self.list.select_row(existsRow)
        else:
            playlists.create_playlist(playlistName)

        self.addNewRow.label.set_visible(True)
        self.addNewRow.entry.set_visible(False)
        self.addNewRow.entry.set_text('')

    @log
    def _on_playlist_created(self, playlists, item):
        newRow = self._add_row(item)
        self.list.select_row(newRow)
