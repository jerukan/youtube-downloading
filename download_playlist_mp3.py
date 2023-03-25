import argparse
from io import BytesIO
from pathlib import Path
import threading
import traceback
import requests

import eyed3
from PIL import Image
from pytube import YouTube, Playlist
import ffmpeg


"""
Script to download a YouTube playlist as mp3 files.
"""


def convert_to_mp3(inpath, outpath, artist=None, title=None, tnpath=None):
    """Convert mp4 to mp3 with ffmpeg"""
    instream = ffmpeg.input(str(inpath), y=None)
    outstream = ffmpeg.output(instream, str(outpath), vn=None)
    ffmpeg.run(outstream)
    print(f"{outpath} created.")
    inpath.unlink()
    print(f"{inpath} removed.")

    # add mp3 metadata
    audiofile = eyed3.load(outpath)
    audiofile.tag.artist = artist
    audiofile.tag.title = title
    if tnpath is not None:
        with open(tnpath, "rb") as tfile:
            thumbnail_data = tfile.read()
        audiofile.tag.images.set(3, thumbnail_data, "image/jpeg", u"cover")
        tnpath.unlink()
        print(f"{tnpath} removed.")
    audiofile.tag.save()


def download_and_convert(url, outdir, overwrite):
    # download from youtube
    yt = YouTube(url)
    title = yt.title
    author = yt.author
    # check if video from youtube music
    from_ytmusic = False
    if author[-7:] == "- Topic":
        author = author[:-8]
        from_ytmusic = True
    # slashes screw with filepaths
    author = author.replace("/", "")

    print(f"Preparing {title} from {url}")
    # YouTube audio streams have some issues where they download as twice the intended
    # length, so we have to use ffmpeg to convert them to an mp3 in order to resolve
    # those issues.
    strm = yt.streams.filter(only_audio=True).first()
    # very important to use since we need valid filenames
    filename = strm.default_filename
    dlpath = outdir / filename
    mp3_name = f"{dlpath.stem} - {author}.mp3"
    mp3_path = outdir / mp3_name
    if mp3_path.exists() and not overwrite:
        print(f"Audio file {mp3_path} already exists. Skipping...")
        return
    # grab thumbnail
    thumbnail_path = outdir / f"{dlpath.stem}.jpeg"
    response = requests.get(yt.thumbnail_url)
    img = Image.open(BytesIO(response.content))
    # thumbnails are 640 x 480
    if from_ytmusic:
        img = img.crop((140, 60, 140 + 360, 60 + 360))
    else:
        img = img.crop((0, 60, 640, 60 + 360))
    img.thumbnail((300, 300))
    img.save(thumbnail_path, "JPEG")
    # download audio mp4
    print("Downloading from stream...")
    strm.download(outdir)
    print(f"{dlpath} successfully downloaded.")

    # convert to mp3 with ffmpeg
    thdfunc = lambda: convert_to_mp3(dlpath, mp3_path, artist=author, title=title, tnpath=thumbnail_path)
    thd = threading.Thread(target=thdfunc)
    thd.start()


def main():
    parser = argparse.ArgumentParser(description="Downloads a YouTube playlist as mp3 files to a specified directory.")
    parser.add_argument("playlist", type=str, help="YouTube link to a public/unlisted playlist")
    parser.add_argument("--overwrite", action=argparse.BooleanOptionalAction)

    args = parser.parse_args()
    overwrite = args.overwrite
    if overwrite is None:
        overwrite = False

    pl = Playlist(args.playlist)
    pltitle = pl.title
    outdir = Path("downloads", pltitle)
    outdir.mkdir(exist_ok=True)

    vidqueue = list(pl.video_urls)

    while len(vidqueue) > 0:
        url = vidqueue.pop(0)
        try:
            download_and_convert(url, outdir, overwrite)
        except Exception as e:
            traceback.print_exc()
            print(f"Failed to download {url}, will retry at the end...")
            vidqueue.append(url)


if __name__ == "__main__":
    main()
