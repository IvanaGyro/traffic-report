import io
import os
import traceback
from inspect import currentframe
from pathlib import Path
from pprint import pprint

import piexif
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
from PIL import ExifTags


def debug_print(*args):
    frameinfo = currentframe()
    print(frameinfo.f_back.f_lineno,':')
    for arg in args:
        if isinstance(arg, Exception):
            traceback.print_tb(arg.__traceback__)
        else:
            pprint(arg)
    print()


def flip_horizontal(im):
    return im.transpose(Image.FLIP_LEFT_RIGHT)


def flip_vertical(im):
    return im.transpose(Image.FLIP_TOP_BOTTOM)


def rotate_180(im):
    return im.transpose(Image.ROTATE_180)


def rotate_90(im):
    return im.transpose(Image.ROTATE_90)


def rotate_270(im):
    return im.transpose(Image.ROTATE_270)


def transpose(im):
    return rotate_90(flip_horizontal(im))


def transverse(im):
    return rotate_90(flip_vertical(im))

orientation_funcs = [
    None,
    lambda x: x,
    flip_horizontal,
    rotate_180,
    flip_vertical,
    transpose,
    rotate_270,
    transverse,
    rotate_90,
]


class Photo:
    def __init__(self, filename):
        self.filename = filename
        self.img = Image.open(filename)
        self.exif = piexif.load(filename)
        self._datetime_original = ''

    def update_thumbnail(self):
        if 'thumbnail' in self.exif:
            try:
                thumbnail = Image.open(io.BytesIO(self.exif['thumbnail']))
                thumbnail_size = thumbnail.size
                thumbnail = self.img.copy()
                thumbnail.thumbnail(thumbnail_size, Image.LANCZOS)
                thumbnail_bytes = io.BytesIO()
                thumbnail.save(thumbnail_bytes, format=self.img.format)
                self.exif['thumbnail'] = thumbnail_bytes.getvalue()
                self.img.info['exif'] = piexif.dump(self.exif)
            except Exception as e:
                debug_print(self.filename, e)
                # raise e # ignore error
    
    @property
    def datetime_original(self):
        if self._datetime_original:
            return self._datetime_original
        exif = self.exif
        datetime = exif['Exif'][piexif.ExifIFD.DateTimeOriginal]
        datetime = datetime.decode()
        datetime_parts = datetime.split()
        try:
            datetime = f'{datetime_parts[0].replace(":", "-")} {datetime_parts[1]}'
        except KeyError as e:
            debug_print(filename, datetime)
            raise e
        self._datetime_original = datetime
        return datetime

    def save(self, dest):
        self.update_thumbnail()
        self.img.save(dest, exif=self.img.info['exif'])

            

def fix_rotation(photo: Photo):
    img = photo.img
    exif = photo.exif
    if img.format == 'JPEG':
        zeroth_ifd = exif.get('0th', {})
        orientation = zeroth_ifd.get(piexif.ImageIFD.Orientation, 1)
        if orientation != 1:
            img = orientation_funcs[orientation](img)
            zeroth_ifd[piexif.ImageIFD.Orientation] = 1
            exif.get('1st', {})[piexif.ImageIFD.Orientation] = 1

            # fix https://github.com/hMatoba/Piexif/issues/95
            if piexif.ExifIFD.SceneType in exif.get('Exif', {}):
                scene_type = exif['Exif'][piexif.ExifIFD.SceneType]
                if not isinstance(scene_type, bytes):
                    exif['Exif'][piexif.ExifIFD.SceneType] = bytes([scene_type])

            try:
                img.info['exif'] = piexif.dump(exif)
                img.format = 'JPEG'
                photo.img = img
            except Exception as e:
                debug_print(photo.filename, e, exif)
                raise e


def draw_datetime(photo: Photo):
    img = photo.img
    draw = ImageDraw.Draw(img)
    # font = ImageFont.truetype(<font-file>, <font-size>)
    w, h = img.size
    font_size = int((w**2 + h**2)**0.5 // 40)
    font = ImageFont.truetype('TaipeiSansTCBeta-Bold.ttf', font_size)
    # draw.text((x, y),"Sample Text",(r,g,b))
    draw.text((w - int(font_size * 10), h - int(font_size * 1.2)),
              photo.datetime_original, (255, 0, 0),
              font=font)


if __name__ == '__main__':
    import argparse
    import glob

    parser = argparse.ArgumentParser()
    parser.add_argument('file', nargs='+',
                        help='input file path')
    parser.add_argument('-s', '--single-directory', action='store_true',
                        help='do not classify with the car plates')
    parser.add_argument('-o', '--output', default=Path(__file__).parent / 'out',
                        help='output directory')
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    photos = []

    for filename in args.file:
        if not filename.endswith('.jpg') or not Path(filename).is_file():
            continue
        photo = Photo(filename)
        try:
            fix_rotation(photo)
            draw_datetime(photo)
            photo.filename = output / Path(filename).name
            photo.save(photo.filename)
            photos.append(photo)
        except Exception as e:
            debug_print(filename, 'Process failed.', e)
            continue
    
    if not args.single_directory:
        import shutil
        from collections import defaultdict
        
        import plate
        
        plate.init_alpr()
        cars = defaultdict(list)
        for photo in photos:
            car_plate = plate.recognize(str(photo.filename))
            if not car_plate: continue
            cars[car_plate].append(photo)
        plate.unload_alpr()

        for car_plate, car_photos in cars.items():
            time_str = min(p.datetime_original for p in car_photos)
            time_str = time_str.replace('-', '')
            time_str = time_str.replace(':', '')
            time_str = time_str.replace(' ', '-')[2:]
            dest = output / f'{time_str}_{car_plate}'
            dest.mkdir(parents=True, exist_ok=True)
            for car_photo in car_photos:
                shutil.move(car_photo.filename, dest / car_photo.filename.name)
        
        
