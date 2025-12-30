from flask import Flask, redirect, url_for, render_template, render_template_string, request, send_file, send_from_directory, session
import os
import cv2
import shelve
from random import randint, choice
from io import BytesIO
import zlib
from PIL import Image, ImageTk
from glob import glob
from functools import lru_cache
import re
import pydub as pd #requires ffmpeg installed on machine
import pyaudio

def get_music_info(fname):
    full = os.popen(f'mediainfo "{fname}"').read()
    d = dict()
    for line in full.splitlines():
        if line.startswith("Sampling rate"):
            d["sample_rate"] = str(int(1000*float(line.split(":",1)[-1].split(" ")[1])))
        elif line.startswith("Channel(s)"):
            d["channels"] = line.split(":",1)[-1].split(" ")[1]
    return d

@lru_cache(maxsize = 16)
def quarters_from_file(user, fname, value):
    ext = fname.rsplit(".",1)[-1]
    for f in glob(f"{user}/mus-*"):
        if not f.endswith(f"mus-{hashify(fname)}.{ext}"):
            try:
                os.remove(f)
            except Exception:
                pass
    if os.path.exists(f"{user}/mus-{hashify(fname)}.{ext}"):
        pass
    else:
        with open(f"{user}/mus-{hashify(fname)}.{ext}", "wb") as f:
            f.write(value)
    ogmix = pd.AudioSegment.from_file(f"{user}/mus-{hashify(fname)}.{ext}")
    length = len(ogmix)
    quarters = []
    index = 0
    try:
        while index<len(ogmix):
            quarters.append(ogmix[index:index+250])
            index+=250
    except Exception:
        quarters.append(ogmix[index:])

    return quarters, length, {**pd.utils.mediainfo(fname), **{"format": pyaudio.PyAudio().get_format_from_width(ogmix.sample_width), "lenogmix": int(len(ogmix)/1000)}}
    

def get_quarters_new(user, fname, value, volume, part_n = -1):
    ext = fname.rsplit(".",1)[-1]
    quarters, length, info = quarters_from_file(user, fname, value)
    focus = 0 if part_n==-1 else part_n
    maximal = len(quarters)
    qd = dict()
    while (focus<maximal and part_n==-1) or (focus<part_n+16):# 4 corresponds to 1 s of playback
        try:
            sound = quarters[focus] - int(volume)
            qd[str(focus)] = bytes(sound.get_array_of_samples())
            focus+=1
        except IndexError:
            qd[str(focus)] = b""
            focus+=1
    if not info:
        try:
            info = get_music_info(f"{user}/mus-{hashify(fname)}.{ext}")
        except Exception:
            info = {"channels": "2", "sample_rate": "44100"}
    return qd, {"channels": info.get("channels"),
                "sample_rate": info.get("sample_rate"),
                "format": info.get("format")}, str(info.get("lenogmix"))

def get_quarters(user, fname, value, volume, part_n = -1):
    ext = fname.rsplit(".",1)[-1]
    for f in glob(f"{user}/mus-*"):
        if not f.endswith(f"mus-{hashify(fname)}.{ext}"):
            try:
                os.remove(f)
            except Exception:
                pass
    if os.path.exists(f"{user}/mus-{hashify(fname)}.{ext}"):
        pass
    else:
        with open(f"{user}/mus-{hashify(fname)}.{ext}", "wb") as f:
            f.write(value)
    ogmix = pd.AudioSegment.from_file(f"{user}/mus-{hashify(fname)}.{ext}")
    length = len(ogmix)
    quarters = []
    index = 0
    try:
        while index<len(ogmix):
            quarters.append(ogmix[index:index+250])
            index+=250
    except Exception:
        quarters.append(ogmix[index:])
    focus = 0 if part_n==-1 else part_n
    maximal = len(quarters)
    info = pd.utils.mediainfo(fname)#send to client
    qd = dict()
    while (focus<maximal and part_n==-1) or (focus<part_n+16):# 4 corresponds to 1 s of playback
        try:
            sound = quarters[focus] - int(volume)
            qd[str(focus)] = bytes(sound.get_array_of_samples())
            focus+=1
        except IndexError:
            qd[str(focus)] = b""
            focus+=1
    #if info.get("channels") is None: info["channels"] = "2"
    #if info.get("sample_rate") is None: info["sample_rate"] = "44100"
    if not info:
        try:
            info = get_music_info(f"{user}/mus-{hashify(fname)}.{ext}")
        except Exception:
            info = {"channels": "2", "sample_rate": "44100"}
    return qd, {"channels": info.get("channels"),
                "sample_rate": info.get("sample_rate"),
                "format": pyaudio.PyAudio().get_format_from_width(ogmix.sample_width)}, len(ogmix)/1000

def hashify(text:str):
  h=0
  for ch in text:
    h = ( h*281  ^ ord(ch)*997) & 0xFFFFFFFF
  return str(h)

def random_link(length = 16):
    abc = "qwertyuiopasdfghjklzxcvbnm"+"qwertyuiopasdfghjklzxcvbnm".upper()+"1234567890"
    link = ""
    while len(link)<length:
        link += choice(abc)
    return link

def del_addr(d, pathlets):
    d2 = dict()
    for key in list(d.keys()):
        if len(pathlets)==1:
            if key==pathlets[0]:
                pass
            else:
                d2[key] = d.get(key)
        else:
            if key==pathlets[0] and isinstance(d.get(key), dict):
                d2[key] = del_addr(d.get(key), pathlets[1:])
            else:
                d2[key] = d.get(key)
    return d2
                

def recursive_del(d, target):
    for key in list(d.keys()):
        if isinstance(d.get(key), dict):
            d[key] = recursive_del(d.get(key), target)
        else:
            if d.get(key)==target:
                d.pop(key)
    return d

def count_ids(d, id_, summa):
    if isinstance(d, dict):
        for key in list(d.keys()):
            if isinstance(d.get(key), int) and d.get(key)==id_:
                summa += 1
            else:
                summa += count_ids(d.get(key), id_, 0)
    return summa

def remove_folder(user, password, folder):
    link_db = f"{user}/links"
    content_db = f"{user}/content"
    if os.path.exists(f"{user}.login"):
        if hashify(read(f"{user}.login"))==password:
            with shelve.open(link_db) as ldb:
                pathlets = folder.replace("~/", f"/{user}/").split("/")[1:-1]
                dictionary = {**ldb}
                for pathlet in pathlets:
                    dictionary = dictionary[pathlet]
                for fname in list(dictionary.keys()):
                    if isinstance(dictionary.get(fname), int):
                        remove_file(user, password, folder+fname)
                    else:
                        remove_folder(user, password, folder+fname+"/")
                        ldb.update(del_addr(dict(ldb), pathlets))

def remove_file(user, password, path):
    link_db = f"{user}/links"
    content_db = f"{user}/content"
    if os.path.exists(f"{user}.login"):
        if hashify(read(f"{user}.login"))==password:
            with shelve.open(link_db) as ldb:
                pathlets = path.replace("~/", f"/{user}/").split("/")[1:]
                dictionary = {**ldb}
                for pathlet in pathlets:
                    dictionary = dictionary[pathlet]
                id_ = dictionary
                id_count = count_ids(dict(ldb), id_, 0)
                recursive_del(ldb, id_)
                if id_count==1:
                    with shelve.open(content_db) as cdb:
                        cdb.pop(str(id_))

def recursive_rename(dictionary, pathlets, name):
    if len(pathlets)>1:
        item = dictionary.get(pathlets[0])
        dictionary[pathlets[0]] = recursive_rename(item, pathlets[1:], name)
    else:
        item = dictionary.pop(pathlets[0])
        dictionary[name] = item
    return dictionary

def rename_file(user, password, path, name):
    link_db = f"{user}/links"
    content_db = f"{user}/content"
    if os.path.exists(f"{user}.login"):
        if hashify(read(f"{user}.login"))==password:
            with shelve.open(link_db) as ldb:
                pathlets = path.replace("~/", f"/{user}/").split("/")[1:]
                recursive_rename(ldb, pathlets, name)

def rename_folder(user, password, path, name):
    link_db = f"{user}/links"
    content_db = f"{user}/content"
    if os.path.exists(f"{user}.login"):
        if hashify(read(f"{user}.login"))==password:
            with shelve.open(link_db) as ldb:
                pathlets = path.replace("~/", f"/{user}/").split("/")[1:-1]
                recursive_rename(ldb, pathlets, name)

def preview(fname, content, full = False):
    if True in [fname.lower().endswith(ext) for ext in (".jpg",".jpeg",".png",".gif",".webp")]:
        image = bytes_to_pil(content)
        if not full:
            image.thumbnail((100,100))
        return image.copy()
    elif True in [fname.lower().endswith(ext) for ext in (".mp4",".webm",".avi")]:
        image = video_thumbnail(content)
        if not full:
            image.thumbnail((100,100))
        return image.copy()
    else:
        return f"[{fname.rsplit('.',1)[-1].upper()}]"

def obtain_id(dictionary, pathlets):
    if len(pathlets)>1:
        return obtain_id(dictionary[pathlets[0]], pathlets[1:])
    else:
        return dictionary[pathlets[0]]

def all_dirs(dictionary, dir_list, base):
    for key in list(dictionary.keys()):
        if isinstance(dictionary.get(key), dict):
            segment = f"{base}/{key}/" if not base.endswith("/") else f"{base}{key}/"
            dir_list.append(segment)
            dir_list.extend(all_dirs(dictionary.get(key),[], segment))
    return dir_list

def add_id(dictionary, pathlets, id_):
    if dictionary.get(pathlets[0]) is None:
        dictionary[pathlets[0]] = dict()
    if len(pathlets)>1:
        dictionary[pathlets[0]] = add_id(dictionary[pathlets[0]], pathlets[1:], id_)
        return dictionary
    else:
        if isinstance(id_, int):
            return dictionary | {pathlets[0]: id_}
        else:#dict id
            dictionary[pathlets[0]] = dictionary[pathlets[0]] | id_
            return dictionary

def from_folder_len(path, user, password):
    link_db = f"{user}/links"
    content_db = f"{user}/content"
    if os.path.exists(f"{user}.login"):
        if hashify(read(f"{user}.login"))==password:
            with shelve.open(link_db) as ldb:
                pathlets = path.replace("~/", f"/{user}/").split("/")[1:-1]
                dictionary = {**ldb}
                for pathlet in pathlets:
                    dictionary = dictionary[pathlet]
            return len(list(dictionary.keys()))

def from_folder(path, user, password):
    link_db = f"{user}/links"
    content_db = f"{user}/content"
    if os.path.exists(f"{user}.login"):
        if hashify(read(f"{user}.login"))==password:
            with shelve.open(link_db) as ldb:
                pathlets = path.replace("~/", f"/{user}/").split("/")[1:-1]
                dictionary = {**ldb}
                for pathlet in pathlets:
                    dictionary = dictionary[pathlet]
            d = dict()
            with shelve.open(content_db) as ldb:
                for key in list(dictionary.keys()):
                    if type(dictionary.get(key))==int:
                        d[key] = ldb[str(dictionary[key])]
                    else:
                        d[key] = "[...]"
            return d

def from_folder_search(path, user, password, what, how, cdb = None):
    link_db = f"{user}/links"
    content_db = f"{user}/content"
    if os.path.exists(f"{user}.login"):
        if hashify(read(f"{user}.login"))==password:
            with shelve.open(link_db) as ldb:
                pathlets = path.replace("~/", f"/{user}/").split("/")[1:-1]
                dictionary = {**ldb}
                for pathlet in pathlets:
                    dictionary = dictionary[pathlet]
            allfiles = dict()
            if cdb is None:
                with shelve.open(content_db) as cdb:
                    for key in list(dictionary.keys()):
                        if type(dictionary.get(key))==int:
                            if (how=="Keyword" and what in key) or (how=="RegEx" and not re.match(what, key) is None):
                                p = "/".join([""]+pathlets+[key]).replace(f"/{user}/", "~/",1)
                                allfiles[p] = dictionary.get(key)
                        else:
                            parent = "/".join([""]+pathlets+[key]).replace(f"/{user}/", "~/",1)+"/"
                            allfiles = {**allfiles, **from_folder_search(parent, user, password, what, how, cdb)}
            else:
                for key in list(dictionary.keys()):
                    if type(dictionary.get(key))==int:
                        if (how=="Keyword" and what in key) or (how=="RegEx" and not re.match(what, key) is None):
                            p = "/".join([""]+pathlets+[key]).replace(f"/{user}/", "~/",1)
                            allfiles[p] = dictionary.get(key)
                    else:
                        parent = "/".join([""]+pathlets+[key]).replace(f"/{user}/", "~/",1)+"/"
                        allfiles = {**allfiles, **from_folder_search(parent, user, password, what, how, cdb)}

            return allfiles

def from_folder_file(path, user, password, file):
    link_db = f"{user}/links"
    content_db = f"{user}/content"
    if os.path.exists(f"{user}.login"):
        if hashify(read(f"{user}.login"))==password:
            with shelve.open(link_db) as ldb:
                pathlets = path.replace("~/", f"/{user}/").split("/")[1:-1]
                dictionary = {**ldb}
                for pathlet in pathlets:
                    dictionary = dictionary[pathlet]
            d = b""#bytes of the needed file
            if isinstance(file, str):
                with shelve.open(content_db) as ldb:
                    for key in list(dictionary.keys()):
                        if type(dictionary.get(key))==int:
                            if key==file:
                                d = ldb[str(dictionary[key])]
            elif isinstance(file, int):
                with shelve.open(content_db) as ldb:
                    for n, key in enumerate(list(dictionary.keys())):
                        if type(dictionary.get(key))==int:
                            if n==file:
                                d = ldb[str(dictionary[key])]
                                return key, d
                        else:
                            if n==file:
                                d = "[...]"
                                return key, d
            return d

def get_dirs(user, password):
    link_db = f"{user}/links"
    if os.path.exists(f"{user}.login"):
        if hashify(read(f"{user}.login"))==password:
            with shelve.open(link_db) as ldb:
                result = all_dirs(dict(ldb), [], "")
            return result

def make_dir(user, password, path, folder):#operates with links and data
    if os.path.exists(f"{user}.login"):
        if hashify(read(f"{user}.login"))==password:
            if not os.path.exists(user):
                os.mkdir(user)
            link_db = f"{user}/links"
            content_db = f"{user}/content"
            pathlets = path.split("/")[1:-1]
            with shelve.open(link_db) as ldb:
                recent = add_id(dict(ldb), pathlets, {folder: dict()})
                ldb.update(recent)

def save_file(user, password, path, content):#operates with links and data
    if os.path.exists(f"{user}.login"):
        if hashify(read(f"{user}.login"))==password:
            if not os.path.exists(user):
                os.mkdir(user)
            link_db = f"{user}/links"
            content_db = f"{user}/content"
            pathlets = path.split("/")[1:-1] if path.split("/")[-1]=="" else path.split("/")[1:]
            with shelve.open(link_db) as ldb:
                id_ = ldb.get("total")
                if id_ is None:
                    id_ = ldb["total"] = 0
                passed = []
                recent = add_id(dict(ldb), pathlets, id_)
                ldb.update(recent)
                ldb["total"] += 1
            with shelve.open(content_db) as cdb:
                cdb[str(id_)] = content

def hide_path(path):
    if os.path.isfile(path):
        return path.split("/",1)[1]
    else:
        if not path.endswith("/"):
            path += "/"
        return path.split("/",1)[1]

def compress(b):
    return zlib.compress(b, 9)

def decompress(b):
    return zlib.decompress(b)

def read(fname):
    with open(fname) as f:
        whole = f.read()
    return whole

def join_path(*parts):
    path = ""
    for part in parts:
        if path.endswith("/"):
            if part.startswith("/"):
                path+=part[1:]
            else:
                path+=part
        else:
            if part.startswith("/"):
                path+=part
            else:
                path+="/"+part
    return path

def to_pil(imgOpenCV):
    return Image.fromarray(cv2.cvtColor(imgOpenCV, cv2.COLOR_BGR2RGB))

def bytes_to_pil(bytes_):
    bio = BytesIO(bytes_)
    bio.seek(0)
    return Image.open(bio)

@lru_cache(maxsize = 128)
def video_thumbnail(content, user):
    #bio = BytesIO()
    #bio.write(content)
    #bio.seek(0)
    with open(f"{user}/temp.vid", "wb") as f:
        f.write(content)
    vidcap = cv2.VideoCapture(f"{user}/temp.vid")#(bio)
    video_length = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))
    success,image = vidcap.read()
    count = 0
    if 0:
        while success and count<0.25*video_length:
            success, image = vidcap.read()
            count += 1
    else:
        vidcap.set(cv2.CAP_PROP_POS_FRAMES, int(0.25*video_length))
        success, image = vidcap.read()
    pimg = to_pil(image)
    pimg.thumbnail((200,200))
    return pimg

def pil_to_bytes(pil_image):
    image = pil_image.convert("RGBA")
    with BytesIO() as output:
        image.save(output, format="PNG", optimize = True, progressive = True, quality = 85)
        contents = output.getvalue()
    return contents#zlib.compress(contents, 9)

def bytes_to_pil(bytes_):
    bio = BytesIO(bytes_)
    bio.seek(0)
    return Image.open(bio)

def checktype(file, content):
    images = [".jpg",".jpeg",".png",".gif",".webp",".bmp"]
    videos = [".mp4",".webm",".avi"]
    if True in [file.lower().endswith(ext) for ext in images]:
        return content #bytes_to_pil(content).convert("RGBA")
    elif True in [file.lower().endswith(ext) for ext in videos]:
        return content
    else:
        return content

def thumbnailify(d, user):
    images = [".jpg",".jpeg",".png",".gif",".webp",".bmp"]
    videos = [".mp4",".webm",".avi"]
    d2 = dict()
    for file in list(d.keys()):
        if True in [file.lower().endswith(ext) for ext in images]:
            d2[file] = bytes_to_pil(d[file]).convert("RGBA")
            d2[file].thumbnail((150,150))
        elif True in [file.lower().endswith(ext) for ext in videos]:
            #with open("temp.vid", "wb") as f:
            #    f.write(d[file])
            d2[file] = video_thumbnail(d[file], user)#("temp.vid")
            d2[file].thumbnail((150,150))
            #os.remove("temp.vid")
        elif d[file]== "[...]":
            d2[file] = "[...]"
        else:
            d2[file] = f"[{file.rsplit('.',1)[-1].upper()}]"
    return d2

def dict_to_bytes(d):
    b = b""
    l = []
    for key in list(d.keys()):
        l.append(key)
        l.append(str(type(d[key])).split("'")[1])
        l.append(d[key])
    for let in l:
        match str(type(let)).split("'")[1]:
            case "str":
                content = bytes(let, "utf-8")
            case "int":
                content = let.to_bytes(length = 4, byteorder = "big", signed = True)
            case "bytes":
                content = let
            case "dict":
                content = dict_to_bytes(let)
            case "PIL.Image.Image":
                content = pil_to_bytes(let)
            case _:
                content = bytes("None", "utf-8")
        byteness = 1
        while 256**byteness<len(content):
            byteness += 1
        #int.to_bytes(
        total = bytes([byteness])+len(content).to_bytes(length = byteness, byteorder = "big")+content
        b += total
    return b

def bytes_to_dict(b):
    bs = []
    focus = 0
    while focus<len(b):
        length = int.from_bytes(b[focus+1:focus+b[focus]+1], "big")
        content = b[focus+b[focus]+1:focus+b[focus]+1+length]
        bs.append(content)
        focus = focus+b[focus]+1+length
    d = dict()
    for n in range(0, len(bs), 3):
        key, dtype, value = bs[n:n+3]
        key = str(key, "utf-8")
        dtype = str(dtype, "utf-8")
        match dtype:
            case "str":
                content = str(value, "utf-8")
            case "int":
                content = int.from_bytes(value, "big", signed = False)
            case "bytes":
                content = value
            case "dict":
                content = bytes_to_dict(value)
            case "PIL.Image.Image":
                content = bytes_to_pil(value)
            case _:
                content = "None"
        d[key] = content
    return d

class AuthError(Exception):
    def __init__(self, user, password, message="Invalid authorization request!\nInvalid combinmation: User({user}, Password({password}))"):
        self.message = message.format(user = user, password = password)
        super().__init__(self.message)

app = Flask(__name__)

@app.route("/<user>/<key>", methods=['post', 'get'])
def public_links(user, key):
    with shelve.open(f"{user}/public") as db:
        folder, file, user, password = db[key]
    dfile = from_folder_file(folder, user, password, file)
    byte_obj = BytesIO()
    byte_obj.write(dfile)
    byte_obj.seek(0)
    return send_file(
                byte_obj, 
                as_attachment=True, 
                download_name=file,
                )

@app.route("/<user>/<password>/<action>", methods=['post', 'get'])
def communication_manager(user, password, action):
    if action!="asklogin":
        if os.path.exists(f"{user}.login"):
            if hashify(read(f"{user}.login"))!=password:
                raise AuthError(user, password)
            else:
                if not os.path.exists(user):
                    os.mkdir(user)
        else:
            raise AuthError(user, password)
    match action:
        case "test":
            return "Success"
        case "rendir":
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            rename_folder(user, password, d["file"], d["name"])
            return "Success"
        case "rename":
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            rename_file(user, password, d["file"], d["name"])
            return "Success"
        case "getmuspart":
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            directory, file = d["file"].rsplit("/",1)
            directory+="/"
            value = from_folder_file(directory, user, password, file)
            qd, info, length = get_quarters_new(user, file, value, float(d["volume"]), d.get("part"))
            data = compress(dict_to_bytes({"quarters": qd, "info": info, "length": int(length)}))
            byte_obj = BytesIO()
            byte_obj.write(data)
            byte_obj.seek(0)
            return send_file(
                byte_obj, 
                as_attachment=True, 
                download_name="res.sd",
                )
        case "getmuslen":
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            directory, file = d["file"].rsplit("/",1)
            directory+="/"
            value = from_folder_file(directory, user, password, file)
            qd, info, length = get_quarters(user, file, value, float(d["volume"]))
            data = compress(dict_to_bytes({"length": len(list(qd.keys())), "info": info, "length2": str(length)}))
            byte_obj = BytesIO()
            byte_obj.write(data)
            byte_obj.seek(0)
            return send_file(
                byte_obj, 
                as_attachment=True, 
                download_name="res.sd",
                )
        case "getmus":
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            directory, file = d["file"].rsplit("/",1)
            directory+="/"
            value = from_folder_file(directory, user, password, file)
            qd, info, length = get_quarters(user, file, value, float(d["volume"]))
            data = compress(dict_to_bytes({"quarters": qd, "info": info, "length": int(length)}))
            byte_obj = BytesIO()
            byte_obj.write(data)
            byte_obj.seek(0)
            return send_file(
                byte_obj, 
                as_attachment=True, 
                download_name="res.sd",
                )
        case "listlogin":
            admins = glob("*.admin")
            for admin in admins:
                adpass = hashify(read(admin))
                adlog = admin.rsplit(".",1)[0]

                if user==adlog and adpass==password:
                    return ";".join([line.split(";",1)[0] for line in read("candidates.txt").splitlines()])
                else:
                    1/0
        case "conflogin":
            admins = glob("*.admin")
            for admin in admins:
                adpass = hashify(read(admin))
                adlog = admin.rsplit(".",1)[0]

                if user==adlog and adpass==password:
                    d = bytes_to_dict(decompress(request.files.get("file").read()))
                    ulog = d["login"]
                    print(ulog)
                    for entry in read("candidates.txt").splitlines():
                        if entry.startswith(ulog+";"):
                            passw = entry.split(";",1)[1]
                            with open(f"{ulog}.login", "w") as f:
                                f.write(passw)
                            return "Success"
                        else:
                            print(entry, ulog)
        case "asklogin":
            if not os.path.exists("candidates.txt"):
                cand = []
            else:
                cand = read("candidates.txt").splitlines()
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            cand.append(f"{d['login']};{d['password']}")
            with open("candidates.txt", "w") as f:
                f.write("\n".join(cand))
            return "Success"
        case "deletelinks":
            with shelve.open(f"{user}/public") as db:
                for key in list(db.keys()):
                    db.pop(key)
            return "Success"
        case "listlinks":
            data = []
            with shelve.open(f"{user}/public") as db:
                for key in list(db.keys()):
                    folder, file, user, password = db[key]
                    data.append(f"{folder}{file};{key}")
            data = compress(dict_to_bytes({"text": "\n".join(data)}))
            byte_obj = BytesIO()
            byte_obj.write(data)
            byte_obj.seek(0)
            return send_file(
                byte_obj, 
                as_attachment=True, 
                download_name="res.sd",
                )
        case "unshare":
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            file = d.get("file")
            folder = d["dir"]
            rlink = random_link()
            example = [folder, file, user, password]
            with shelve.open(f"{user}/public") as db:
                for key in db.keys():
                    identical = True
                    from_db = db[key]
                    for n in range(4):
                        if from_db[n]!=example[n]:
                            identical = False
                            break
                    if identical:
                        db.pop(key)
                        break
        case "share":
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            file = d.get("file")
            folder = d["dir"]
            rlink = random_link()
            with shelve.open(f"{user}/public") as db:
                db[rlink] = [folder, file, user, password]
            return rlink
        case "savebig":
            if not glob("*.big"):
                request.files.get("file").save("temp.big")
            else:
                fname = sorted(glob("*.big"))[0]
                if request.files.get("act").read()==b"continue":
                    with open(fname, "ab") as f:
                        f.write(request.files.get("file").read())
                else:
                    with open(fname, "rb") as f:
                        d = bytes_to_dict(decompress(f.read()))
                    os.remove(fname)
                    destination = d["folder"]
                    for file in list(d["files"].keys()):
                        save_file(user, password, f"{destination}{file}", d["files"][file])
        case "deldir":
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            ddel = d["folders"]
            for folder in list(ddel.keys()):
                remove_folder(user, password, folder)
        case "delete":
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            ddel = d["files"]
            for file in list(ddel.keys()):
                remove_file(user, password, file)
        case "mkdir":#creates a new folder withing current scope
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            path, folder = d.get("path"), d.get("folder")
            make_dir(user, password, path, folder)
        case "save":#saves a list of files in the db
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            destination = d["folder"]
            for file in list(d["files"].keys()):
                save_file(user, password, f"{destination}{file}", d["files"][file])
        case "getfilesnum":
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            folder = d["dir"]
            n = d["partition"]
            fname, dfile = from_folder_file(folder, user, password, n)
            dfiles = {fname: dfile}
            dfiles = thumbnailify(dfiles, user)
            byte_obj = BytesIO()
            byte_obj.write(compress(dict_to_bytes(dfiles)))
            byte_obj.seek(0)
            return send_file(
                byte_obj, 
                as_attachment=True, 
                download_name="res.sd",
                )
        case "getfileslen":
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            folder = d["dir"]
            length = from_folder_len(folder, user, password)
            byte_obj = BytesIO()
            byte_obj.write(compress(dict_to_bytes({"length": length})))
            byte_obj.seek(0)
            return send_file(
                byte_obj, 
                as_attachment=True, 
                download_name="res.sd",
                )
        case "getfiles":
            temp = f"req-{randint(0,1000)}.sd"
            request.files.get("file").save(temp)
            with open(temp, "rb") as f:
                d = bytes_to_dict(decompress(f.read()))
            folder = d["dir"]
            dfiles = from_folder(folder, user, password)
            dfiles = thumbnailify(dfiles, user)
            byte_obj = BytesIO()
            byte_obj.write(compress(dict_to_bytes(dfiles)))
            byte_obj.seek(0)
            os.remove(temp)
            return send_file(
                byte_obj, 
                as_attachment=True, 
                download_name="res.sd",
                )
        case "search":
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            dfiles_ = from_folder_search(d["folder"], user, password, d["pattern"], d["mode"])
            dfiles = dict()
            for full in list(dfiles_.keys()):
                start, end = full.rsplit("/",1)
                dval = from_folder_file(start+"/", user, password, end)
                dfiles[full] = dval
            dfiles = thumbnailify(dfiles, user)
            byte_obj = BytesIO()
            byte_obj.write(compress(dict_to_bytes(dfiles)))
            byte_obj.seek(0)
            return send_file(
                byte_obj, 
                as_attachment=True, 
                download_name="res.sd",
                )
        case "getbigfile":
            chunk = 1024**2//4
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            folder = d["dir"]
            chonker = d["partition"]
            file = d["file"]
            dfile = from_folder_file(folder, user, password, d["file"])
            dfiler = dfile[chunk*chonker:(chonker+1)*chunk] if len(dfile)>(chonker+1)*chunk else dfile[chunk*chonker:]
            dfiles = {"file": dfiler}
            if len(dfile)>(chonker+1)*chunk:
                dfiles["big"] = 1
            data = compress(dict_to_bytes(dfiles))

            byte_obj = BytesIO()
            byte_obj.write(data)
            byte_obj.seek(0)
            
            return send_file(
                byte_obj, 
                as_attachment=True, 
                download_name="res.sd",
                )
        case "getfile":
            d = bytes_to_dict(decompress(request.files.get("file").read()))
            folder = d["dir"]
            dfile = from_folder_file(folder, user, password, d["file"])
            dfiles = {"file": checktype(d["file"], dfile)}
            data = compress(dict_to_bytes(dfiles))

            chunk = 1024**2//4
            chonker = 0
            while 1:
                if len(dfile)>(chonker+1)*chunk:
                    dfiler = dfile[chunk*chonker:(chonker+1)*chunk]
                    chonker+=1
                else:
                    dfiler = dfile[chunk*chonker:]
                    break
            
            if len(dfile)>1024**2*4:
                dfiles = {"file": b"", "big": chonker}
                data = compress(dict_to_bytes(dfiles))
                byte_obj = BytesIO()
                byte_obj.write(data)
                byte_obj.seek(0)
            else:
                byte_obj = BytesIO()
                byte_obj.write(data)
                byte_obj.seek(0)
            #os.remove(temp)
            return send_file(
                byte_obj, 
                as_attachment=True, 
                download_name="res.sd",
                )
        case "getdirs":#returns a list of directories
            paths = [p.replace(f"/{user}/","~/",1) for p in get_dirs(user, password)]
            byte_obj = BytesIO()
            byte_obj.write(dict_to_bytes({"dirs":";".join(paths)}))
            byte_obj.seek(0)
            return send_file(
                byte_obj, 
                as_attachment=True, 
                download_name="res.sd",
                )
        
    return "End"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, threaded=True)
    #print(all_dirs(add_id(dict(), ["one","two","three","four.png"], 0),[],""))#
