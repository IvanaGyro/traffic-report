import subprocess
import re
import datetime
import time
import pytz
import os
from pathlib import Path

def get_create_time(filename):
    p = subprocess.Popen(
        ['exiftool', filename, '-CreateDate', '-Duration', '-n'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    out, err = p.communicate()
    if err:
        print(err)
        exit(1)

    m = re.search(r'Create Date[ ]*:[ ]*(\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2})', out)
    if m is None:
        raise Exception('create date not found')
        return None
    
    d = re.search(r'Duration[ ]*:[ ]*(\d+(\.\d+)?)', out)
    if d is None:
        raise Exception('duration not found')
        return None

    # convert UTC time to timestamp
    create_time = datetime.datetime.strptime(m.group(1), '%Y:%m:%d %H:%M:%S')
    create_time = create_time.replace(tzinfo=pytz.timezone('UTC'))
    create_time = create_time.astimezone()
    duration = float(d.group(1))
    create_time -= datetime.timedelta(seconds=duration)
    create_time = time.mktime(create_time.timetuple())
    return create_time

'''
preset:
    ultrafast
    superfast
    veryfast
    faster
    fast
    medium
    slow
    slower
    veryslow
    placebo
'''
def draw_timestamp(
    filename,
    output_filename,
    font_path,
    font_size='(w^2+h^2)^0.5/40',
    font_color='red',
    resoluion=None,
    preset='ultrafast',
):
    x = 'w-tw-20'
    y = 'h-lh-20'
    start_time = get_create_time(filename)
    scale = '' if resoluion is None else f"scale='iw*{resoluion}/min(iw,ih)':-1,"
    p = subprocess.Popen([
        'ffmpeg',
        '-i', filename,
        '-vf', f"{scale} drawtext=fontfile={font_path}: fontsize={font_size}: text='%{{pts\\:localtime\\:{start_time}}}': x={x}: y={y}: fontcolor={font_color}: box=0",
        '-c:v', 'libx264',
        '-preset', preset,
        output_filename,
    ])
    p.wait()


def compress(filename, output_filename, target_size):
    p = subprocess.Popen([
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'stream=bit_rate:format=duration',
        '-select_streams', 'a',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        filename,
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    if err:
        print(err)
        return
    audio_bit_rate, duration, *_ = out.split('\n')
    audio_bit_rate, duration = (float(e) for e in (audio_bit_rate, duration))

    target_video_bit_rate = (target_size - audio_bit_rate * duration) / duration
    tmp_filename = str(filename) + 'tmp.mp4'
    pass_log_prefix = str(filename) + 'pass'

    p = subprocess.Popen([
        'ffmpeg',
        '-y',
        '-i', str(filename),
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-b:v', str(target_video_bit_rate),
        '-pass', '1',
        '-passlogfile', pass_log_prefix,
        '-acodec', 'copy',
        '-f', 'mp4',
        tmp_filename,
    ])
    p.wait()

    p = subprocess.Popen([
        'ffmpeg',
        '-i', str(filename),
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-b:v', str(target_video_bit_rate),
        '-pass', '2',
        '-passlogfile', pass_log_prefix,
        '-acodec', 'copy',
        output_filename,
    ])
    p.wait()
    os.remove(tmp_filename)
    os.remove(f'{pass_log_prefix}-0.log')
    os.remove(f'{pass_log_prefix}-0.log.mbtree')


FONT_PATH = './TaipeiSansTCBeta-Regular.ttf'


if __name__ == '__main__':
    import argparse
    import shutil

    parser = argparse.ArgumentParser()
    parser.add_argument('file', nargs='+',
                        help='input file path')
    parser.add_argument('-r', '--resolution', type=int, nargs=1, default=1080,
                        help='e.g. 1080. Set to zero to keep the original resolution.')
    parser.add_argument('-s', '--size', type=int, nargs=1, default=28,
                        help='output file size in MB.')
    parser.add_argument('-u', '--save-uncompressed', action='store_true', default=False,
                        help='do not delete uncompressed videos')
    parser.add_argument('-d', '--draw-only', action='store_true', default=False,
                        help='draw timestamp without compressing')
    parser.add_argument('-o', '--output', default=Path(__file__).parent / 'out',
                        help='output directory')
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    if args.draw_only:
        args.save_uncompressed = True

    for file_path in args.file:
        if not file_path.endswith('.mp4') or not Path(file_path).is_file():
            continue
        filename = Path(file_path).name
        try:
            drawn_file = output / (filename + '.drawn.mp4')
            draw_timestamp(file_path, drawn_file, FONT_PATH, resoluion=args.resolution or None)
            if not args.draw_only:
                compress(drawn_file, output / filename, args.size * 8 * 1024 * 1024)
            if not args.save_uncompressed:
                os.remove(drawn_file)
        except Exception as e:
            print(file_path, 'Process failed.', e)
            continue
