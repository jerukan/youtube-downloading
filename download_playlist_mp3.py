import sys
import os
import argparse
import traceback

import eyed3
from pytube import YouTube, Playlist
from ffmpy import FFmpeg
import pytube


"""
The YouTube streams do have audio streams that can be downloaded, which would be great if they didn't download
twice the length they're supposed to be. The other audio only formats don't work really well, so I'm stuck
here converting mp4s to mp3s. reeeee
"""


def force_remove(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def main():

    parser = argparse.ArgumentParser(description="Downloads a YouTube playlist as mp3 files to a specified directory.")
    parser.add_argument("playlist", type=str, help="YouTube link to a public playlist")
    parser.add_argument("outdir", type=str, help="Full path to download the mp3 files to")
    parser.add_argument("overwrite", type=bool, help="If true, overwrite existing mp3 files", nargs="?", const=True, default=True)

    args = parser.parse_args()

    pl = Playlist(args.playlist)
    outputDir = args.outdir

    vidqueue = list(pl.video_urls)

    while len(vidqueue) > 0:
        vidURL = vidqueue.pop(0)
        try:
            print(f"Preparing {vidURL} for download.")
            yt = YouTube(vidURL)
            print(f"{yt.title} from {vidURL} YouTube object successfully created.")
            strm = yt.streams.filter(only_audio=True).first()
            author = yt.author
            if author[-7:] == "- Topic":
                author = author[:-8]
            vidTitle = yt.title
            fileName = strm.default_filename
            dlPath = os.path.join(outputDir, fileName)

            outputNameSplit = fileName.split(".")
            outputNameSplit[len(outputNameSplit) - 1] = "mp3"
            outputName = ".".join(outputNameSplit)
            outputPath = os.path.join(outputDir, outputName)
            if os.path.exists(outputPath) and not args.overwrite:
                print(f"Audio file {outputName} already exists. Skipping video...")
                continue

            print("Downloading from stream...")
            strm.download(outputDir)
            print(f"{vidTitle} from {vidURL} successfully downloaded.")

            print(f"Converting file {fileName} to mp3")
            ff = FFmpeg(
                inputs={dlPath: "-y"},  # autmatically overwrite
                outputs={outputPath: "-vn"}  # remove video data
            )
            ff.run()
            print(f"File {outputName} successfully created.")
            os.remove(dlPath)
            print(f"File {fileName} removed.")

            audiofile = eyed3.load(outputPath)
            audiofile.tag.artist = author
            audiofile.tag.title = vidTitle
            audiofile.tag.save()
        except Exception as e:
            traceback.print_exc()
            print(f"Failed to download {vidURL}, will retry at the end...")
            vidqueue.append(vidURL)


if __name__ == "__main__":
    main()