#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
  Copyright (C) 2016-2018, Douglas Vinicius
  douglvini@gmail.com

  Distributed under the terms of GNU GPL v3 (or lesser GPL) license.

Fanim is an extention for GIMP thats implements a simple timeline that can
be used to play in sequence and manipulate layers that works as each frame of an 
frame by frame animation.

  Adapted to Python 3 / GTK3 by Charlie Martínez - Quirinux GNU/Linux.
"""

from gimpfu import register, main, gimp, pdb, \
        TRANSPARENT_FILL, RGBA_IMAGE, NORMAL_MODE

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf

import array, time, os, json

# general info
VERSION = 1.16
AUTHORS = ["Douglas Vinicius <douglvini@gmail.com>"]
NAME = "FAnim Timeline " + str(VERSION)
WINDOW_TITLE = ("GIMP %s " % NAME) + "[%s]"
COPYRIGHT = "Copyright (C) 2016-2019 \nDouglas Vinicius"
WEBSITE = "https://github.com/douglasvini/gimp-fanim"
YEAR = "2016-2019"
DESCRIPTION = "Timeline to edit frames and play animations with some aditional functionality."
GIMP_LOCATION = "<Image>/FAnim/FAnim Timeline"

# fixed frames prefix in the end to store visibility fix for the playback understand.
PREFIX = "_fix"

# playback macros
NEXT = 1
PREV = 2
END = 3
START = 4
NOWHERE = 5
POS = 6
GIMP_ACTIVE = 7

# settings constant macros
WIN_WIDTH = "win_width"
WIN_HEIGHT = "win_height"
WIN_POSX = "win_posx"
WIN_POSY = "win_posy"
FRAMERATE = "framerate"
OSKIN_DEPTH = "oskin_depth"
OSKIN_ONPLAY = "oskin_onplay"
OSKIN_FORWARD = "oskin_forward"
OSKIN_BACKWARD = "oskin_backward"

# state to disable the buttons
PLAYING = 1
NO_FRAMES = 2

# onionskin constants
OSKIN_MAX_DEPTH = 6
OSKIN_MAX_OPACITY = 50.0

CONF_FILENAME = "conf.json"


class Utils:

    @staticmethod
    def add_fixed_prefix(layer):
        if Utils.is_frame_fixed(layer):
            return
        layer.name = layer.name + PREFIX

    @staticmethod
    def rem_fixed_prefix(layer):
        if not Utils.is_frame_fixed(layer):
            return
        layer.name = layer.name[:-4]

    @staticmethod
    def is_frame_fixed(layer):
        name = layer.name
        return name[-4:] == PREFIX

    @staticmethod
    def button_stock(stock, size):
        """Return a button with an image from a named icon."""
        b = Gtk.Button()
        img = Gtk.Image.new_from_icon_name(stock, size)
        b.set_image(img)
        return b

    @staticmethod
    def toggle_button_stock(stock, size):
        """Return a ToggleButton with an image from a named icon."""
        b = Gtk.ToggleButton()
        img = Gtk.Image.new_from_icon_name(stock, size)
        b.set_image(img)
        return b

    @staticmethod
    def spin_button(name="variable", number_type="int", value=0, min=1, max=100, advance=1):
        adjustment = Gtk.Adjustment(value=value, lower=min, upper=max,
                                    step_increment=advance, page_increment=advance)
        digits = 0
        if number_type != "int":
            digits = 3
        l = Gtk.Label(label=name)
        b = Gtk.SpinButton(adjustment=adjustment, climb_rate=0, digits=digits)

        h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        h.pack_start(l, True, True, 0)
        h.pack_start(b, True, True, 0)
        return h, adjustment

    @staticmethod
    def load_conffile(filename):
        directory = gimp.directory + "/fanim"
        if not os.path.exists(directory):
            os.mkdir(directory)

        filepath = directory + "/" + filename
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                dic = json.load(f)
            return dic
        else:
            return None

    @staticmethod
    def save_conffile(filename, conf={}):
        directory = gimp.directory + "/fanim"
        if not os.path.exists(directory):
            os.mkdir(directory)

        filepath = directory + "/" + filename
        with open(filepath, 'w') as f:
            json.dump(conf, f)


class ConfDialog(Gtk.Dialog):
    """Configuration dialog."""

    def __init__(self, title="Config", parent=None, config=None):
        super().__init__(title=title, parent=parent,
                         flags=Gtk.DialogFlags.DESTROY_WITH_PARENT)
        self.add_buttons("Apply", Gtk.ResponseType.APPLY,
                         "Cancel", Gtk.ResponseType.CANCEL)

        self.set_keep_above(True)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.last_config = config
        self.atual_config = dict(config)  # copy to avoid mutating original

        self._setup_widgets()

    def update_config(self, widget, var_type=None):
        if isinstance(widget, Gtk.Adjustment):
            value = widget.get_value()
        elif isinstance(widget, Gtk.CheckButton):
            value = widget.get_active()
        self.atual_config[var_type] = value

    def _setup_widgets(self):
        h_space = 4

        f_time = Gtk.Frame(label="Time")
        f_oskin = Gtk.Frame(label="Onion Skin")
        self.set_size_request(300, -1)

        content = self.get_content_area()
        content.pack_start(f_time, True, True, h_space)
        content.pack_start(f_oskin, True, True, h_space)

        # Time settings
        th = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        fps, fps_spin = Utils.spin_button("Framerate", 'int',
                                          self.last_config[FRAMERATE], 1, 100)
        th.pack_start(fps, True, True, h_space)
        f_time.add(th)

        # Onion skin settings
        ov = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        f_oskin.add(ov)

        oh1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        depth, depth_spin = Utils.spin_button("Depth", 'int',
                                              self.last_config[OSKIN_DEPTH],
                                              1, OSKIN_MAX_DEPTH, 1)
        on_play = Gtk.CheckButton(label="On Play")
        on_play.set_active(self.last_config[OSKIN_ONPLAY])

        oh1.pack_start(depth, True, True, h_space)
        oh1.pack_start(on_play, True, True, h_space)
        ov.pack_start(oh1, True, True, 0)

        oh2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        forward = Gtk.CheckButton(label="Forward")
        forward.set_active(self.last_config[OSKIN_FORWARD])
        backward = Gtk.CheckButton(label="Backward")
        backward.set_active(self.last_config[OSKIN_BACKWARD])

        oh2.pack_start(forward, True, True, h_space)
        oh2.pack_start(backward, True, True, h_space)
        ov.pack_start(oh2, True, True, 0)

        # Connect callbacks
        fps_spin.connect("value_changed", self.update_config, FRAMERATE)
        depth_spin.connect("value_changed", self.update_config, OSKIN_DEPTH)
        on_play.connect("toggled", self.update_config, OSKIN_ONPLAY)
        forward.connect("toggled", self.update_config, OSKIN_FORWARD)
        backward.connect("toggled", self.update_config, OSKIN_BACKWARD)

        self.show_all()

    def run(self):
        result = super().run()
        conf = self.last_config

        if result == Gtk.ResponseType.APPLY:
            conf = self.atual_config

        return result, conf


class Player():
    """Loop to play frames in sequence without freezing the UI."""

    def __init__(self, timeline, play_button):
        self.timeline = timeline
        self.play_button = play_button
        self.cnt = 0

    def start(self):
        while self.timeline.is_playing:
            self.timeline.on_goto(None, NEXT)

            # skip fixed frames
            while (self.timeline.frames[self.timeline.active].fixed and
                   self.timeline.active < len(self.timeline.frames)):
                self.timeline.on_goto(None, NEXT)

            if (not self.timeline.is_replay and
                    self.timeline.active == len(self.timeline.frames) - 1):
                self.timeline.on_toggle_play(self.play_button)

            time.sleep(1.0 / self.timeline.framerate)

            # process pending GTK events
            while Gtk.events_pending():
                Gtk.main_iteration()


class AnimFrame(Gtk.EventBox):
    """A frame representation widget for GTK."""

    def __init__(self, layer, width=100, height=120):
        super().__init__()
        self.set_size_request(width, height)

        self.thumbnail = None
        self.label = None
        self.layer = layer
        self.fixed = False

        self._fix_button_images = []
        self._fix_button = None
        self._setup()

    def highlight(self, state):
        if state:
            self.set_state_flags(Gtk.StateFlags.SELECTED, True)
        else:
            self.set_state_flags(Gtk.StateFlags.NORMAL, True)

    def on_toggle_fix(self, widget):
        self.fixed = widget.get_active()
        if widget.get_active():
            Utils.add_fixed_prefix(self.layer)
            self._fix_button.set_image(self._fix_button_images[0])
        else:
            Utils.rem_fixed_prefix(self.layer)
            self._fix_button.set_image(self._fix_button_images[1])

    def _setup(self):
        self.thumbnail = Gtk.Image()
        self.label = Gtk.Label(label=self.layer.name)

        icon_size = Gtk.IconSize.MENU

        # GTK3 uses icon names instead of stock items
        self._fix_button = Gtk.ToggleButton()
        img_no = Gtk.Image.new_from_icon_name("dialog-no", icon_size)
        self._fix_button.set_image(img_no)
        self._fix_button.set_tooltip_text("toggle fixed visibility.")

        self.fixed = Utils.is_frame_fixed(self.layer)

        img_yes = Gtk.Image.new_from_icon_name("dialog-yes", icon_size)
        img_no2 = Gtk.Image.new_from_icon_name("dialog-no", icon_size)
        self._fix_button_images = [img_yes, img_no2]

        self._fix_button.connect('clicked', self.on_toggle_fix)

        if self.fixed:
            self._fix_button.set_image(self._fix_button_images[0])
            self._fix_button.set_active(True)
        else:
            self._fix_button.set_image(self._fix_button_images[1])
            self._fix_button.set_active(False)

        frame = Gtk.Frame()
        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.add(frame)
        frame.add(layout)

        layout.pack_start(self.label, False, False, 0)
        layout.pack_start(self.thumbnail, False, False, 0)
        layout.pack_start(self._fix_button, False, False, 0)
        self._get_thumb_image()

    def _get_thumb_image(self):
        width = 100
        height = 100
        image_data = pdb.gimp_drawable_thumbnail(self.layer, width, height)

        w, h, c, data = (image_data[0], image_data[1],
                         image_data[2], image_data[4])

        # data is already bytes in Python 3
        image_array = array.array('B', data)

        has_alpha = c > 3
        colorspace = GdkPixbuf.Colorspace.RGB
        pixbuf = GdkPixbuf.Pixbuf.new_from_data(
            image_array.tobytes(), colorspace, has_alpha, 8, w, h, w * c)
        self.thumbnail.set_from_pixbuf(pixbuf)

    def update_layer_info(self):
        self._get_thumb_image()


class Timeline(Gtk.Window):

    def __init__(self, title, image):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)

        self.set_title(title)
        self.image = image
        self.frame_bar = None

        self.is_playing = False
        self.is_replay = False

        self.play_button_images = []
        self.widgets_to_disable = []
        self.play_bar = None

        self.frames = []
        self.active = None
        self.before_play = None

        self.framerate = 30
        self.new_layer_type = TRANSPARENT_FILL

        self.oskin = False
        self.oskin_depth = 2
        self.oskin_backward = True
        self.oskin_forward = False
        self.oskin_max_opacity = OSKIN_MAX_OPACITY
        self.oskin_onplay = True

        self.player = None

        self.win_pos = (20, 20)
        self.win_size = (200, 200)

        self._setup_widgets()

    def undo(self, state):
        if state:
            self.image.undo_thaw()
        else:
            self.image.undo_freeze()

    def destroy(self, widget):
        if self.is_playing:
            self.is_playing = False
            gimp.message("Please do not close the image with FAnim playing the animation.")
        if widget is not False:
            pdb.script_fu_reverse_layers(self.image, None)
            self.on_goto(None, START)

        Utils.save_conffile(CONF_FILENAME, self.get_settings())
        Gtk.main_quit()

    def start(self):
        Gtk.main()

    def _get_theme_gtkrc(self, themerc):
        rcpath = ""
        with open(themerc, 'r') as trc:
            for l in trc.readlines():
                if l[:7] == "include":
                    rcpath = l[9:-2]
                    break
        return rcpath

    def on_window_resize(self, *args):
        self.win_pos = self.get_position()

    def _setup_widgets(self):
        self.set_settings(Utils.load_conffile(CONF_FILENAME))

        self.connect("destroy", self.destroy)
        self.connect("focus_in_event", self.on_window_focus)
        self.connect("configure_event", self.on_window_resize)

        self.set_default_size(self.win_size[0], self.win_size[1])
        self.set_keep_above(True)
        self.move(self.win_pos[0], self.win_pos[1])

        # Apply GIMP theme (GTK3: use CSS provider instead of rc_parse)
        try:
            gtkrc_path = self._get_theme_gtkrc(gimp.personal_rc_file('themerc'))
            if os.name != 'nt' and gtkrc_path:
                from gi.repository import Gdk
                css_provider = Gtk.CssProvider()
                # GTK3 can't parse GTK2 rc files directly; silently skip on error
                try:
                    css_provider.load_from_path(gtkrc_path)
                    Gtk.StyleContext.add_provider_for_screen(
                        Gdk.Screen.get_default(),
                        css_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_USER)
                except Exception:
                    pass
        except Exception:
            pass

        base = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        cbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        cbar.pack_start(self._setup_playbackbar(), False, False, 10)
        cbar.pack_start(self._setup_editbar(), False, False, 10)
        cbar.pack_start(self._setup_onionskin(), False, False, 10)
        cbar.pack_start(self._setup_config(), False, False, 10)
        cbar.pack_start(self._setup_generalbar(), False, False, 10)

        self.frame_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        scroll_window = Gtk.ScrolledWindow()
        scroll_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        viewport = Gtk.Viewport()
        viewport.add(self.frame_bar)
        scroll_window.add(viewport)
        scroll_window.set_size_request(-1, 140)

        base.pack_start(cbar, False, False, 0)
        base.pack_start(scroll_window, True, True, 0)
        self.add(base)

        pdb.script_fu_reverse_layers(self.image, None)
        self._scan_image_layers()
        self.active = 0
        self.on_goto(None, GIMP_ACTIVE)

        self.show_all()

    def _scan_image_layers(self):
        self.undo(False)
        layers = self.image.layers

        if self.frames:
            for frame in self.frames:
                self.frame_bar.remove(frame)
                frame.destroy()
            self.frames = []

        for layer in reversed(layers):
            layer.mode = NORMAL_MODE
            layer.opacity = 100.0

            f = AnimFrame(layer)
            f.connect("button_press_event", self.on_click_goto)
            self.frame_bar.pack_start(f, False, True, 2)
            self.frames.append(f)
            f.show_all()

        self.undo(True)

    def _setup_playbackbar(self):
        playback_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_size = 30
        stock_size = Gtk.IconSize.BUTTON

        self.play_button_images = [
            Gtk.Image.new_from_icon_name("media-playback-start", stock_size),
            Gtk.Image.new_from_icon_name("media-playback-pause", stock_size)
        ]

        b_play = Gtk.Button()
        b_play.set_image(self.play_button_images[0])
        b_play.set_size_request(button_size, button_size)

        b_tostart = Utils.button_stock("media-skip-backward", stock_size)
        b_toend = Utils.button_stock("media-skip-forward", stock_size)
        b_prev = Utils.button_stock("media-seek-backward", stock_size)
        b_next = Utils.button_stock("media-seek-forward", stock_size)
        b_repeat = Utils.toggle_button_stock("media-playlist-repeat", stock_size)

        b_play.connect('clicked', self.on_toggle_play)
        b_repeat.connect('toggled', self.on_replay)
        b_next.connect('clicked', self.on_goto, NEXT, True)
        b_prev.connect('clicked', self.on_goto, PREV, True)
        b_toend.connect('clicked', self.on_goto, END, True)
        b_tostart.connect('clicked', self.on_goto, START, True)

        w = [b_repeat, b_prev, b_next, b_tostart, b_toend]
        for x in w:
            self.widgets_to_disable.append(x)
        self.play_bar = playback_bar

        b_play.set_tooltip_text("Animation play/pause")
        b_repeat.set_tooltip_text("Animation replay active/deactive")
        b_prev.set_tooltip_text("To the previous frame")
        b_next.set_tooltip_text("To the next frame")
        b_tostart.set_tooltip_text("To the start frame")
        b_toend.set_tooltip_text("To the end frame")

        for x in [b_tostart, b_prev, b_play, b_next, b_toend, b_repeat]:
            playback_bar.pack_start(x, False, False, 0)
        return playback_bar

    def _setup_editbar(self):
        stock_size = Gtk.IconSize.BUTTON
        edit_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        b_back = Utils.button_stock("go-previous", stock_size)
        b_forward = Utils.button_stock("go-next", stock_size)
        b_rem = Utils.button_stock("list-remove", stock_size)
        b_add = Utils.button_stock("list-add", stock_size)
        b_copy = Utils.button_stock("edit-copy", stock_size)

        w = [b_back, b_forward, b_rem, b_add, b_copy]
        for x in w:
            self.widgets_to_disable.append(x)

        b_rem.connect("clicked", self.on_remove)
        b_add.connect("clicked", self.on_add)
        b_copy.connect("clicked", self.on_add, True)
        b_back.connect("clicked", self.on_move, PREV)
        b_forward.connect("clicked", self.on_move, NEXT)

        b_rem.set_tooltip_text("Remove a frame/layer")
        b_add.set_tooltip_text("Add a frame/layer")
        b_copy.set_tooltip_text("Duplicate the atual selected frame")
        b_back.set_tooltip_text("Move the atual selected frame backward")
        b_forward.set_tooltip_text("Move the atual selected frame forward")

        for x in w:
            edit_bar.pack_start(x, False, False, 0)
        return edit_bar

    def _setup_config(self):
        stock_size = Gtk.IconSize.BUTTON
        config_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        b_to_gif = Utils.button_stock("image-x-generic", stock_size)
        b_to_sprite = Utils.button_stock("image-x-generic", stock_size)
        b_conf = Utils.button_stock("preferences-system", stock_size)

        b_conf.connect("clicked", self.on_config)
        b_to_gif.connect('clicked', self.create_formated_version, 'gif')
        b_to_sprite.connect('clicked', self.create_formated_version, 'spritesheet')

        b_conf.set_tooltip_text("open configuration dialog")
        b_to_gif.set_tooltip_text("Create a formated Image to export as gif animation")
        b_to_sprite.set_tooltip_text("Create a formated Image to export as spritesheet")

        w = [b_conf, b_to_gif, b_to_sprite]
        for x in w:
            self.widgets_to_disable.append(x)
        for x in w:
            config_bar.pack_start(x, False, False, 0)
        return config_bar

    def _setup_onionskin(self):
        stock_size = Gtk.IconSize.BUTTON
        onionskin_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        b_active = Utils.toggle_button_stock("view-paged", stock_size)
        b_active.connect("clicked", self.on_onionskin)
        b_active.set_tooltip_text("enable/disable the onion skin effect")

        w = [b_active]
        for x in w:
            self.widgets_to_disable.append(x)
        for x in w:
            onionskin_bar.pack_start(x, False, False, 0)
        return onionskin_bar

    def _setup_generalbar(self):
        stock_size = Gtk.IconSize.BUTTON
        general_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        b_about = Utils.button_stock("help-about", stock_size)
        b_quit = Utils.button_stock("application-exit", stock_size)

        b_quit.connect('clicked', self.destroy)
        b_about.connect('clicked', self.on_about)

        b_about.set_tooltip_text("About FAnim")
        b_quit.set_tooltip_text("Exit")

        w = [b_about, b_quit]
        for x in w:
            self.widgets_to_disable.append(x)
        for x in w:
            general_bar.pack_start(x, False, False, 0)
        return general_bar

    def get_settings(self):
        s = {}
        s[FRAMERATE] = self.framerate
        s[OSKIN_DEPTH] = self.oskin_depth
        s[OSKIN_FORWARD] = self.oskin_forward
        s[OSKIN_BACKWARD] = self.oskin_backward
        s[OSKIN_ONPLAY] = self.oskin_onplay
        s[WIN_POSX] = self.win_pos[0]
        s[WIN_POSY] = self.win_pos[1]
        alloc = self.get_allocation()
        s[WIN_WIDTH] = alloc.width
        s[WIN_HEIGHT] = alloc.height
        return s

    def set_settings(self, conf):
        if conf is None:
            return
        self.framerate = int(conf[FRAMERATE])
        self.oskin_depth = int(conf[OSKIN_DEPTH])
        self.oskin_forward = conf[OSKIN_FORWARD]
        self.oskin_backward = conf[OSKIN_BACKWARD]
        self.oskin_onplay = conf[OSKIN_ONPLAY]
        self.win_size = (conf[WIN_WIDTH], conf[WIN_HEIGHT])
        self.win_pos = (conf[WIN_POSX], conf[WIN_POSY])

    def _toggle_enable_buttons(self, state):
        if state == PLAYING:
            for w in self.widgets_to_disable:
                w.set_sensitive(not self.is_playing)
        elif state == NO_FRAMES:
            self.play_bar.set_sensitive(not self.play_bar.get_sensitive())

    # ---------------------- Callback Functions ---------------------- #

    def on_window_focus(self, widget, other):
        time.sleep(0.1)
        if self.image not in gimp.image_list():
            self.destroy(False)
        else:
            if not self.image.layers:
                self.destroy(False)
            else:
                if self.active >= len(self.image.layers):
                    self.active = len(self.image.layers) - 1
                self._scan_image_layers()
                self.on_goto(None, GIMP_ACTIVE)

    def on_about(self, widget):
        about = Gtk.AboutDialog()
        about.set_authors(AUTHORS)
        about.set_program_name(NAME)
        about.set_copyright(COPYRIGHT)
        about.set_website(WEBSITE)
        about.run()
        about.destroy()

    def create_formated_version(self, widget, format='gif'):
        oskin_disabled = False
        if self.oskin:
            self.on_onionskin(None)
            oskin_disabled = True

        # In Python 3, filter() returns an iterator → convert to list
        normal_frames = list(filter(lambda x: x.fixed == False, self.frames))
        fixed_frames = list(filter(lambda x: x.fixed == True, self.frames))

        new_image = gimp.Image(self.image.width, self.image.height, self.image.base_type)

        normal_frames.reverse()

        for fl in normal_frames:
            group = gimp.GroupLayer(new_image, fl.layer.name)

            lcopy = pdb.gimp_layer_new_from_drawable(fl.layer, new_image)
            lcopy.visible = True

            new_image.add_layer(group, len(new_image.layers))
            new_image.insert_layer(lcopy, group, 0)

            up_fixed = list(filter(
                lambda x: self.frames.index(x) > self.frames.index(fl),
                fixed_frames))
            bottom_fixed = list(filter(
                lambda x: self.frames.index(x) < self.frames.index(fl),
                fixed_frames))

            b = 0
            for ff in fixed_frames:
                copy = pdb.gimp_layer_new_from_drawable(ff.layer, new_image)
                if ff in bottom_fixed:
                    new_image.insert_layer(copy, group, len(group.layers) - b)
                    b += 1
                elif ff in up_fixed:
                    new_image.insert_layer(copy, group, 0)

        if format == 'gif':
            gimp.Display(new_image)

        elif format == 'spritesheet':
            simg = gimp.Image(len(new_image.layers) * self.image.width,
                              self.image.height, self.image.base_type)

            cnt = 0

            def novisible(x, state):
                x.visible = state

            n_img_layers = list(new_image.layers)
            n_img_layers.reverse()

            for l in n_img_layers:
                cl = pdb.gimp_layer_new_from_drawable(l, simg)
                simg.add_layer(cl, 0)
                cl.transform_2d(0, 0, 1, 1, 0, -cnt * new_image.width, 0, 1, 0)
                cnt += 1
                for x in simg.layers:
                    novisible(x, False)
                cl.visible = True
                simg.merge_visible_layers(1)

            for x in simg.layers:
                novisible(x, True)
            gimp.Display(simg)

        if oskin_disabled:
            self.on_onionskin(None)

    def on_toggle_play(self, widget):
        if self.oskin_onplay:
            self.layers_show(False)

        self.is_playing = not self.is_playing

        if self.is_playing:
            if self.before_play is None:
                self.before_play = self.active

            widget.set_image(self.play_button_images[1])

            if not self.player:
                self.player = Player(self, widget)
            self._toggle_enable_buttons(PLAYING)
            self.player.start()

        else:
            if self.before_play is not None:
                self.on_goto(None, POS, index=self.before_play)
                self.before_play = None

            widget.set_image(self.play_button_images[0])
            self._toggle_enable_buttons(PLAYING)
            self.on_goto(None, NOWHERE)

    def on_replay(self, widget):
        self.is_replay = widget.get_active()

    def on_onionskin(self, widget):
        self.layers_show(False)
        if widget is None:
            self.oskin = not self.oskin
        else:
            self.oskin = widget.get_active()
        self.on_goto(None, NOWHERE, True)

    def on_config(self, widget):
        dialog = ConfDialog("FAnim Config", self, self.get_settings())
        result, config = dialog.run()

        if result == Gtk.ResponseType.APPLY:
            self.set_settings(config)
        dialog.destroy()

    def on_move(self, widget, direction):
        index = 0
        if direction == NEXT:
            index = self.active + 1
            if index == len(self.frames):
                return
        elif direction == PREV:
            index = self.active - 1
            if self.active - 1 < 0:
                return

        if direction == NEXT:
            self.image.raise_layer(self.frames[self.active].layer)
        elif direction == PREV:
            self.image.lower_layer(self.frames[self.active].layer)

        self._scan_image_layers()
        self.active = index
        self.on_goto(None, NOWHERE)

    def on_remove(self, widget):
        if not self.frames:
            return

        index = 0
        if self.active > 0:
            self.on_goto(None, PREV, True)
            index = self.active + 1

        self.image.remove_layer(self.frames[index].layer)
        self.frame_bar.remove(self.frames[index])
        self.frames[index].destroy()
        self.frames.remove(self.frames[index])

        if len(self.frames) == 0:
            self._toggle_enable_buttons(NO_FRAMES)
        else:
            self.on_goto(None, None, True)
        self.on_window_focus(None, None)

    def on_add(self, widget, copy=False):
        self.image.undo_group_start()

        name = "Frame " + str(len(self.frames))
        l = None
        if not copy:
            l = gimp.Layer(self.image, name, self.image.width,
                           self.image.height, RGBA_IMAGE, 100, NORMAL_MODE)
        else:
            l = self.frames[self.active].layer.copy()
            l.name = name

        self.image.add_layer(l, len(self.image.layers) - self.active - 1)
        if self.new_layer_type == TRANSPARENT_FILL and not copy:
            pdb.gimp_edit_clear(l)

        self._scan_image_layers()
        self.on_goto(None, NEXT, True)

        if len(self.frames) == 1:
            self._toggle_enable_buttons(NO_FRAMES)

        self.image.undo_group_end()

    def on_click_goto(self, widget, event):
        i = self.frames.index(widget)
        self.on_goto(None, POS, index=i)

    def on_goto(self, widget, to, update=False, index=0):
        self.layers_show(False)

        if update:
            self.frames[self.active].update_layer_info()

        if to == START:
            self.active = 0
        elif to == END:
            self.active = len(self.frames) - 1
        elif to == NEXT:
            i = self.active + 1
            if i > len(self.frames) - 1:
                i = 0
            self.active = i
        elif to == PREV:
            i = self.active - 1
            if i < 0:
                i = len(self.frames) - 1
            self.active = i
        elif to == POS:
            self.active = index
        elif to == GIMP_ACTIVE:
            if self.image.active_layer in self.image.layers:
                self.active = list(self.image.layers).index(self.image.active_layer)
                self.active = len(self.image.layers) - 1 - self.active
            else:
                self.active = 0

        self.layers_show(True)
        self.image.active_layer = self.frames[self.active].layer
        gimp.displays_flush()

    def layers_show(self, state):
        self.undo(False)

        self.frames[self.active].layer.opacity = 100.0

        if not state:
            opacity = 100.0
        else:
            opacity = self.oskin_max_opacity

        self.frames[self.active].layer.visible = state
        self.frames[self.active].highlight(state)

        is_fixed = self.frames[self.active].fixed

        if (self.oskin and not is_fixed) and not (self.is_playing and not self.oskin_onplay):
            for i in range(1, self.oskin_depth + 1):
                o = opacity
                if i > 1 and state:
                    o = opacity // i - 1 * 2  # integer division

                pos = self.active - i
                if self.oskin_backward and pos >= 0:
                    is_fixed = self.frames[pos].fixed
                    if not is_fixed:
                        self.frames[pos].layer.visible = state
                        self.frames[pos].layer.opacity = o

                pos = self.active + i
                if self.oskin_forward and pos <= len(self.frames) - 1:
                    is_fixed = self.frames[pos].fixed
                    if not is_fixed:
                        self.frames[pos].layer.visible = state
                        self.frames[pos].layer.opacity = o

        if self.frames[self.active].fixed and state == False:
            self.frames[self.active].layer.visible = True

        self.undo(True)


def timeline_main(image, drawable):
    global WINDOW_TITLE
    WINDOW_TITLE = WINDOW_TITLE % (image.name)
    win = Timeline(WINDOW_TITLE, image)
    win.start()


# Register the script in GIMP
register(
    "fanim_timeline",
    DESCRIPTION,
    DESCRIPTION,
    AUTHORS[0],
    AUTHORS[0],
    YEAR,
    GIMP_LOCATION,
    "*",
    [], [], timeline_main)

main()
