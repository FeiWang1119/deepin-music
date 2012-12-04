#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2011~2012 Deepin, Inc.
#               2011~2012 Hou Shaohui
#
# Author:     Hou Shaohui <houshao55@gmail.com>
# Maintainer: Hou ShaoHui <houshao55@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gobject
import gtk
import threading
from dtk.ui.draw import draw_pixbuf
from dtk.ui.utils import get_optimum_pixbuf_from_file
from dtk.ui.timeline import Timeline, CURVE_SINE


from player import Player
from cover_manager import CoverManager, COVER_SIZE
from widget.skin import app_theme
from helper import Dispatcher


class CoverButton(gtk.Button):
    def __init__(self):
        super(CoverButton, self).__init__()
        
        self.current_cover_pixbuf = CoverManager.get_default_cover(COVER_SIZE["x"], COVER_SIZE["y"])
        self.cover_side_pixbuf = app_theme.get_pixbuf("cover/side.png").get_pixbuf()
        self.set_size_request(self.cover_side_pixbuf.get_width(), self.cover_side_pixbuf.get_height())
        
        self.webcast_dpixbuf = app_theme.get_pixbuf("cover/webcast.png")

        self.connect("expose-event", self.expose_button_cb)
        # MediaDB.connect("simple-changed", self.update_cover)
        Dispatcher.connect("album-changed", self.on_album_changed)
        
        
        self.current_song = None
        self.next_cover_to_download = None
        
        self.condition = threading.Condition()
        self.thread = threading.Thread(target=self.func_thread)
        self.thread.setDaemon(True)
        self.thread.start()
        
        # animation params.
        self.active_alpha = 1.0
        self.target_alpha = 0.0
        self.in_animation = False
        self.animation_time = 1500
        self.active_pixbuf = self.current_cover_pixbuf
        self.target_pixbuf = None
        
    def start_animation(self, target_pixbuf):    
        self.target_pixbuf = target_pixbuf
        if not self.in_animation:
            self.in_animation = False
            try:
                self.timeline.stop()
            except:    
                pass
            self.timeline = Timeline(self.animation_time, CURVE_SINE)
            self.timeline.connect("update", self.update_animation)
            self.timeline.connect("completed", lambda source: self.completed_animation(source, target_pixbuf))
            self.timeline.run()
    
    def update_animation(self, source, status):
        self.active_alpha = 1.0 - status
        self.target_alpha = status
        self.queue_draw()
    
    def completed_animation(self, source, target_pixbuf):    
        self.active_pixbuf = target_pixbuf
        self.active_alpha = 1.0
        self.target_alpha = 0.0
        self.in_animation = False
        self.queue_draw()
        
    def expose_button_cb(self, widget, event):    
        cr = widget.window.cairo_create()
        rect = widget.allocation
        
        # Draw cover side.
        draw_pixbuf(cr, self.cover_side_pixbuf, rect.x, rect.y)
        
        if Player.song:
            if Player.song.get_type() == "webcast":
                self.active_pixbuf = self.webcast_dpixbuf.get_pixbuf()
        
        draw_pixbuf(cr, self.active_pixbuf, rect.x + 4, rect.y + 4,
                    self.active_alpha)
        
        if self.target_pixbuf:
            draw_pixbuf(cr, self.target_pixbuf, rect.x + 4, rect.y + 4, self.target_alpha)
        return True
        
        
    def func_thread(self):    
        while True:
            self.condition.acquire()
            while not self.next_cover_to_download:
                self.condition.wait()
            next_cover_to_download = self.next_cover_to_download    
            self.next_cover_to_download = None
            self.condition.release()
            self.set_current_cover(True, next_cover_to_download)

    def update_default_cover(self, widget, song):            
        if not self.current_song or CoverManager.get_cover_search_str(self.current_song) != CoverManager.get_cover_search_str(song):
            pixbuf = CoverManager.get_pixbuf_from_name("", COVER_SIZE["x"], COVER_SIZE["y"])
            self.active_pixbuf = pixbuf
            self.queue_draw()
            self.start_animation(pixbuf)
            
    def init_default_cover(self):        
        pixbuf = CoverManager.get_pixbuf_from_name("", COVER_SIZE["x"], COVER_SIZE["y"])
        self.start_animation(pixbuf)
        
    def on_album_changed(self, obj, song):    
        if song == self.current_song:
            self.update_cover(None, song)
            
            
    def update_cover(self, widget, song):        
        self.current_song = song
        
        if self.current_song is not None:        
            if not self.set_current_cover(False):
                self.condition.acquire()
                self.next_cover_to_download = self.current_song
                self.condition.notify()
                self.condition.release()
                
    def set_current_cover(self, try_web=True, force_song=None):            
        if not force_song:
            force_song = self.current_song
        filename = CoverManager.get_cover(force_song, try_web)    
        
        if Player.song != force_song:
            return
        try:
            pixbuf = get_optimum_pixbuf_from_file(filename, COVER_SIZE["x"], COVER_SIZE["y"])
        except gobject.GError:    
            pass
        else:
            self.start_animation(pixbuf)
            if not try_web:
                return CoverManager.default_cover != filename

            
class PlayerCoverButton(CoverButton):    
    def __init__(self):
        super(PlayerCoverButton, self).__init__()
        Player.connect("new-song", self.update_cover)
        Player.connect("init-status", lambda w : self.init_default_cover())
        Player.connect("instant-new-song", self.instant_update_cover)
        
    def instant_update_cover(self, widget, song):    
        if not CoverManager.get_cover(song, False):
            self.update_default_cover(widget, song)
        else:    
            self.update_cover(widget, song)
