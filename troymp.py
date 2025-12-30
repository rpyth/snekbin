from tkinter import *
from tkinter import ttk, scrolledtext, filedialog, font
import subprocess
#import pydub as pd
import os
from glob import glob
from random import randint, choice
#import numpy as np
from multiprocessing import Process, Array, Value, freeze_support, Queue, Manager
from time import sleep, time
import pyaudio
from snektools import *
import requests
#py -3.10 -m pip install sv-ttk pydub pyaudio

session = requests.Session()

def fix_popups():
    return
    """import importlib.util
    import re
    import sys
    import types

    import pydub
    from IceSpringPathLib import Path

    for moduleName in "pydub.utils", "pydub.audio_segment":
        spec = importlib.util.find_spec(moduleName, None)
        source = spec.loader.get_source(moduleName)
        snippet = "__import__('subprocess').STARTUPINFO(dwFlags=__import__('subprocess').STARTF_USESHOWWINDOW)"
        source, n = re.subn(r"(Popen)\((.+?)\)", rf"\1(\2, startupinfo=print('worked') or {snippet})", source, flags=re.DOTALL)
        module = importlib.util.module_from_spec(spec)
        exec(compile(source, module.__spec__.origin, "exec"), module.__dict__)
        sys.modules[moduleName] = module
    module = importlib.reload(sys.modules["pydub"])
    for k, v in module.__dict__.items():
        if isinstance(v, types.ModuleType):
            setattr(module, k, importlib.import_module(v.__name__))"""
    #pydub.audio_segment.AudioSegment.from_file(Path("~/Music").expanduser().glob("**/*.mp3").__next__())

def playback(q, volume, controls, is_playing, changed):
    fix_popups()
    while 1:
        while q.empty():
            sleep(0.01)
        fname = q.get()
        ogmix = pd.AudioSegment.from_file(fname)
        length = len(ogmix)
        quarters = []
        index = 0
        try:
            while index<len(ogmix):
                quarters.append(ogmix[index:index+250])
                index+=250
        except Exception:
            quarters.append(ogmix[index:])
        focus = 0
        maximal = len(quarters)
        info = pd.utils.mediainfo(fname)
        play = None

        p = pyaudio.PyAudio()

        # open stream (2)
        stream = p.open(format=p.get_format_from_width(ogmix.sample_width),
                        channels=int(info["channels"]),
                        rate=int(info["sample_rate"]),
                        output=True)

        while focus<maximal and q.empty():
            while not is_playing.value:
                sleep(0.01)
            sound = quarters[focus] - int(volume.value)
            stream.write(bytes(sound.get_array_of_samples()))
            focus+=1
            if not changed.value:
                controls.value = 100*focus/maximal
            else:
                focus = int(controls.value/100*maximal)
                changed.value = 0
                
def playback_stream(q, volume, controls, is_playing, changed, qlist, qcount):
    maximal = 0
    while 1:
        while q.empty():
            sleep(0.01)
        info, maximal = q.get()#dict of bytes and a dict
        if not isinstance(info, dict):
            break
        p = pyaudio.PyAudio()
        if len(qlist[:])!=maximal:
            focus = 0

        stream = p.open(format=info.get("format"),
                        channels=int(info["channels"]),
                        rate=int(info["sample_rate"]),
                        output=True)
        while len(qlist[:])<32 and maximal>40:
            sleep(0.01)
        qlist_local = []
        while q.empty():
            qcount.value = focus
            while focus>=maximal and q.empty():#what happens if song finishes
                if changed.value:
                    focus = int(controls.value/100*maximal)
                    changed.value = 0
                else:
                    sleep(0.01)
            
            while not is_playing.value:
                sleep(0.01)

            while 1:
                try:
                    if len(qlist_local)==len(qlist):
                        pass
                    elif len(qlist_local)<len(qlist):
                        qlist[:len(qlist_local)] = [b""]*len(qlist_local)
                        qlist_local.extend(qlist[len(qlist_local):])
                    elif len(qlist_local)>len(qlist):
                        qlist_local = []
                    stream.write(qlist_local[focus])
                    break
                except IndexError as e:
                    while len(qlist[:])<focus:
                        if changed.value:
                            focus = 0
            focus+=1
            if not changed.value:
                controls.value = 100*focus/maximal
            else:
                focus = int(controls.value/100*maximal)
                changed.value = 0
                
def zeros(i):
    s = str(i)
    if len(s)<2:
        s = "0"+s
    return s

def timestamp(t):
    t = int(t)
    return f"{zeros(t//60)}:{zeros(t%60)}"

def test(fname):
    sound = pd.AudioSegment.from_file(fname)
    samples = sound.get_array_of_samples()
    info = pd.utils.mediainfo(fname)
    obj = sa.WaveObject(samples, int(info["channels"]), sound.sample_width, int(info["sample_rate"]))
    obj.play()
# url, length, self.quarter_list, self.fname, self.volume_var, self.slider_var, self.playback_var, self.changed_var
def music_miner(url, length, ql, fname, volume, controls, is_playing, changed, stopper, cutter):
    part = 0
    while len(ql)<length and stopper.value==0:
        if cutter.value>-1:
            ql[:] = ql[:cutter.value]
            part = cutter.value
            cutter.value = -1
        to_upload = {"file": compress(dict_to_bytes({"file": fname, "volume": str(volume.value), "part": part}))}#file is the FULL path
        r = session.get(url, files = to_upload)
        if r.status_code == 200:
            r.raw.decode_content = True
            d = bytes_to_dict(decompress(r.content))
            my_list = []
            for key in sorted(list(d.get("quarters").keys()), key = lambda v: int(v)):
                my_list.append(d.get("quarters").get(key))
            ql[:] = ql[:]+my_list

            part += 16
        

class Troy(Toplevel):
    def __init__(self, master, fname):
        super().__init__(master)
        self.title("Troy Music Player v1.1s")
        #sv_ttk.use_light_theme()

        self.miner = None
        self.quarters = []
        self.is_playing = False
        self.is_ticking = False
        self.obj = None
        self.mode_val = 0
        self.control = 0
        self.vlock = 0
        self.q = Queue()
        self.volume_var = Value("d", 0.5)
        self.playback_var = Value("i", 0)
        self.changed_var = Value("i", 0)
        self.slider_var = Value("d", 0.0)
        self.stopper = Value("i", 0)
        self.cutter = Value("i", -1)
        self.quarter_counter = Value("i", 0)

        self.manager = Manager()
        self.quarter_list = self.manager.list([])
        
        self.process = Process(target = playback_stream, args = (self.q,
                                                                 self.volume_var,
                                                                 self.slider_var,
                                                                 self.playback_var,
                                                                 self.changed_var,
                                                                 self.quarter_list,
                                                                 self.quarter_counter))
        self.process.start()
        self.fname = fname
        self.style = ttk.Style()
        #self.style.configure("TButton", font = "Hack 18")
        self.style.configure("Big.TButton", font=(font.nametofont("TkDefaultFont"), 24), width = 2)
        self.buffervar = IntVar()
        #self.buffervar and self.buffered added, must add scalebuf

        self.top_panel = Frame(self)
        self.bottom_panel = Frame(self)
        self.play_btn = ttk.Button(self.top_panel, text = "⏵", command = self.on_play, style = "Big.TButton")
        self.scalebuf = Frame(self.top_panel)
        self.scale = ttk.Scale(self.scalebuf, from_=0, to=100, command = self.changed)# cursed
        self.buffered = ttk.Progressbar(self.scalebuf, orient="horizontal", variable = self.buffervar, maximum = 100)
        self.seconds = ttk.Label(self.top_panel, text = "00:00")
        self.text = scrolledtext.ScrolledText(self.bottom_panel, wrap = NONE, height = 0, relief = FLAT, font = ("Noto San", 12))
        self.dniwe = Frame(self)
        self.volume = ttk.Scale(self.dniwe, from_=0, to=1, command = self.volume_)
        self.svar = StringVar()
        self.search = ttk.Entry(self.dniwe, textvariable = self.svar)
        self.search.bind("<Return>", self.on_search)
        self.mode = ttk.Button(self.dniwe, text = "🔁", command = self.change_mode)
        self.pause = ttk.Button(self.top_panel, text = "⏯", command = self.on_pause, style = "Big.TButton")
        
        self.menu = Menu(self, tearoff=0)
        self.playlist = Menu(self.menu)
        self.playlist.add_command(label = "Refresh Folder", command = self.update_playlist)
        self.menu.add_cascade(label = "File", menu = self.playlist)

        self.top_panel.pack(side = TOP, fill = X, padx = 10, pady = 30)
        self.bottom_panel.pack(side = TOP, fill = BOTH, expand = True)
        self.play_btn.pack(side = LEFT)
        self.pause.pack(side = LEFT)
        self.scalebuf.pack(fill = X, expand = True, side = LEFT, padx = 5)
        self.scale.pack(fill = X)
        self.buffered.pack(fill = X)
        self.seconds.pack(side = RIGHT)
        self.text.pack(fill = BOTH, expand = True)
        self.dniwe.pack(side = BOTTOM, fill = X)
        self.search.pack(side = LEFT, padx = 10, pady = 10)
        self.mode.pack(side = LEFT, pady = 10)
        self.volume.pack(side = RIGHT, padx = 10)
        self.volume.bind("<ButtonRelease-1>", self.on_volume)

        self.geometry("600x500")
        self.after(1000, self.tick)
        self.configure(menu = self.menu)
        self.volume.set(0.5)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        #self.mainloop()

    def on_pause(self):
        if self.is_playing:
            self.is_playing = False
            self.playback_var.value = 0
        else:
            self.is_playing = True
            self.playback_var.value = 1

    def change_mode(self):
        self.mode_val += 1
        self.mode_val %= 3
        icon = "🔁⏩🔀"[self.mode_val]
        self.mode.config(text = icon)

    def on_close(self, event = None):
        #self.q.put(("rip","ded"))
        self.playback_var.value = 0
        self.stopper.value = 1
        if not self.miner is None and self.miner.is_alive():
            self.miner.kill()
        self.withdraw()
        #self = None
        #self.quit()
        #quit()

    def on_search(self, event):
        tags = self.svar.get().split(" ")
        self.text.delete("1.0", END)
        n = 1
        self.text.tag_config("grey", background = "#cccccc")
        gui = self.master
        music = [".mp3", ".wav", ".flac", ".ogg", ".wma"]
        self.text.config(state = NORMAL)
        self.text.delete("1.0", END)
        for file in self.files:
            if False in [tag.lower() in file.lower() for tag in tags]:
                continue

            if not True in [ext in file for ext in music]:
                continue
            self.text.window_create(f"{n}.0", window = SpecialButton(self.text, self, file))
            if n%2==0:
                self.text.insert(f"{n+1}.0", os.path.basename(file)+"\n", "grey")
            else:
                self.text.insert(f"{n+1}.0", os.path.basename(file)+"\n")
                #self.text.tag_add("grey", f"{n}.0", f"{n}.end")
            n+=1
        self.text.config(state = DISABLED)

    def update_playlist(self):
        gui = self.master
        music = [".mp3", ".wav", ".flac", ".ogg", ".wma"]
        self.text.config(state = NORMAL)
        url = f"{gui.server}/{gui.user}/{gui.password}/getfiles"
        directory = gui.var.get().replace("~/", f"/{gui.user}/",1)
        to_upload = {"file": compress(dict_to_bytes({"dir": directory}))}
        r = session.get(url, files = to_upload)
        self.text.tag_config("grey", background = "#cccccc")
        if r.status_code == 200:
            self.text.delete("1.0", END)
            r.raw.decode_content = True
            d = bytes_to_dict(decompress(r.content))
            n = 1
            self.files = [directory+f for f in list(d.keys())]
            for file in self.files:
                if not True in [ext in file for ext in music]:
                    continue
                self.text.window_create(f"{n}.0", window = SpecialButton(self.text, self, file))
                if n%2==0:
                    self.text.insert(f"{n+1}.0", os.path.basename(file)+"\n", "grey")
                else:
                    self.text.insert(f"{n+1}.0", os.path.basename(file)+"\n")
                    #self.text.tag_add("grey", f"{n}.0", f"{n}.end")
                n+=1
            """
            for key in list(d.keys()):
                win = Element(self.text, d[key], key)
                self.text.window_create(END, window = win)
                self.text.tag_add("centered","1.0",END)
                self.update()"""
        self.text.config(state = DISABLED)
        return
        self.text.delete("1.0", END)
        folder = filedialog.askdirectory()
        files = [i for i in glob(folder+"/*") if i.endswith(".mp3") or i.endswith(".wav") or i.endswith(".flac") or i.endswith(".wma")]
        self.files = files
        n = 1
        self.text.tag_config("grey", background = "#cccccc")
        self.fname = files[0]
        for file in files:
            self.text.window_create(f"{n}.0", window = SpecialButton(self.text, self, file))
            if n%2==0:
                self.text.insert(f"{n+1}.0", os.path.basename(file)+"\n", "grey")
            else:
                self.text.insert(f"{n+1}.0", os.path.basename(file)+"\n")
                #self.text.tag_add("grey", f"{n}.0", f"{n}.end")
            n+=1

    def on_volume(self, event):
        self.volume_var.value = int(30-30*self.volume.get())
        self.cutter.value = self.quarter_counter.value
        #self.is_playing = False
        #self.on_play()

    def on_play_legacy(self, lazy = False):
        self.title(f"Troy Music Player v1.1s - {self.fname.rsplit('/',1)[-1]}")
        if not self.is_playing:
            if not self.quarters:
                gui = self.master
                url = f"{gui.server}/{gui.user}/{gui.password}/getmus"
                to_upload = {"file": compress(dict_to_bytes({"file": self.fname, "volume": str(self.volume_var.value)}))}#file is the FULL path
                r = session.get(url, files = to_upload)
                if r.status_code == 200:
                    r.raw.decode_content = True
                    d = bytes_to_dict(decompress(r.content))
                    n = d.get("length")
                    self.seconds.config(text = timestamp(n))
                    self.q.put((d.get("quarters"), d.get("info")))
                    self.is_playing = True
                    self.playback_var.value = 1
            return
            n = len(pd.AudioSegment.from_file(self.fname))/1000
            self.seconds.config(text = timestamp(n))
            self.q.put(self.fname)
            self.is_playing = True
            self.playback_var.value = 1
        else:
            self.is_playing = False
            self.playback_var.value = 0

    def on_play(self, lazy = False):
        self.title(f"Troy Music Player v1.1s - {self.fname.rsplit('/',1)[-1]}")
        if not self.is_playing:
            if not self.quarters:
                if not self.process.is_alive():
                    self.process = Process(target = playback_stream, args = (self.q, self.volume_var, self.slider_var, self.playback_var, self.changed_var, self.quarter_list, self.quarter_counter))
                    self.process.start()
                gui = self.master
                url = f"{gui.server}/{gui.user}/{gui.password}/getmuslen"
                to_upload = {"file": compress(dict_to_bytes({"file": self.fname, "volume": str(self.volume_var.value)}))}#file is the FULL path
                self.stopper.value = 1
                while not self.miner is None and self.miner.is_alive():
                    self.miner.kill()
                self.quarter_list[:] = []
                self.slider_var.value = 0.0
                self.scale.set(0)
                self.changed_var.value = 1
                self.update()
                r = session.get(url, files = to_upload)
                if r.status_code == 200:
                    d = bytes_to_dict(decompress(r.content))
                    length = d.get("length")
                    self.buffered.config(maximum = int(length))
                    n = float(d.get("length2"))
                    self.info = d.get("info")
                    url = f"{gui.server}/{gui.user}/{gui.password}/getmuspart"
                    self.stopper.value = 0
                    self.miner = Process(target = music_miner, args = (url, length, self.quarter_list, self.fname, self.volume_var, self.slider_var, self.playback_var, self.changed_var, self.stopper, self.cutter))
                    self.miner.start()
                    self.q.put((self.info, length))
                    self.seconds.config(text = timestamp(n))
                    self.is_playing = True
                    while len(self.quarter_list[:])<4:#buffers for a second
                        sleep(0.01)
                        self.update()
                    self.playback_var.value = 1
                    return
                    r.raw.decode_content = True
                    d = bytes_to_dict(decompress(r.content))
                    n = d.get("length")
                    self.seconds.config(text = timestamp(n))
                    self.q.put((d.get("quarters"), d.get("info")))
                    self.is_playing = True
                    self.playback_var.value = 1
            return
            n = len(pd.AudioSegment.from_file(self.fname))/1000
            self.seconds.config(text = timestamp(n))
            self.q.put(self.fname)
            self.is_playing = True
            self.playback_var.value = 1
        else:
            self.is_playing = False
            self.playback_var.value = 0

    def tick(self):
        self.scale.config(value = self.slider_var.value)
        self.buffervar.set(len(self.quarter_list[:]))
        if self.slider_var.value==100.0:
            if self.mode_val==1:
                self.fname = self.files[self.files.index(self.fname)+1%len(self.files)]
                self.slider_var.value = 0.0
            elif self.mode_val==2:
                self.fname = choice(self.files)
                self.slider_var.value = 0.0
            else:
                self.slider_var.value = 0.0
                self.changed_var.value = 1
            self.is_playing = False
            self.on_play()
        self.after(50, self.tick)

    def volume_(self, event):
        self.volume_var.value = int(30-30*self.volume.get())

    def changed(self, event, recreate = False):
        self.slider_var.value = self.scale.get()
        self.changed_var.value = 1

class SpecialButton(ttk.Button):
    def __init__(self, parent, gigaparent, fname):
        super().__init__(parent, text = "•", command = self.callback, cursor = "hand2")
        self.fname = fname
        self.gp = gigaparent
    
    def callback(self):
        self.gp.fname = self.fname
        if self.gp.obj:
            self.gp.obj.stop()
        self.gp.is_playing = False
        self.gp.on_play()

if __name__=="__main__":
    #print(pd.__file__)#creationflags=0x08000000
    freeze_support()
    fix_popups()
    gui = Troy()
