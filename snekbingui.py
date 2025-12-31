import requests
import os, re
from tkinter import *
from tkinter import ttk
from tkinter.filedialog import *
from tkinter.scrolledtext import ScrolledText
from PIL import Image, ImageTk, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
import shutil
from io import BytesIO
from viewer import MainWindow
from random import randint
from idlelib.tooltip import Hovertip
from pyguidialog import get_dict
from tkinter.messagebox import *
from glob import glob
from tkinterdnd2 import DND_FILES, TkinterDnD
from troymp import Troy
from snektools import *
import sv_ttk
from multiprocessing import Pool, cpu_count, freeze_support
from time import sleep

def update_folder_worker(incoming):
    url = incoming.pop("url")
    s = incoming.pop("session")
    retries = 0
    while 1:
        try:
            if retries>=10:
                return dict()
            r = s.get(url, files = incoming)
            r.raw.decode_content = True
            d = bytes_to_dict(decompress(r.content))
            break
        except Exception:
            sleep(0.05)
            retries+=1
    return d

class Progress(Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.value = DoubleVar(value=0.0)
        self.progressbar =  ttk.Progressbar(self, orient="horizontal", variable=self.value, maximum = 100.0)
        self.progressbar.pack(fill = X, expand = True)
        self.geometry("300x25")
        self.resizable(True, False)

class GUI(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        #s = ttk.Style()
        #s.theme_use('clam')
        if not os.name=="nt":
            sv_ttk.set_theme("light")
        #enable on linux
        self.title("SnekBin GUI")
        self.text = ScrolledText(self, relief = FLAT, wrap = CHAR, cursor = "arrow")
        self.history = ["~/"]
        self.changes = []
        self.geometry("500x300")
        #variables start
        self.s = requests.Session()
        self.troy = None #the music player has not been initialized
        self.server = "http://127.0.0.1:5000"
        self.user = "user"
        self.password = hashify("password")
        if os.path.exists("config.txt"):
            with open("config.txt") as f:
                entries = f.read().splitlines()
            self.server = entries[0]
            self.user = entries[1]
            self.password = hashify(entries[2])
        #variables end
        #menu start
        self.menubar = Menu(self)
        self.filemenu = Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(label="Connect", command=self.test)
        self.filemenu.add_command(label="Upload", command=self.upload, accelerator = "Ctrl+V")
        self.filemenu.add_command(label="Refresh", command=self.getdirs)
        self.filemenu.add_command(label="Search", command=self.getdirs, accelerator = "Ctrl+F")
        self.menubar.add_cascade(label="File", menu=self.filemenu)
        self.linkmenu = Menu(self.menubar, tearoff=0)
        self.linkmenu.add_command(label="List", command=self.list_links)
        self.linkmenu.add_command(label="Unshare All", command=self.remove_links)
        self.menubar.add_cascade(label="Links", menu=self.linkmenu)
        self.accmenu = Menu(self.menubar, tearoff=0)
        self.accmenu.add_command(label="Register", command=self.register)
        self.accmenu.add_command(label="Login", command=lambda self=self: self.login(force_login = True))
        self.accmenu.add_command(label="List Candidates", command=self.listlogin)
        self.accmenu.add_command(label="Verify Candidate", command=self.verify)
        self.menubar.add_cascade(label="Account", menu=self.accmenu)
        self.config(menu=self.menubar)
        #menu end
        #right click menu start
        self.menu = Menu(self, tearoff = 0)
        self.menu.add_command(label = "Create Folder", command = self.create_folder)
        self.menu.add_command(label = "Upload Files", command = self.upload)
        self.text.bind("<Button-3>", self.popup)
        #rcm end
        #top bar start
        self.topbar = Frame(self)
        self.topbar.pack(side = TOP)
        self.back_btn = ttk.Button(self.topbar, text = "Back", width = 5, command = self.go_back)
        self.up_btn = ttk.Button(self.topbar, text = "Up", width = 5, command = self.go_up)
        self.var = StringVar(value = "~/")
        self.path_box = ttk.Combobox(self.topbar, width = 5000, values = self.history, textvariable = self.var)
        self.back_btn.pack(side = LEFT)
        self.up_btn.pack(side = LEFT)
        self.path_box.pack(side = RIGHT, fill = X)
        #top bar end
        self.text.pack(fill = BOTH, expand = True, side = BOTTOM)

        self.path_box.bind('<<ComboboxSelected>>', self.update_folder3)
        self.text.tag_configure("centered", justify = "center")
        self.text.drop_target_register(DND_FILES)
        self.text.dnd_bind('<<Drop>>', self.dnd)
        self.bind('<Control-v>', self.paste)
        self.bind("<Control-f>", self.search)
        if self.test():
            self.getdirs()
            self.update_folder3()
        self.text.config(state = DISABLED)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.mainloop()

    def on_close(self):
        if not self.troy is None:
            self.troy.process.kill()
            try:
                self.troy.miner.kill()
            except Exception:
                pass
        self.quit()

    def search(self, event = None):
        l = [("<choice>", "Folder", self.history),
             "Pattern",
             ("<choice>", "Mode", ["Keyword","RegEx"])]
        d = get_dict(self, l)
        d["folder"] = d["folder"].replace("~/", f"/{self.user}/", 1)
        req = compress(dict_to_bytes(d))
        r = self.s.post(f"{self.server}/{self.user}/{self.password}/search", files = {"file": req})
        if r.status_code == 200:
            self.text.config(state = NORMAL)
            self.text.delete("1.0", END)
            self.var.set(f"Search: {d.get('pattern')}")
            r.raw.decode_content = True
            d = bytes_to_dict(decompress(r.content))
            for key in list(d.keys()):
                self.text.config(state = NORMAL)
                folder, value = key.rsplit("/",1)[0]+"/", d[key]
                print(key, value)
                win = Element(self.text, value, key.rsplit("/",1)[-1], folder)
                self.text.window_create(END, window = win)
                self.text.tag_add("centered","1.0",END)
                self.update()
                self.text.config(state = DISABLED)

    def dnd(self, event):
        path = self.var.get().replace("~/", f"/{self.user}/", 1)
        d = {"folder": path}
        d["files"] = dict()
        matches = re.finditer('({.+?}|[^ ]+)', event.data)
        results = [(m.group(0) if not m.group(0).startswith("{") else m.group(0)[1:-1]) for m in matches]# event.data[1:-1].split("} {")
        for file in results:
            d["files"][os.path.basename(file)] = open(file, "rb").read()
        req = compress(dict_to_bytes(d))
        if len(req)>1024**2*2:
            self.big_upload(req)
        else:
            r = self.s.post(f"{self.server}/{self.user}/{self.password}/save", files = {"file": req})

        self.update_folder3()

    def paste(self, event):
        path = self.var.get().replace("~/", f"/{self.user}/", 1)
        d = {"folder": path}
        d["files"] = dict()
        results = [i for i in self.clipboard_get().splitlines() if os.path.exists(i)]
        for file in results:
            d["files"][os.path.basename(file)] = open(file, "rb").read()
        req = compress(dict_to_bytes(d))
        if len(req)>1024**2*2:
            self.big_upload(req)
        else:
            r = self.s.post(f"{self.server}/{self.user}/{self.password}/save", files = {"file": req})

        self.update_folder3()

    def listlogin(self):
        r = self.s.post(f"{self.server}/{self.user}/{self.password}/listlogin")
        if r.status_code==200:
            LinkDisplay(self, r.text.replace(";","\n"))
        else:
            showerror("Admin Action", "Admin action failure!")

    def verify(self):
        l = ["User"]
        d = get_dict(self, l)
        bdict = compress(dict_to_bytes({"login": d["user"]}))
        r = self.s.post(f"{self.server}/{self.user}/{self.password}/conflogin", files = {"file": bdict})
        if r.text=="Success":
            showinfo("Registration Info", f"User {d['user']} registered!")
        else:
            showerror("Registration Info", "Validation failure!")

    def register(self):
        l = [("<cache>", "login"), "Server", "User", "Password"]
        info = get_dict(self, l)
        if self.login(info)=="err":
            return
        bdict = compress(dict_to_bytes({"login": self.user, "password": info.get("password")}))
        r = self.s.post(f"{self.server}/{self.user}/{self.password}/asklogin", files = {"file": bdict})
        if r.text=="Success":
            showinfo("Registration Info", "Registration entry created.\nWait until an admin validates\nthe account.")

    def login(self, d = None, force_login = False):
        if d is None:
            l = [("<cache>", "login"), "Server", "User", "Password"]
            d = get_dict(self, l)
        if ";" in d.get("user"):
            showerror("Registration Error", "Username cannot contain semicolons.")
            return "err"
        self.server = d.get("server")
        self.user = d.get("user")
        self.password = hashify(d.get("password"))
        with open("config.txt", "w") as f:
            f.write(f"{d['server']}\n{d['user']}\n{d['password']}")
        if force_login:
            if self.test():
                self.getdirs()
                self.update_folder3()
        return ""

    def list_links(self):
        url = f"{self.server}/{self.user}/{self.password}/listlinks"
        r = self.s.get(url)
        if r.status_code == 200:
            r.raw.decode_content = True
            d = bytes_to_dict(decompress(r.content))
            text = d.get("text")
            l = [f"{i.split(';')[0]}: {self.server}/{self.user}/{i.split(';')[1]}" for i in text.splitlines() if ";" in i]
            if not l:
                showwarning("List Links", "No links found!")
            else:
                LinkDisplay(self, "\n".join(l))

    def remove_links(self):
        if askyesno("Permanent Action Notice", "Do you really want\nto remove all external links?"):
            url = f"{self.server}/{self.user}/{self.password}/deletelinks"
            r = self.s.get(url)
            if r.status_code == 200:
                showinfo("Process Complete", "All links have been\nsuccessfully removed.")

    def big_upload(self, file):
        chunk = 1024**2//4
        focus = 0
        p = Progress(self)
        while focus<len(file):
            file_part = file[focus:focus+chunk] if focus+chunk<len(file) else file[focus:]
            self.s.post(f"{self.server}/{self.user}/{self.password}/savebig", files = {"file": file_part, "act": b"continue"})
            focus+=chunk
            p.value.set(100*focus/len(file))
            self.update()
        self.s.post(f"{self.server}/{self.user}/{self.password}/savebig", files = {"file": file_part, "act": b"terminate"})
        p.destroy()

    def popup(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def create_folder(self):
        folder_name = get_dict(self, ["Folder Name:"])["foldername"]
        path = self.var.get().replace("~/", f"/{self.user}/", 1)
        d = {"path": path, "folder": folder_name}
        req = compress(dict_to_bytes(d))
        r = self.s.post(f"{self.server}/{self.user}/{self.password}/mkdir", files = {"file": req})

        self.getdirs()
        self.update_folder3()

    def update_folder(self, event = None):
        self.text.config(state = NORMAL)
        self.changes.append(self.var.get())
        url = f"{self.server}/{self.user}/{self.password}/getfiles"
        to_upload = {"file": compress(dict_to_bytes({"dir": self.var.get().replace("~/", f"/{self.user}/", 1)}))}
        r = self.s.get(url, files = to_upload)
        self.history = []
        if r.status_code == 200:
            self.text.delete("1.0", END)
            with open("dirs.sd", 'wb') as f:
                r.raw.decode_content = True
                f.write(decompress(r.content))
            with open("dirs.sd","rb") as f:
                d = bytes_to_dict(f.read())
            for key in list(d.keys()):
                win = Element(self.text, d[key], key)
                self.text.window_create(END, window = win)
                self.text.tag_add("centered","1.0",END)
                self.update()
        self.text.config(state = DISABLED)

    def update_folder2(self, event = None):
        self.text.config(state = NORMAL)
        self.text.delete("1.0", END)
        self.changes.append(self.var.get())
        url = f"{self.server}/{self.user}/{self.password}/getfileslen"
        to_upload = {"file": compress(dict_to_bytes({"dir": self.var.get().replace("~/", f"/{self.user}/", 1)}))}
        r = self.s.get(url, files = to_upload)
        #self.history = []
        if r.status_code == 200:
            r.raw.decode_content = True
            d = bytes_to_dict(decompress(r.content))
            for n in range(d["length"]):
                url = f"{self.server}/{self.user}/{self.password}/getfilesnum"
                to_upload = {"file": compress(dict_to_bytes({"partition": n, "dir": self.var.get().replace("~/", f"/{self.user}/", 1)}))}
                r = self.s.get(url, files = to_upload)
                r.raw.decode_content = True
                d = bytes_to_dict(decompress(r.content))
                for key in list(d.keys()):
                    win = Element(self.text, d[key], key)
                    self.text.window_create(END, window = win)
                    self.text.tag_add("centered","1.0",END)
                    self.update()
        self.text.config(state = DISABLED)

    def update_folder3(self, event = None):
        self.text.config(state = NORMAL)
        self.text.delete("1.0", END)
        self.changes.append(self.var.get())
        url = f"{self.server}/{self.user}/{self.password}/getfileslen"
        to_upload = {"file": compress(dict_to_bytes({"dir": self.var.get().replace("~/", f"/{self.user}/", 1)}))}
        r = self.s.get(url, files = to_upload)
        #self.history = []
        if r.status_code == 200:
            r.raw.decode_content = True
            d = bytes_to_dict(decompress(r.content))
            to_pool = []
            for n in range(d["length"]):
                url = f"{self.server}/{self.user}/{self.password}/getfilesnum"
                to_upload = {"file": compress(dict_to_bytes({"partition": n, "dir": self.var.get().replace("~/", f"/{self.user}/", 1)}))}
                to_upload["url"] = url
                to_upload["session"] = self.s
                to_pool.append(to_upload)
            with Pool(cpu_count()) as p:
                for d in p.imap_unordered(update_folder_worker, to_pool):
                    for key in list(d.keys()):
                        win = Element(self.text, d[key], key)
                        self.text.window_create(END, window = win)
                        self.text.tag_add("centered","1.0",END)
                        self.update()
        self.text.config(state = DISABLED)

    def go_back(self):
        v = self.changes.pop()
        while v==self.var.get():
            v = self.changes.pop()
        self.var.set(self.changes.pop())
        self.update_folder3()

    def go_up(self):
        if self.var.get()!="~/":
            self.var.set("/".join(self.var.get().split("/")[:-2])+"/")
            self.update_folder3()

    def upload(self):
        path = self.var.get().replace("~/", f"/{self.user}/", 1)
        d = {"folder": path}
        d["files"] = dict()
        results = askopenfilenames()
        for file in results:
            d["files"][os.path.basename(file)] = open(file, "rb").read()
        req = compress(dict_to_bytes(d))
        if len(req)>1024**2*2:
            self.big_upload(req)
        else:
            r = self.s.post(f"{self.server}/{self.user}/{self.password}/save", files = {"file": req})

        self.update_folder3()

    def getdirs(self):
        url = f"{self.server}/{self.user}/{self.password}/getdirs"
        r = self.s.get(url)
        self.history = []
        if r.status_code == 200:
            d = bytes_to_dict(decompress(r.content))
            self.history = d["dirs"].split(";")
            self.path_box.configure(values = self.history)

    def test(self):
        url = f"{self.server}/{self.user}/{self.password}/test"
        try:
            r = self.s.get(url)
            if r.status_code==200 and r.text=="Success":
                self.title("SnekBin GUI [Connected]")
                return True
            else:
                self.title("SnekBin GUI [Disconnected]")
                return False
        except Exception:
            self.title("SnekBin GUI [Disconnected]")
            return False

    def _on_mousewheel(self, event):
        if isinstance(event, int):
            self.text.yview_scroll(int(-1*(event/120)), "units")
        else:
            self.text.yview_scroll(int(-1*(event.delta/120)), "units")

class LinkDisplay(Toplevel):
    def __init__(self, master, link):
        super().__init__(master)
        self.link = link
        self.text = Text(self, font = ("Courier", 14), wrap = NONE)
        self.text.pack(fill = BOTH, expand = True)
        self.text.insert("1.0", self.link)
        self.text.config(state = DISABLED)
        self.geometry("300x100")

class Element(ttk.Frame):
    def __init__(self, master, thing, fname, folder = None):
        super().__init__(master, width = 150, height = 200)
        self.s = self.master.master.master.s
        self.fname = fname
        self.thing = thing
        self.pack_propagate(0)
        self.button = ttk.Button(self, command = self.open_image, cursor = "hand2")
        self.menu = Menu(self, tearoff = 0)
        #TODO: program the copy functionality
        #self.menu.add_command(label = "Copy")
        self.menu.add_command(label = "Save As", command = self.save)
        self.menu.add_command(label = "Delete", command = self.delete)
        self.menu.add_command(label = "Rename", command = self.rename)
        self.menu.add_command(label = "Share", command = self.share)
        self.menu.add_command(label = "Unshare", command = self.unshare)
        if not folder is None:
            self.menu.add_command(label = "Open Folder", command = self.open_folder)
            self.folder = folder
        else:
            self.folder = None
        self.button.bind("<Button-3>", self.popup)
        self.button.pack(fill = BOTH, expand = True)
        self.label = Label(self, text = shorten(fname), bg = "white")
        self.label.pack(fill = X)
        if os.name=="nt":
            self.button.bind("<MouseWheel>", master.master.master._on_mousewheel)
            self.label.bind("<MouseWheel>", master.master.master._on_mousewheel)
        else:
            button = "<Button-4>"
            self.button.bind(button, lambda event, master=master: master.master.master._on_mousewheel(120))
            self.label.bind(button, lambda event, master=master: master.master.master._on_mousewheel(120))
            button = "<Button-5>"
            self.button.bind(button, lambda event, master=master: master.master.master._on_mousewheel(-120))
            self.label.bind(button, lambda event, master=master: master.master.master._on_mousewheel(-120))
        Hovertip(self.label, self.fname)
        if isinstance(thing, str):
            self.button.config(text = thing)
        else:
            self.image = thing.copy()
            self.tkimage = ImageTk.PhotoImage(self.image)
            self.button.config(image = self.tkimage)

    def rename(self):
        gui = self.master.master.master
        images = [".jpg",".jpeg",".png",".gif",".webp",".bmp"]
        d = get_dict(gui, [("<entry>", "New Name", self.fname)])
        if not checkname(d.get("newname")):
            showerror("Rename Action", "Name contains\nprohibited characters!")
            return
        if self.thing == "[...]":
            url = f"{gui.server}/{gui.user}/{gui.password}/rendir"
            original = gui.var.get().replace("~/", f"/{gui.user}/", 1)+self.fname+"/"
            new = d.get("newname")
            to_upload = {"file": compress(dict_to_bytes({"file": original, "name": new}))}
            r = self.s.get(url, files = to_upload)
            if r.status_code == 200:
                gui.update_folder3()
                gui.getdirs()
        else:
            url = f"{gui.server}/{gui.user}/{gui.password}/rename"
            #fs = {gui.var.get().replace("~/", f"/{gui.user}/", 1)+self.fname: ""}
            original = gui.var.get().replace("~/", f"/{gui.user}/", 1)+self.fname
            new = d.get("newname")
            to_upload = {"file": compress(dict_to_bytes({"file": original, "name": new}))}
            r = self.s.get(url, files = to_upload)
            if r.status_code == 200:
                gui.update_folder3()

    def open_folder(self):
        gui = self.master.master.master
        gui.var.set(self.folder)
        gui.update_folder3()

    def share(self):
        gui = self.master.master.master
        url = f"{gui.server}/{gui.user}/{gui.password}/share"
        to_upload = {"file": compress(dict_to_bytes({"dir": gui.var.get().replace("~/", f"/{gui.user}/", 1),
                                                     "file": self.fname}))}
        r = self.s.get(url, files = to_upload)
        LinkDisplay(gui, f"{gui.server}/{gui.user}/{r.text}")

    def unshare(self):
        gui = self.master.master.master
        url = f"{gui.server}/{gui.user}/{gui.password}/unshare"
        to_upload = {"file": compress(dict_to_bytes({"dir": gui.var.get().replace("~/", f"/{gui.user}/", 1),
                                                     "file": self.fname}))}
        r = self.s.get(url, files = to_upload)
        if r.status_code == 200:
            showinfo(title="Public Access Removal", message="Link Terminated")

    def delete(self):
        gui = self.master.master.master
        images = [".jpg",".jpeg",".png",".gif",".webp",".bmp"]
        if self.thing == "[...]":
            url = f"{gui.server}/{gui.user}/{gui.password}/deldir"
            fs = {gui.var.get().replace("~/", f"/{gui.user}/", 1)+self.fname+"/": ""}
            to_upload = {"file": compress(dict_to_bytes({"folders": fs}))}
            r = self.s.get(url, files = to_upload)
            if r.status_code == 200:
                gui.update_folder3()
                gui.getdirs()
        else:
            url = f"{gui.server}/{gui.user}/{gui.password}/delete"
            fs = {gui.var.get().replace("~/", f"/{gui.user}/", 1)+self.fname: ""}
            to_upload = {"file": compress(dict_to_bytes({"files": fs}))}
            r = self.s.get(url, files = to_upload)
            if r.status_code == 200:
                gui.update_folder3()

    def save(self):
        if self.thing == "[...]":
            showerror("Saving Error", "Can't save a FOLDER.")
            return
        path = asksaveasfilename(initialfile = self.fname, filetypes = [("Standard Extension","*."+self.fname.rsplit(".",1)[-1]),("Other","*.*")],defaultextension = self.fname.rsplit(".",1)[-1])#TODO: add extensions
        gui = self.master.master.master
        images = [".jpg",".jpeg",".png",".gif",".webp",".bmp"]
        url = f"{gui.server}/{gui.user}/{gui.password}/getfile"
        to_upload = {"file": compress(dict_to_bytes({"dir": gui.var.get().replace("~/", f"/{gui.user}/", 1), "file": self.fname}))}
        r = self.s.get(url, files = to_upload)
        if r.status_code == 200:
            r.raw.decode_content = True
            d = bytes_to_dict(decompress(r.content))
            if d.get("big") is None:
                d = bytes_to_dict(decompress(r.content))
                if True in [self.fname.lower().endswith(ext) for ext in images]:
                    #d["file"].save(path)
                    with open(path, "wb") as f:
                        f.write(d["file"])
                elif self.thing == "[...]":
                    pass#TODO: add error popup
                else:
                    ext = self.fname.rsplit(".",1)[-1]
                    fname = f"temp-{randint(0,1000)}.{ext}"
                    with open(path, "wb") as f:
                        f.write(d["file"])
            else:
                b = d["file"]
                
                p = Progress(gui)
                
                url = f"{gui.server}/{gui.user}/{gui.password}/getbigfile"
                is_big = maximal = d.get("big")
                n = 0
                while not is_big is None:
                    to_upload = {"file": compress(dict_to_bytes({"dir": gui.var.get().replace("~/", f"/{gui.user}/", 1),
                                                                 "file": self.fname,
                                                                 "partition": n}))}
                    
                    r = self.s.get(url, files = to_upload)
                    r.raw.decode_content = True
                    d = bytes_to_dict(decompress(r.content))
                    b+=d["file"]
                    is_big = d.get("big")
                    n+=1
                    p.value.set(100*n/maximal)
                    gui.update()
                p.destroy()

                with open(path, "wb") as f:
                    f.write(b)

    def popup(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def open_image(self):
        images = [".jpg",".jpeg",".png",".gif",".webp",".bmp"]
        music = [".mp3", ".wav", ".flac", ".ogg", ".wma"]
        gui = self.master.master.master

        if True in [self.fname.lower().endswith(ext) for ext in music]:
            url = f"{gui.server}/{gui.user}/{gui.password}/getmus"
            filename = (gui.var.get() if self.folder is None else self.folder).replace("~/", f"/{gui.user}/", 1) + self.fname
            if gui.troy is None:
                gui.troy = Troy(gui, filename)
                gui.troy.update_playlist()
                gui.troy.on_play()
            else:
                gui.troy.fname = filename
                gui.troy.deiconify()
                gui.troy.update_playlist()
                gui.troy.on_play()
            return
        
        url = f"{gui.server}/{gui.user}/{gui.password}/getfile"
        to_upload = {"file": compress(dict_to_bytes({"dir": (gui.var.get() if self.folder is None else self.folder).replace("~/", f"/{gui.user}/", 1), "file": self.fname}))}
        r = self.s.get(url, files = to_upload)
        if r.status_code == 200:
            r.raw.decode_content = True
            d = bytes_to_dict(decompress(r.content))
            if d.get("big") is None:
                if True in [self.fname.lower().endswith(ext) for ext in images]:
                    Viewer(gui, exif_rotate(d["file"]), self.fname)
                elif self.thing == "[...]":
                    gui.changes.append(gui.var.get())
                    gui.var.set(f"{gui.var.get()}{self.fname}/")
                    gui.update_folder3()
                else:
                    ext = self.fname.rsplit(".",1)[-1]
                    for to_del in glob("temp-*.*"):
                        os.remove(to_del)
                    fname = f"temp-{randint(0,1000)}.{ext}"
                    with open(fname, "wb") as f:
                        f.write(d["file"])
                    os.startfile(fname)
            else:
                b = d["file"]
                
                p = Progress(gui)
                
                url = f"{gui.server}/{gui.user}/{gui.password}/getbigfile"
                is_big = maximal = d.get("big")
                n = 0
                while not is_big is None:
                    to_upload = {"file": compress(dict_to_bytes({"dir": gui.var.get().replace("~/", f"/{gui.user}/", 1),
                                                                 "file": self.fname,
                                                                 "partition": n}))}
                    
                    r = self.s.get(url, files = to_upload)
                    r.raw.decode_content = True
                    d = bytes_to_dict(decompress(r.content))
                    b+=d["file"]
                    is_big = d.get("big")
                    n+=1
                    p.value.set(100*n/maximal)
                    gui.update()
                p.destroy()

                if True in [self.fname.lower().endswith(ext) for ext in images]:
                    #bio = BytesIO(b)
                    #bio.seek(0)
                    Viewer(gui, exif_rotate(b), self.fname)
                elif self.thing == "[...]":
                    gui.changes.append(gui.var.get())
                    gui.var.set(f"{gui.var.get()}{self.fname}/")
                    gui.update_folder3()
                else:
                    ext = self.fname.rsplit(".",1)[-1]
                    for to_del in glob("temp-*.*"):
                        os.remove(to_del)
                    fname = f"temp-{randint(0,1000)}.{ext}"
                    with open(fname, "wb") as f:
                        f.write(b)
                    os.startfile(fname)

class Viewer(Toplevel):
    def __init__(self, master, image, fname):
        super().__init__(master)
        app = MainWindow(self, image)
        self.title(fname)

class Tip(Hovertip):
    def position_window(self):
        """(re)-set the tooltip's screen position"""
        x, y = self.get_position()
        root_x = self.anchor_widget.winfo_rootx() + x - self.anchor_widget.winfo_width()
        root_y = self.anchor_widget.winfo_rooty() + y
        self.tipwindow.wm_geometry("+%d+%d" % (root_x, root_y))

    def showcontents(self):
        label = Label(self.tipwindow, text=self.text, justify=LEFT,
                      relief=SOLID, font=("Segoe UI", 12), borderwidth=0,
                      background=background, foreground=foreground,
                      padx=10, pady=10)
        label.pack()

if __name__=="__main__":
    freeze_support()
    gui = GUI()
