# [[Info]]
# Pyguidialog - an overhaul of pygui's input class to return a dict
# object instead of a list, for increased development flexibility.
# 
# Dict keys are generated according to the rename() function, which
# means that it takes a label and only uses letters from it, in lower case.

from tkinter import *
from tkinter.ttk import *
#import sv_ttk
import tkinter.filedialog
from tkinter.scrolledtext import ScrolledText
import yaml
import os
import unicodedata
import re
from idlelib.tooltip import Hovertip

def smart_eval(text):
    recognized = ["None","True","False"]
    numerals = set("-0123456789.")
    if isinstance(text, str):
        if not text:
            return None
        if set(text).issubset(numerals):
            if "." in text:
                try:
                    return float(text)
                except Exception:
                    return text
            else:
                return int(text)
        elif text in recognized:
            return eval(text)
    return text

def rename(entry):
    key = ""
    for character in entry:
        if character.lower()!=character.upper():
            key+=character.lower()
    return key

def get_dict(parent, constructor_list):
    """Receives:
  parent: Tk, which will be the parent of the pop-up
  constructor_list: list, describes the pop-up shape and dict structure
Returns:
  dict, keys are made from constructor_list entries via 'rename' function"""
    return_dict = dict()
    keys = []
    prohibited = ["<ok>","<cache>"]
    for entry in constructor_list:
        if not isinstance(entry, str):
            if not entry[0] in prohibited:
                keys.append(rename(entry[1]))
        else:
            keys.append(rename(entry))
    inp = Input(parent, constructor_list)
    for n in range(len(keys)):
        return_dict[keys[n]] = smart_eval(inp.input[n])
    return return_dict

class Input(Toplevel):
    """The input class, collects labels as a list of tuples/strings,
strings default to Entry widgets"""
    def __init__(self, master, labels, **kwargs):
        super().__init__(**kwargs)
        self.resizable(True,False)
        self.master = master
        self.label_widgets = []
        self.interactive_widgets = []
        self.interactive_hooks = []
        self.rows = []
        self.commands = []
        self.cache = None
        self.cache_list = []
        self.ok = "Ok"#Ok button text
        self.bind("<Return>", self.action)
        try:
            wid = 2+max([len(i) for i in labels if isinstance(i,str)])# label width, in units
        except Exception as e:
            wid = 8
        for item in labels:
            if type(item)==str:
                self.rows.append( Frame(self, padding = (20,0,20,0)) )
                self.label_widgets.append( Label(self.rows[-1], text = item, width = wid, style = "Popup.TLabel") )
                self.interactive_hooks.append( StringVar() )
                self.interactive_widgets.append( Entry(self.rows[-1], textvariable = self.interactive_hooks[-1], style = "Popup.TEntry") )

                self.label_widgets[-1].pack(side = LEFT)
                self.interactive_widgets[-1].pack(side = LEFT, fill = X, expand = True)
                self.rows[-1].pack(fill = X)
            else:
                if item[0] == "<entry>":
                    self.rows.append( Frame(self, padding = (20,0,20,0)) )
                    self.label_widgets.append( Label(self.rows[-1], text = item[1], width = wid, style = "Popup.TLabel") )
                    self.interactive_hooks.append( StringVar(value = item[2]) )
                    self.interactive_widgets.append( Entry(self.rows[-1], textvariable = self.interactive_hooks[-1], style = "Popup.TEntry") )

                    self.label_widgets[-1].pack(side = LEFT)
                    self.interactive_widgets[-1].pack(side = LEFT, fill = X, expand = True)
                    self.rows[-1].pack(fill = X)
                elif item[0] == "<ok>":
                    self.ok = item[1]
                elif item[0] == "<cache>":
                    self.cache = item[1]+".cache"
                    if os.path.exists(self.cache):
                        with open(self.cache) as f:
                            self.cache_list = yaml.safe_load(f.read())
                elif item[0] == "<choice>":
                    self.rows.append( Frame(self, padding = (20,0,20,0)) )
                    self.label_widgets.append( Label(self.rows[-1], text = item[1], width = wid, style = "Popup.TLabel") )
                    self.interactive_hooks.append( StringVar() )
                    self.interactive_hooks[-1].set(item[2][0])
                    self.interactive_widgets.append( Combobox(self.rows[-1], textvariable = self.interactive_hooks[-1], values = item[2]) )

                    self.label_widgets[-1].pack(side = LEFT)
                    self.interactive_widgets[-1].pack(side = LEFT, fill = X, expand = True)
                    self.rows[-1].pack(fill = X)
                elif item[0] == "<slider>":
                    self.rows.append( Frame(self, padding = (20,0,20,0)) )
                    self.label_widgets.append( Label(self.rows[-1], text = item[1], width = wid, style = "Popup.TLabel") )
                    self.interactive_hooks.append( IntVar() )
                    self.interactive_widgets.append( CustomScale(self.rows[-1],
                                                           variable = self.interactive_hooks[-1],
                                                           from_ = item[2],
                                                           to = item[3]) )

                    self.label_widgets[-1].pack(side = LEFT)
                    self.interactive_widgets[-1].pack(side = LEFT, fill = X, expand = True)
                    self.rows[-1].pack(fill = X)
                elif item[0] == "<path>":
                    self.rows.append( Frame(self, padding = (20,0,20,0)) )
                    self.label_widgets.append( Label(self.rows[-1], text = item[1], width = wid, style = "Popup.TLabel") )
                    self.interactive_hooks.append( StringVar() )
                    exts = None if len(item)<3 else item[2]
                    self.interactive_widgets.append( Path(self.rows[-1],
                                                          self.interactive_hooks[-1],
                                                          exts) )

                    self.label_widgets[-1].pack(side = LEFT)
                    self.interactive_widgets[-1].pack(side = LEFT, fill = X, expand = True)
                    self.rows[-1].pack(fill = X)
                elif item[0] == "<out>":
                    self.rows.append( Frame(self, padding = (20,0,20,0)) )
                    self.label_widgets.append( Label(self.rows[-1], text = item[1], width = wid, style = "Popup.TLabel") )
                    self.interactive_hooks.append( StringVar() )
                    default = item[-1] if len(item)==4 else ""
                    exts = None if len(item)<3 else item[2]
                    self.interactive_widgets.append( Out(self.rows[-1],
                                                         self.interactive_hooks[-1],
                                                         exts,
                                                         default) )

                    self.label_widgets[-1].pack(side = LEFT)
                    self.interactive_widgets[-1].pack(side = LEFT, fill = X, expand = True)
                    self.rows[-1].pack(fill = X)
            if self.cache_list and self.interactive_hooks and labels[-1][0]!="<cache>":
                self.interactive_hooks[-1].set(self.cache_list.pop(0))
                if item[0] == "<slider>":
                    self.interactive_widgets[-1].right["text"] = str(self.interactive_hooks[-1].get())
            
        self.final_row = Frame(self, padding = (20,0,20,0))
        self.accept_button = Button(self.final_row, text = self.ok, command = self.action)
        self.accept_button.pack(fill = BOTH)
        self.final_row.pack(fill = X)
        self.mainloop()

    def action(self, event = None):
        self.input = []
        for item in self.interactive_hooks:
            self.input.append(item.get())
        if self.cache:
            with open(self.cache, "w") as f:
                f.write(yaml.dump(self.input))
        self.destroy()
        self.quit()

class InputText(Toplevel):
    def __init__(self, master):
        super().__init__()
        self.title("Recover image from ID or 4SDG")
        self.master = master
        self.text = ScrolledText(self)
        self.button = Button(self, text = "Generate", command = self.action)
        self.text.pack(fill = BOTH, expand = True)
        self.button.pack(fill = X)
        self.mainloop()

    def action(self):
        self.input_text = self.text.get("1.0", END)#################
        self.input = get_list(self.input_text)
        self.destroy()
        self.quit()

class CustomScale(Frame):
    def __init__(self, master, variable, from_, to):
        super().__init__(master)
        self.master = master
        self.var = variable
        #self.var.set(32)
        self.left = Scale(self, variable = self.var, command = self.callback, from_ = from_, to = to)
        self.right = Label(self, width = 3, style = "Custom.TLabel")
        self.left.pack(side = LEFT, fill = X, expand = True)
        self.right.pack(side = RIGHT)
        self.right["text"] = str(self.var.get())

    def callback(self, event):
        self.right["text"] = str(self.var.get())

class Path(Frame):
    def __init__(self, master, hook, exts = None):
        super().__init__(master)
        self.master = master
        self.hook = hook
        self.ent = Entry(self, textvariable = self.hook, style = "Popup.TEntry")
        self.but = Button(self, text = "?", width = 3, command = self.command)

        self.ent.pack(fill = X, expand = True, side = LEFT)
        self.but.pack(side = RIGHT)
        if not exts:
            self.exts = [("Lossless Graphics","*.png"),("Lossy Graphics","*.jpg"),("Other","*")]
        else:
            self.exts = exts

    def command(self):
        self.hook.set( tkinter.filedialog.askopenfilename(title = "Select image",
                                                            filetypes = self.exts) )
        self.master.focus_set()

class Out(Frame):
    def __init__(self, master, hook, exts = None, default = ""):
        super().__init__(master)
        self.master = master
        self.hook = hook
        self.ent = Entry(self, textvariable = self.hook, style = "Popup.TEntry")
        if default:
            self.hook.set(default)
        self.but = Button(self, text = "?", width = 3, command = self.command)

        self.ent.pack(fill = X, expand = True, side = LEFT)
        self.but.pack(side = RIGHT)
        if not exts:
            self.exts = [("Lossless Graphics","*.png"),("Lossy Graphics","*.jpg")]
        else:
            self.exts = exts

    def command(self):
        self.hook.set( tkinter.filedialog.asksaveasfilename(title = "Insert or select output filename",
                                                            defaultextension = ".png",
                                                            filetypes = self.exts) )
        self.master.focus_set()
