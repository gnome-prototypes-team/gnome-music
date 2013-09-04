from gi.repository import TotemPlParser, GLib, Gio

import os


class Playlists:
    instance = None

    @classmethod
    def get_default(self):
        if self.instance:
            return self.instance
        else:
            self.instance = Playlists()
        return self.instance

    def __init__(self):
        self.playlist_dir = os.path.join(GLib.get_user_data_dir(),
                                         'gnome-music',
                                         'playlists')

    def create_playlist(self, name, iterlist=None):
        parser = TotemPlParser.Parser()
        playlist = TotemPlParser.Playlist()
        pl_file = Gio.file_new_for_path(self.get_path_to_playlist(name))
        if iterlist is not None:
            for _iter in iterlist:
                pass
        else:
            _iter = TotemPlParser.PlaylistIter()
            playlist.append(_iter)
        parser.save(playlist, pl_file, name, TotemPlParser.ParserType.PLS)
        return False

    def get_playlists(self):
        playlist_files = [pl_file for pl_file in os.listdir(self.playlist_dir)
                          if os.path.isfile(os.path.join(self.playlist_dir,
                                                         pl_file))]
        playlist_names = []
        for playlist_file in playlist_files:
            name, ext = os.path.splitext(playlist_file)
            playlist_names.append(name)
        return playlist_names

    def add_to_playlist(self, playlist_name):
        pass

    def delete_playlist(self, playlist_name):
        pass

    def get_path_to_playlist(self, playlist_name):
        return os.path.join(self.playlist_dir, playlist_name + ".pls")
