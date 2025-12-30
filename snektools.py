import zlib
from io import BytesIO
from PIL import Image, ImageTk, ImageFile, ExifTags
ImageFile.LOAD_TRUNCATED_IMAGES = True

def exif_rotate(b: bytes):
    image=Image.open(BytesIO(b))
    try:
        for orientation in ExifTags.TAGS.keys() : 
            if ExifTags.TAGS[orientation]=='Orientation' : break 
        exif=dict(image._getexif().items())
        x, y = image.size
        image = image.convert("RGBA")
        m = max([x,y])
        bg = Image.new("RGBA", (m,m))
        bg.paste(image, (0,0), image)
        image = bg.copy()
        if   exif[orientation] == 3 : 
            image=image.rotate(180, expand=True)
        elif exif[orientation] == 6 : 
            image=image.rotate(270, expand=True)
            image = image.crop(((m-y),0,m,x))
        elif exif[orientation] == 8 : 
            image=image.rotate(90, expand=True)
            image = image.crop(((m-y),0,m,x))
    except Exception:
        pass
    return image

def checkname(fname):
    prohibited = ["/"]
    if True in [pr in fname for pr in prohibited]:
        return False
    return True

def hashify(text:str):
    h=0
    for ch in text:
        h = ( h*281  ^ ord(ch)*997) & 0xFFFFFFFF
    return str(h)

def shorten(fname):
    if len(fname)>20:
        fname = fname[:8]+"..."+fname[-9:]
    return fname

def compress(b):
    return zlib.compress(b, 9)

def decompress(b):
    return zlib.decompress(b)

def read(fname):
    with open(fname) as f:
        whole = f.read()
    return whole

def test():
    testUrl = "http://127.0.0.1:5000/rpyth/autismaxin/action"
    testFiles = {
        "file": open("1702324489786880.gif", "rb")
        }

    responseVar = requests.post(testUrl, files = testFiles)
    if responseVar.ok:
        print("Successfully Uploaded all files !")
        print(responseVar.text)
    else:
        print("Upload failed !")

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

def bytes_to_pil(bytes_):
    bio = BytesIO(bytes_)
    bio.seek(0)
    return Image.open(bio)

def bytes_to_dict(b):
    bs = []
    focus = 0
    while focus<len(b):
        length = int.from_bytes(b[focus+1:focus+b[focus]+1], byteorder="big")
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
                content = int.from_bytes(value, byteorder = "big", signed = False)
            case "bytes":
                content = value
            case "dict":
                content = bytes_to_dict(value)
            case "PIL.Image.Image":
                content = bytes_to_pil(value)
            case _:
                if "PIL.JpegImagePlugin.JpegImageFile" in dtype:
                    content = bytes_to_pil(value)
                else:
                    content = "None"
        d[key] = content
    return d
