import argparse
from pathlib import Path
import traceback

import eyed3
from pytube import YouTube, Playlist
import ffmpeg


"""
Script to download a YouTube playlist as mp3 files.
"""


def main():
    parser = argparse.ArgumentParser(description="Downloads a YouTube playlist as mp3 files to a specified directory.")
    parser.add_argument("playlist", type=str, help="YouTube link to a public/unlisted playlist")
    parser.add_argument("overwrite", type=bool, help="If true, overwrite existing mp3 files", nargs="?", const=True, default=True)

    args = parser.parse_args()

    pl = Playlist(args.playlist)
    pltitle = pl.title
    outdir = Path("downloads", pltitle)

    vidqueue = list(pl.video_urls)

    while len(vidqueue) > 0:
        url = vidqueue.pop(0)
        try:
            # download from youtube
            yt = YouTube(url)
            print(f"Preparing {yt.title} from {url}")
            # YouTube audio streams have some issues where they download as twice the intended
            # length, so we have to use ffmpeg to convert them to an mp3 in order to resolve
            # those issues.
            strm = yt.streams.filter(only_audio=True).first()
            author = yt.author
            if author[-7:] == "- Topic":
                author = author[:-8]
            title = yt.title
            filename = strm.default_filename
            dlpath = outdir / filename
            print("Downloading from stream...")
            strm.download(outdir)
            print(f"{dlpath} successfully downloaded.")

            # convert to mp3 with ffmpeg
            mp3_name_split = filename.split(".")
            mp3_name_split[-1] = "mp3"
            mp3_name = ".".join(mp3_name_split)
            mp3_path = outdir / mp3_name
            if mp3_path.exists() and not args.overwrite:
                print(f"Audio file {mp3_path} already exists. Skipping video...")
                continue
            print(f"Converting file {dlpath} to mp3")
            instream = ffmpeg.input(str(dlpath), y=None)
            outstream = ffmpeg.output(instream, str(mp3_path), vn=None)
            ffmpeg.run(outstream)
            print(f"{mp3_path} created.")
            dlpath.unlink()
            print(f"{dlpath} removed.")

            # add mp3 metadata
            audiofile = eyed3.load(mp3_path)
            audiofile.tag.artist = author
            audiofile.tag.title = title
            audiofile.tag.save()
        except Exception as e:
            traceback.print_exc()
            print(f"Failed to download {url}, will retry at the end...")
            vidqueue.append(url)


if __name__ == "__main__":
    main()
