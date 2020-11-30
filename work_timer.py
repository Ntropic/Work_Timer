#!/usr/bin/env python
# Module     : SysTrayIcon.py
# Synopsis   : Windows System tray icon.
# Programmer : Simon Brunning - simon@brunningonline.net - modified for Python 3
# Date       : 13 February 2018
# Notes      : Based on (i.e. ripped off from) Mark Hammond's
#              win32gui_taskbar.py and win32gui_menu.py demos from PyWin32
import os
import sys
import win32api         # package pywin32
import win32con
import win32gui_struct
import sounddevice as sd
import tkinter as tk
import tkinter.font as tkfont
from ttkthemes import ThemedStyle
from ttkthemes import ThemedTk
import tkinter.ttk as ttk
import time
import numpy as np
import numpy.matlib
import os.path
import json
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
# Implement the default Matplotlib key bindings.
from matplotlib.backend_bases import key_press_handler
from matplotlib.figure import Figure
from matplotlib import rcParams #Make space for all elements (autolayout!)
import datetime
import itertools
import glob
rcParams.update({'figure.autolayout': True})
try:
    import winxpgui as win32gui
except ImportError:
    import win32gui

class Work_Timer(object):
    '''TODO'''
    QUIT = 'QUIT'
    SPECIAL_ACTIONS = [QUIT]

    FIRST_ID = 1023

    def __init__(self):
        def quitter(sysTrayIcon): self.destroyer()
        def opener(sysTrayIcon): self.open_window()
        def doer(sysTrayIcon): print('')
        self.default_menu_index = 1
        self.hover_text = "Work Timer"

        self._next_action_id = self.FIRST_ID
        self.menu_actions_by_id = set()
        self.window_state = 0  # Window is open
        menu_options = (('Currently: Nothing', None, doer),('Return', None, opener),('Quit', None, quitter),)
        self.menu_options = self._add_ids_to_menu_options(list(menu_options))
        self.menu_actions_by_id = dict(self.menu_actions_by_id)
        del self._next_action_id
        self.window_class_name = "Work Timer"

        message_map = {win32gui.RegisterWindowMessage("Taskbar Created"): self.make_icon,
                       win32con.WM_DESTROY: self.destroyer,
                       win32con.WM_COMMAND: self.command,
                       win32con.WM_USER+20 : self.notify,}
        # Register the Window class.
        window_class = win32gui.WNDCLASS()
        hinst = window_class.hInstance = win32gui.GetModuleHandle(None)
        window_class.lpszClassName = self.window_class_name
        window_class.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW;
        window_class.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        window_class.hbrBackground = win32con.COLOR_WINDOW
        window_class.lpfnWndProc = message_map # could also specify a wndproc.
        classAtom = win32gui.RegisterClass(window_class)
        # Create the Window.
        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(classAtom, self.window_class_name, style, 0, 0, win32con.CW_USEDEFAULT, win32con.CW_USEDEFAULT, 0, 0, hinst, None)
        win32gui.UpdateWindow(self.hwnd)
        self.notify_id = None
        self.make_icon()

        # Load Variables from file
        self.file_name = 'calendar.json'  # File to load/create append to
        self.today = datetime.datetime.now().date()
        if os.path.isfile(self.file_name)==0: # Create file
            self.data=[]
            self.data.append({'date': self.today, 'total_work_time': 0, 'total_pause_time': 0, 'remaining_earned_pause_time': 0})  # , 'work_starts': [], 'work_ends': [], 'pause_starts': [], 'pause_ends': []})
            save_json( self.data, self.file_name )
            self.current_index = 0
        else: #Find this date in the notebook
            self.data = load_json(self.file_name)
            self.current_index = len(self.data)-1
            last_date = self.data[self.current_index]['date']
            if last_date!=self.today:  # Create intermediate data entries
                while last_date!=self.today:
                    last_date = last_date + datetime.timedelta(days = 1)  # Add one day
                    self.data.append({'date': last_date, 'total_work_time': 0, 'total_pause_time': 0, 'remaining_earned_pause_time': 0})  # , 'work_starts': [], 'work_ends': [], 'pause_starts': [], 'pause_ends': []})  # Add new day to list
                    self.current_index = len(self.data)-1
        save_json(self.data, self.file_name)
        self.how_many_days = 7

        # Prepare audio
        bitrate = 44100
        self.bitrate = bitrate
        length = 1  # second
        self.loudness = 0.5
        x = np.linspace(0, length, round(bitrate * length))

        self.up = np.multiply(self.loudness, np.exp(-(x - length / 2) ** 2 / (length / 4) ** 2) * np.cos(
            2 * np.pi * 100 * (length * (np.cos(x ** 2 / length * np.pi * 12)))))
        self.down = np.multiply(self.loudness, np.exp(-(x - length / 2) ** 2 / (length / 4) ** 2) * np.cos(
            2 * np.pi * 100 * (length * (np.cos(1 / (x + 0.25) / length * np.pi * 4)))))
        self.low = np.multiply(self.loudness,
                               np.exp(-(x - length / 2) ** 2 / (length / 4) ** 2) * np.cos(2 * np.pi * x * 110))
        self.high = np.multiply(self.loudness,
                                np.exp(-(x - length / 2) ** 2 / (length / 4) ** 2) * np.cos(2 * np.pi * x * 440))
        length = 2  # second
        x = np.linspace(0, length, round(bitrate * length))
        x2 = np.linspace(0, 1, round(bitrate / 2))
        arr = np.cos(2 * np.pi * 200 * length * (x2 * (np.cos(x2 * np.pi) ** 2)))
        arr2 = np.matlib.repmat(arr, 1, length * 2)
        arr3 = arr2[0]
        self.warn = np.multiply(np.exp(-(x - length / 2) ** 2 / (length / 6) ** 2), arr3)

        # Create variables for total work time and current work time
        # {'date': self.today, 'total_work_time': 0, 'total_pause_time': 0, 'remaining_earned_pause_time': 0})  # , 'work_starts': [], 'work_ends': [], 'pause_starts': [], 'pause_ends': []}
        self.load_data()

        self.started = 0
        self.currently_working = 0  # 0=nothing, 1=working 2=pausing
        self.work_pause_ratio = 0.25

        self.first_time=1
        self.open_window()

        win32gui.PumpMessages()

    def load_data(self):
        self.total_work_time = self.data[self.current_index]['total_work_time']
        self.how_much_total_pauses = self.data[self.current_index]['total_pause_time']
        self.how_much_pause = self.data[self.current_index]['remaining_earned_pause_time']
        #self.work_starts = self.data[self.current_index]['work_starts']
        #self.work_ends = self.data[self.current_index]['work_ends']
        #self.pause_starts = self.data[self.current_index]['pause_starts']
        #self.pause_ends = self.data[self.current_index]['pause_ends']
        self.current_total_work = self.total_work_time
        self.current_total_pause = self.how_much_total_pauses


    def _add_ids_to_menu_options(self, menu_options):
        result = []
        for menu_option in menu_options:
            option_text, option_icon, option_action = menu_option
            if callable(option_action) or option_action in self.SPECIAL_ACTIONS:
                self.menu_actions_by_id.add((self._next_action_id, option_action))
                result.append(menu_option + (self._next_action_id,))
            elif non_string_iterable(option_action):
                result.append((option_text,
                               option_icon,
                               self._add_ids_to_menu_options(option_action),
                               self._next_action_id))
            else:
                print(option_action)
                result.append((option_text,
                               option_icon,
                               None,
                               self._next_action_id))
                #print('Unknown item', option_text, option_icon, option_action)
            self._next_action_id += 1
        return result

    def make_icon(self):
        # Try and find a custom icon
        hinst = win32gui.GetModuleHandle(None)
        icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
        hicon = win32gui.LoadImage(hinst, 'cWindow_Icon_high_res.ico', win32con.IMAGE_ICON, 0, 0, icon_flags)


        if self.notify_id:
            message = win32gui.NIM_MODIFY
        else:
            message = win32gui.NIM_ADD
        self.notify_id = (self.hwnd, 0, win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP, win32con.WM_USER + 20, hicon, self.hover_text)
        win32gui.Shell_NotifyIcon(message, self.notify_id)

    def destroyer(self):  #, hwnd, msg, wparam, lparam):
        if self.window_state==1:
            print("Closing Window.")
            self.root.quit()
            self.root.destroy()
        nid = (self.hwnd, 0)
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        win32gui.PostQuitMessage(0) # Terminate the app.
        self.QUIT

    def notify(self, hwnd, msg, wparam, lparam):
        if lparam==win32con.WM_LBUTTONDBLCLK:
            self.execute_menu_option(self.default_menu_index + self.FIRST_ID)
        elif lparam==win32con.WM_RBUTTONUP:
            self.show_menu()
        elif lparam==win32con.WM_LBUTTONUP:
            pass
        return True

    def show_menu(self):
        self.menu = win32gui.CreatePopupMenu()
        self.create_menu( self.menu_options)

        pos = win32gui.GetCursorPos()
        # See http://msdn.microsoft.com/library/default.asp?url=/library/en-us/winui/menus_0hdi.asp
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.TrackPopupMenu(self.menu, win32con.TPM_LEFTALIGN, pos[0], pos[1], 0, self.hwnd, None)
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)

    def create_menu(self, menu_options):
        for option_text, option_icon, option_action, option_id in menu_options[:0:-1]:
            if option_icon:
                option_icon = self.prep_menu_icon(option_icon)

            if option_id in self.menu_actions_by_id:
                item, extras = win32gui_struct.PackMENUITEMINFO(text=option_text, hbmpItem=option_icon, wID=option_id)
                win32gui.InsertMenuItem(self.menu, 0, 1, item)
        # Last entry
        option_text, option_icon, option_action, option_id = menu_options[0]
        if option_icon:
            option_icon = self.prep_menu_icon(option_icon)

        if option_id in self.menu_actions_by_id:
            if self.currently_working==0:
                option_text = 'Nothing'
            elif self.currently_working==1:
                tcum = time.time() - self.changed
                tcum_struct = time.gmtime(tcum)
                option_text = 'Working - '+time.strftime("%H:%M:", tcum_struct)+' [hh:mm]'
            else:
                tcum = time.time() - self.changed
                tcum_struct = time.gmtime(tcum)
                option_text = 'Pausing - '+time.strftime("%H:%M:", tcum_struct)+' [hh:mm]'
            item, extras = win32gui_struct.PackMENUITEMINFO(text=option_text, hbmpItem=option_icon, wID=option_id)
            win32gui.InsertMenuItem(self.menu, 0, 1, item)

    def prep_menu_icon(self, icon):
        # First load the icon.
        ico_x = win32api.GetSystemMetrics(win32con.SM_CXSMICON)
        ico_y = win32api.GetSystemMetrics(win32con.SM_CYSMICON)
        hicon = win32gui.LoadImage(0, icon, win32con.IMAGE_ICON, ico_x, ico_y, win32con.LR_LOADFROMFILE)

        hdcBitmap = win32gui.CreateCompatibleDC(0)
        hdcScreen = win32gui.GetDC(0)
        hbm = win32gui.CreateCompatibleBitmap(hdcScreen, ico_x, ico_y)
        hbmOld = win32gui.SelectObject(hdcBitmap, hbm)
        # Fill the background.
        brush = win32gui.GetSysColorBrush(win32con.COLOR_MENU)
        win32gui.FillRect(hdcBitmap, (0, 0, 16, 16), brush)
        # unclear if brush needs to be feed.  Best clue I can find is:
        # "GetSysColorBrush returns a cached brush instead of allocating a new
        # one." - implies no DeleteObject
        # draw the icon
        win32gui.DrawIconEx(hdcBitmap, 0, 0, hicon, ico_x, ico_y, 0, 0, win32con.DI_NORMAL)
        win32gui.SelectObject(hdcBitmap, hbmOld)
        win32gui.DeleteDC(hdcBitmap)
        return hbm

    def command(self, hwnd, msg, wparam, lparam):
        id = win32gui.LOWORD(wparam)
        self.execute_menu_option(id)

    def execute_menu_option(self, id):
        menu_action = self.menu_actions_by_id[id]
        if menu_action == self.QUIT:
            win32gui.DestroyWindow(self.hwnd)
        else:
            menu_action(self)

    def on_closing(self):
        self.window_state=0
        print("Closing Window. Remaining in System Tray.")
        self.root.destroy()
        self.root.quit()

    def open_window(self):
        if self.window_state==0:
            print('Opening new window')
            self.window_state=1
            # Create Style and style-variables for window
            root = ThemedTk(theme="equilux", background=True)
            root.resizable(width="false", height="false")
            self.root = root
            if self.first_time==1:
                s = ttk.Style()
                font_color = s.lookup('TButton', 'foreground')  # ="white"
                mpl.rcParams['text.color'] = font_color
                mpl.rcParams['axes.labelcolor'] = font_color
                mpl.rcParams['xtick.color'] = font_color
                mpl.rcParams['ytick.color'] = font_color
                mpl.rcParams['axes.edgecolor'] = font_color
                b_g = s.lookup('TFrame', 'background')
                mpl.rcParams["figure.facecolor"] = b_g
                mpl.rcParams["axes.facecolor"] = b_g
                mpl.rcParams["savefig.facecolor"] = b_g
                s.configure('bold.Label', font=('Arial', 11, 'bold'))
                s.configure('normal.Label', font=('Arial', 11,))
                s.configure('.', font=('Arial', 10))
                self.b_g = s.lookup('TFrame', 'background')
                self.text_color = s.lookup('TButton', 'foreground')
                self.first_time = 0
            self.root.title("Work Timer")
            self.root.wm_iconbitmap('Icon/cWindow_Icon_high_res.ico')
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

            len_pady = 3
            len_padx = 5
            # Create GUI Elements
            self.tot_timer_text = ttk.Label(self.root,text="Total Work    (Today)")  # ,font=self.normal_font)
            self.tot_timer_text.grid(row=0, column=0, padx=len_padx, pady=len_pady, sticky="W")

            self.tot_pause_text = ttk.Label(self.root,text="Total Pauses (Today)")  # ,font=self.normal_font)
            self.tot_pause_text.grid(row=1, column=0, padx=len_padx, pady=len_pady, sticky="W")

            self.con_timer_text = ttk.Label(self.root,text="Current Work")  # ,font=self.normal_font)
            self.con_timer_text.grid(row=2, column=0, padx=len_padx, pady=len_pady, sticky="W")

            self.earned_pause_text = ttk.Label(self.root,text="Remaining Pause")  # ,font=self.normal_font)
            self.earned_pause_text.grid(row=3, column=0, padx=len_padx, pady=len_pady, sticky="W")

            self.tot_timer_label = ttk.Label(self.root,text="")
            self.tot_timer_label.grid(row=0, column=2, padx=len_padx, pady=len_pady, sticky="E")

            self.tot_pause_label = ttk.Label(self.root,text="")
            self.tot_pause_label.grid(row=1, column=2, padx=len_padx, pady=len_pady, sticky="E")

            self.con_timer_label = ttk.Label(self.root,text="")
            self.con_timer_label.grid(row=2, column=2, padx=len_padx, pady=len_pady, sticky="E")

            self.earned_pause_label = ttk.Label(self.root,text="")
            self.earned_pause_label.grid(row=3, column=2, padx=len_padx, pady=len_pady, sticky="E")

            self.work_button = ttk.Button(self.root, text="Work", command=self.work)
            self.work_button.grid(row=4, column=0, padx=len_padx, pady=len_pady, sticky="W")

            self.pause_button = ttk.Button(self.root, text="Pause", command=self.pause)
            self.pause_button.grid(row=4, column=2, padx=len_padx, pady=len_pady, sticky="E")

            self.done_button = ttk.Button(self.root, text="Done", command=self.done)
            self.done_button.grid(row=4, column=1, padx=len_padx, pady=len_pady, sticky="E")

            self.initial_plot()
            self.update_clock()
            self.root.mainloop()

    def update_clock(self):

        if (datetime.datetime.now() + datetime.timedelta(seconds=5)).date() != self.today:  #
            # A new day started stop work counter, give warning sign
            self.done()
            sd.play(self.high, self.bitrate, blocking=True)
            # Wait until new day:
            while datetime.datetime.now().date() == self.today:
                time.sleep(1)
            #Change day
            self.today=datetime.datetime.now().date()
            self.data.append({'date': self.today, 'total_work_time': 0, 'total_pause_time': 0, 'remaining_earned_pause_time': 0})  # , 'work_starts': [], 'work_ends': [], 'pause_starts': [], 'pause_ends': []})
            self.current_index = len(self.data) - 1
            self.load_data()

            # This way we have no problems with the variables

        if datetime.datetime.now().date() != self.today:
            self.today = datetime.datetime.now().date()
            # Create a new entry in the data bank and save
            self.data.append(
                {'date': self.today, 'total_work_time': 0, 'total_pause_time': 0, 'remaining_earned_pause_time': 0,
                 'work_starts': [], 'work_ends': [], 'pause_starts': [], 'pause_ends': []})  # Add new day to list
            save_json(self.data, self.file_name)
            self.current_index = len(self.data)
            self.total_work_time = self.data[self.current_index]['total_work_time']
            self.how_much_total_pauses = self.data[self.current_index]['total_pause_time']
            self.how_much_pause = self.data[self.current_index]['remaining_earned_pause_time']
            self.work_starts = self.data[self.current_index]['work_starts']
            self.work_ends = self.data[self.current_index]['work_ends']
            self.pause_starts = self.data[self.current_index]['pause_starts']
            self.pause_ends = self.data[self.current_index]['pause_ends']

        if self.currently_working == 1:
            tcum = time.time() - self.started
            tcum_struct = time.gmtime(tcum)
            cum_worked_string = time.strftime("%H:%M:%S", tcum_struct)
            cum_worked_string = '+' + cum_worked_string
        elif self.currently_working == 2:
            tcum = 0
            tcum_struct = time.gmtime(tcum)
            cum_worked_string = time.strftime("%H:%M:%S", tcum_struct)
            cum_worked_string = '+' + cum_worked_string
        else:
            tcum = 0
            tcum_struct = time.gmtime(tcum)
            cum_worked_string = time.strftime("%H:%M:%S", tcum_struct)
            cum_worked_string = '+' + cum_worked_string

        self.current_total_work = self.total_work_time
        if self.currently_working == 1:  # Working
            t_tot = self.total_work_time + tcum
            t_tot_struct = time.gmtime(t_tot)
            tot_worked_string = time.strftime("%H:%M:%S", t_tot_struct)
            tot_worked_string = '+' + tot_worked_string
            self.current_total_work = self.current_total_work + tcum
        else:
            t_tot = self.total_work_time
            t_tot_struct = time.gmtime(t_tot)
            tot_worked_string = time.strftime("%H:%M:%S", t_tot_struct)
            tot_worked_string = '+' + tot_worked_string

        self.current_total_pause = self.how_much_total_pauses
        if self.currently_working == 2:  # Doing a pause
            tcum = time.time() - self.started
            t_pause = self.how_much_pause - tcum
            t_struct = time.gmtime(abs(t_pause))
            t = t_pause
            earned_pause_string = time.strftime("%H:%M:%S", t_struct)
            self.current_total_pause = self.current_total_pause + tcum
        elif self.currently_working == 1:
            t = self.how_much_pause + tcum * self.work_pause_ratio
            t_struct = time.gmtime(abs(t))
            earned_pause_string = time.strftime("%H:%M:%S", t_struct)
        else:
            t = self.how_much_pause
            t_struct = time.gmtime(abs(t))
            earned_pause_string = time.strftime("%H:%M:%S", t_struct)
        tot_pause_string = time.strftime("%H:%M:%S", time.gmtime(abs(self.current_total_pause)))
        tot_pause_string = '+' + tot_pause_string

        if t < 0:
            earned_pause_string = '-' + earned_pause_string
        else:
            earned_pause_string = '+' + earned_pause_string

        # now = time.strftime("%H:%M:%S")
        if self.window_state==1:
            self.tot_timer_label.configure(text=tot_worked_string)
            self.tot_pause_label.configure(text=tot_pause_string)
            self.con_timer_label.configure(text=cum_worked_string)
            self.earned_pause_label.configure(text=earned_pause_string)

            if self.currently_working != 0:
                if np.mod(t_tot, 900) == 0:
                    sd.play(self.high, self.bitrate)
                elif np.mod(t_tot, 300) == 0:  # 5 minutes
                    sd.play(self.low, self.bitrate, blocking=True)

            if self.currently_working == 2:
                if round(t_pause) == 0:
                    sd.play(self.warn, self.bitrate, blocking=True)

            if self.currently_working != 0:  # Update plot
                if np.abs(np.mod(time.time(), 30)) <= 1:
                    self.replot()
                    if self.currently_working == 1:
                        self.work()
                    elif self.currently_working == 2:
                        self.pause()

        self.root.after(1000, self.update_clock)

    def work(self):
        self.work_button['state'] = 'disabled'
        self.pause_button['state'] = 'normal'

        self.con_timer_label.configure(style='bold.Label')  # font=self.bold_font)
        self.con_timer_text.configure(style='bold.Label')

        self.earned_pause_label.configure(style='normal.Label')
        self.earned_pause_text.configure(style='normal.Label')

        self.tot_timer_text.configure(style='bold.Label')
        self.tot_timer_label.configure(style='bold.Label')

        self.tot_pause_text.configure(style='normal.Label')
        self.tot_pause_label.configure(style='normal.Label')

        if self.currently_working == 2:  # Previously a pause
            curr_time = time.time()
            tcum = curr_time - self.started
            self.how_much_pause = self.how_much_pause - tcum
            self.how_much_total_pauses = self.how_much_total_pauses + tcum
            self.data[self.current_index]['total_pause_time'] = self.how_much_total_pauses
            self.data[self.current_index]['remaining_earned_pause_time'] = self.how_much_pause
            #self.pause_starts = curr_time - tcum
            #self.pause_ends = curr_time
            #self.data[self.current_index]['pause_starts'].append(self.pause_starts)
            #self.data[self.current_index]['pause_ends'].append(self.pause_ends)
            self.changed = curr_time
        elif self.currently_working == 1:
            curr_time = time.time()
            tcum = curr_time - self.started
            self.total_work_time = self.total_work_time + tcum
            self.how_much_pause = self.how_much_pause + tcum * self.work_pause_ratio
            self.data[self.current_index]['total_work_time'] = self.total_work_time

            #self.work_starts = curr_time - tcum
            #self.work_ends = curr_time
            #self.data[self.current_index]['work_starts'].append(self.work_starts)
            #self.data[self.current_index]['work_ends'].append(self.work_ends)
        else:
            curr_time = time.time()
            self.changed = curr_time

        self.started = curr_time

        if self.currently_working != 1:
            sd.play(self.up, self.bitrate)

        self.currently_working = 1  # self.update_clock()  # Update once
        save_json(self.data, self.file_name)

    def pause(self):
        self.pause_button['state'] = 'disabled'
        self.work_button['state'] = 'normal'

        self.con_timer_label.configure(style='normal.Label')  # font=self.bold_font)
        self.con_timer_text.configure(style='normal.Label')

        self.earned_pause_label.configure(style='bold.Label')
        self.earned_pause_text.configure(style='bold.Label')

        self.tot_timer_text.configure(style='normal.Label')
        self.tot_timer_label.configure(style='normal.Label')

        self.tot_pause_text.configure(style='bold.Label')
        self.tot_pause_label.configure(style='bold.Label')

        if self.currently_working == 1:
            curr_time = time.time()
            tcum = curr_time - self.started
            self.total_work_time = self.total_work_time + tcum
            self.how_much_pause = self.how_much_pause + tcum * self.work_pause_ratio
            self.data[self.current_index]['total_work_time'] = self.total_work_time

            #self.work_starts = curr_time - tcum
            #self.work_ends = curr_time
            #self.data[self.current_index]['work_starts'].append(self.work_starts)
            #self.data[self.current_index]['work_ends'].append(self.work_ends)
            self.changed = curr_time
        elif self.currently_working == 2:
            curr_time = time.time()
            tcum = curr_time - self.started
            self.how_much_pause = self.how_much_pause - tcum
            self.how_much_total_pauses = self.how_much_total_pauses + tcum
            self.data[self.current_index]['total_pause_time'] = self.how_much_total_pauses
            self.data[self.current_index]['remaining_earned_pause_time'] = self.how_much_pause

            #self.pause_starts = curr_time - tcum
            #self.pause_ends = curr_time
            #self.data[self.current_index]['pause_starts'].append(self.pause_starts)
            #self.data[self.current_index]['pause_ends'].append(self.pause_ends)
        else:
            curr_time = time.time()
            self.changed = curr_time

        self.started = curr_time

        if self.currently_working != 2:
            sd.play(self.down, self.bitrate)
        self.currently_working = 2
        save_json(self.data, self.file_name)

    def done(self):
        self.pause_button['state'] = 'normal'
        self.work_button['state'] = 'normal'

        self.con_timer_label.configure(style='normal.Label')
        self.earned_pause_label.configure(style='normal.Label')
        self.con_timer_text.configure(style='normal.Label')
        self.earned_pause_text.configure(style='normal.Label')

        curr_time = time.time()
        if self.currently_working == 1:
            tcum = time.time() - self.started
            self.total_work_time = self.total_work_time + tcum
            self.how_much_pause = self.how_much_pause + tcum * self.work_pause_ratio
            #self.work_starts = curr_time - tcum
            #self.work_ends = curr_time
            #self.data[self.current_index]['work_starts'].append(self.work_starts)
            #self.data[self.current_index]['work_ends'].append(self.work_ends)
            self.changed = curr_time

        if self.currently_working == 2:
            tcum = time.time() - self.started
            self.how_much_pause = self.how_much_pause - tcum
            self.how_much_total_pauses = self.how_much_total_pauses + tcum
            #self.pause_starts = curr_time - tcum
            #self.pause_ends = curr_time
            #self.data[self.current_index]['pause_starts'].append(self.pause_starts)
            #self.data[self.current_index]['pause_ends'].append(self.pause_ends)
            self.changed = curr_time

        self.data[self.current_index]['total_work_time'] = self.total_work_time
        self.data[self.current_index]['total_pause_time'] = self.how_much_total_pauses
        self.data[self.current_index]['remaining_earned_pause_time'] = self.how_much_pause
        self.started = 0

        self.currently_working = 0
        sd.play(self.high, self.bitrate)

        save_json(self.data, self.file_name)

    def initial_plot(self):
        paused = extract_total_pauses(self.data, self.how_many_days, self.current_total_pause)
        worked = extract_total_work(self.data, self.how_many_days, self.current_total_work)
        dates = make_dates(self.how_many_days)

        fig = Figure(figsize=(3.75, 2.0), dpi=90)
        ax = fig.add_subplot(111)
        x = np.arange(self.how_many_days)
        time_in_h = np.divide(worked, 3600)
        allowed_pause = np.multiply(time_in_h, self.work_pause_ratio)
        pause_time_in_h = np.divide(paused, 3600)
        time_in_h_cum1 = np.max(np.add(time_in_h, pause_time_in_h))
        time_in_h_cum2 = np.max(np.add(time_in_h, allowed_pause))
        time_in_h_cum = np.max([time_in_h_cum1, time_in_h_cum2])
        ax.bar(x, time_in_h, color=self.text_color, edgecolor=self.text_color)
        ax.bar(x, pause_time_in_h, bottom=time_in_h, color=self.text_color, edgecolor=self.text_color, hatch='////',
               fill=False)
        ax.bar(x, allowed_pause, bottom=time_in_h, color=self.text_color, edgecolor=self.text_color, fill=False)
        ax.set_ylabel('Worktime [h]')
        ax.set_xticks(x)
        ax.set_xticklabels(dates, rotation=45, ha="right")
        ax.set_ylim([0, np.ceil(np.max([1, np.ceil(time_in_h_cum)]))])

        canvas = FigureCanvasTkAgg(fig, master=self.root)  # A tk.DrawingArea.
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=3, columnspan=5, rowspan=5)

        self.ax = ax
        self.fig = fig
        self.canvas = canvas

    def replot(self):
        paused = extract_total_pauses(self.data, self.how_many_days, self.current_total_pause)
        worked = extract_total_work(self.data, self.how_many_days, self.current_total_work)
        dates = make_dates(self.how_many_days)

        x = np.arange(self.how_many_days)
        time_in_h = np.divide(worked, 3600)
        allowed_pause = np.multiply(time_in_h, self.work_pause_ratio)
        pause_time_in_h = np.divide(paused, 3600)
        time_in_h_cum1 = np.max(np.add(time_in_h, pause_time_in_h))
        time_in_h_cum2 = np.max(np.add(time_in_h, allowed_pause))
        time_in_h_cum = np.max([time_in_h_cum1, time_in_h_cum2])

        self.ax.clear()
        self.ax.bar(x, time_in_h, color=self.text_color, edgecolor=self.text_color)
        self.ax.bar(x, pause_time_in_h, bottom=time_in_h, color=self.text_color, edgecolor=self.text_color,
                    hatch='////', fill=False)
        self.ax.bar(x, allowed_pause, bottom=time_in_h, color=self.text_color, edgecolor=self.text_color, fill=False)
        self.ax.set_ylabel('Worktime [h]')
        self.ax.set_xticks(x)
        self.ax.set_xticklabels(dates, rotation=45, ha="right")
        self.ax.set_ylim([0, np.ceil(np.max([1, np.ceil(time_in_h_cum)]))])
        self.canvas.draw()

def non_string_iterable(obj):
    try:
        iter(obj)
    except TypeError:
        return False
    else:
        return not isinstance(obj, str)

def default(o):  # To reformat the data for json -> datetime to isofromat
    if type(o) is datetime.date or type(o) is datetime.datetime or type(o) is datetime.time:
        return o.isoformat()

def load_json(file_name):  # Return to datetime formatting
    with open(file_name, 'r') as json_file:
        data = json.load(json_file)
    for i in range(0, len(data)):  # Reformat the datetimes
        a = datetime.datetime.fromisoformat(data[i]['date']).date()
        data[i]['date'] = a

    return data

def save_json(data, file_name):  # Return to datetime formatting
    with open(file_name, 'w') as json_file:
        json.dump(data, json_file, default=default)  # Save as json

def extract_total_work(data, how_many_days, total_work_time):
    worked = []
    if len(data) > how_many_days:
        for i in range(len(data) - how_many_days, len(data)):
            worked.append(data[i]['total_work_time'])
    else:
        length = len(data)
        for i in range(0, how_many_days - length):
            worked.append(0)
        for i in range(0, length):
            worked.append(data[i]['total_work_time'])
    worked[len(worked) - 1] = total_work_time
    return worked

def extract_total_pauses(data, how_many_days, total_pause_time):
    paused = []
    if len(data) > how_many_days:
        for i in range(len(data) - how_many_days, len(data)):
            paused.append(data[i]['total_pause_time'])
    else:
        length = len(data)
        for i in range(0, how_many_days - length):
            paused.append(0)
        for i in range(0, length):
            paused.append(data[i]['total_pause_time'])
    paused[len(paused) - 1] = total_pause_time
    return paused

def make_dates(how_many_dates):
    today = datetime.datetime.now().date()
    dates = []
    for i in range(0, how_many_dates):
        delta_now = how_many_dates - i - 1;
        dates.append((today - datetime.timedelta(days=delta_now)).strftime("%d-%m"))  # %b for month as str eg. Nov.
    return dates

# Start:
if __name__ == '__main__':
    Work_Timer()