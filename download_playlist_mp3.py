import argparse
import concurrent.futures
from json import loads
from io import BytesIO
from pathlib import Path
import threading
import traceback
import requests

import eyed3
import ffmpeg
from PIL import Image
import pytube
from pytube import YouTube, Playlist


"""
Script to download a YouTube playlist as mp3 files.

Usage: python download_playlist_mp3.py <url>
"""


def get_description(video: YouTube) -> str:
    """
    yt.description is None, it literally doesn't work right now. Workaround for now.

    https://stackoverflow.com/questions/77481385/pytube-library-getting-error-in-video-description
    """
    i: int = video.watch_html.find('"shortDescription":"')
    desc: str = '"'
    i += 20  # excluding the `"shortDescription":"`
    while True:
        letter = video.watch_html[i]
        desc += letter  # letter can be added in any case
        i += 1
        if letter == '\\':
            desc += video.watch_html[i]
            i += 1
        elif letter == '"':
            break
    return loads(desc)


def convert_to_mp3(inpath, outpath, artist=None, title=None, album=None, tnpath=None):
    """Convert mp4 to mp3 with ffmpeg"""
    outpath_unfixed = outpath.parent / f"{outpath.stem}_unfixed{outpath.suffix}"
    instream = ffmpeg.input(str(inpath), y=None)
    outstream = ffmpeg.output(instream, str(outpath_unfixed), vn=None)
    ffmpeg.run(outstream)
    # something about the apple music player makes these songs double the length
    # if they aren't re-encoded, so we have to rerun ffmpeg on the mp3.
    fixinstream = ffmpeg.input(str(outpath_unfixed), y=None)
    fixoutstream = ffmpeg.output(fixinstream, str(outpath), acodec="copy")
    ffmpeg.run(fixoutstream)
    print(f"{outpath} created.")
    inpath.unlink()
    outpath_unfixed.unlink()
    print(f"{inpath} and {outpath_unfixed} removed.")

    # add mp3 metadata
    audiofile = eyed3.load(outpath)
    audiofile.tag.artist = artist
    audiofile.tag.title = title
    audiofile.tag.album = album
    if tnpath is not None:
        with open(tnpath, "rb") as tfile:
            thumbnail_data = tfile.read()
        audiofile.tag.images.set(3, thumbnail_data, "image/jpeg", u"cover")
        tnpath.unlink()
        print(f"{tnpath} removed.")
    audiofile.tag.save()


def download_and_convert(url, outdir, overwrite):
    succeeded = False
    while not succeeded:
        try:
            # download from youtube
            yt = YouTube(url)
            vidid = yt.video_id
            title = yt.title
            author = yt.author
            album = None
            # check if video from youtube music
            from_ytmusic = yt._vid_info is not None and yt._vid_info["videoDetails"]["musicVideoType"] == "MUSIC_VIDEO_TYPE_ATV"
            if from_ytmusic:
                # author = author[:-8]
                from_ytmusic = True
                # desc = yt.description
                desc = get_description(yt)
                descsplit = list(filter(lambda x: x.strip(), desc.splitlines()))
                # getting metadata for the album isn't working anymore, so we have to
                # infer from the description
                # I think auto generated descriptions have the album on the 3rd line
                album = descsplit[2]
            # slashes screw with filepaths
            author = author.replace("/", "")

            print(f"Preparing {title} from {url} [author: {author}, from_ytmusic: {from_ytmusic}]")
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
            # thumbnails from yt music don't need to be cropped anymore
            # if from_ytmusic:
            #     img = img.crop((140, 60, 140 + 360, 60 + 360))
            # else:
            #     img = img.crop((0, 60, 640, 60 + 360))
            img.thumbnail((300, 300))
            img.save(thumbnail_path, "JPEG")
            # download audio mp4
            print("Downloading from stream...")
            strm.download(outdir)
            print(f"{dlpath} successfully downloaded.")

            # convert to mp3 with ffmpeg
            convert_to_mp3(dlpath, mp3_path, artist=author, title=title, album=album, tnpath=thumbnail_path)
            succeeded = True
        except Exception:
            traceback.print_exc()
            print(f"Failed to download {url}, will retry...")


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

    # vidqueue = list(pl.video_urls)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(download_and_convert, url, outdir, overwrite): url for url in pl.video_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                future.result()
            except Exception:
                traceback.print_exc()
            else:
                print(f"Finished processing of {url}")


if __name__ == "__main__":
    # pytube.innertube._default_clients["ANDROID"] = pytube.innertube._default_clients["WEB"]
    main()
