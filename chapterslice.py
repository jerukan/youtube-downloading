"""
Format of description file

-------- Start of file --------
album name
artist name

chapter 1
chapter 2
...
chapter x
--------- End of file ---------
"""
import re
import sys
import os

import eyed3
import ffmpeg


def parse_timestamp(timestamp):
    time_split = timestamp.split(":")
    seconds = 0
    if len(time_split) == 3:
        seconds += int(time_split[0]) * 3600
        seconds += int(time_split[1]) * 60
        seconds += int(time_split[2])
    else:
        seconds += int(time_split[0]) * 60
        seconds += int(time_split[1])
    return seconds


# CONFIGURE THESE #
TIME_FIRST = False
CONTAINS_TRACK_NUMBER = True
TIME_SEPARATION_REGEX = r"\s+\-\s+"
###################

TIME_REGEX = r"((?:\d+:)?\d+:\d\d)"


def reorder_info(info):
    if TIME_FIRST:
        if CONTAINS_TRACK_NUMBER:
            return (info[1], info[2], info[0])
        else:
            return (None, info[1], info[0])
    else:
        if CONTAINS_TRACK_NUMBER:
            return info
        else:
            return (None, info[0], info[1])


if CONTAINS_TRACK_NUMBER:
    TITLE_REGEX = r"[^\s\d]*(\d+)\S*\s+(.+)"
else:
    TITLE_REGEX = r"(.+)"
if not TIME_FIRST:
    TITLE_REGEX = TITLE_REGEX + f"(?={TIME_SEPARATION_REGEX})"
if TIME_FIRST:
    info_regex = f"{TIME_REGEX}{TIME_SEPARATION_REGEX}{TITLE_REGEX}"
else:
    info_regex = f"{TITLE_REGEX}{TIME_SEPARATION_REGEX}{TIME_REGEX}"
print(info_regex)

# default order below
# gets (track number, song title, timestamp start)
# info_regex = r"[^\s\d]*(\d+)\S*\s+(.+)(?=\s+\-\s+)\s+\-\s+(\d+:\d\d)"
mp3_path = sys.argv[1]
title = os.path.splitext(mp3_path)[0]
description_path = title + ".description"

# parse description file
with open(description_path, "r") as d_file:
    lines = d_file.readlines()
album_name = lines[0].strip()
if not os.path.isdir(album_name):
    os.mkdir(album_name)
artist_name = lines[1].strip()
trackcounter = 1

re_tracks = re.findall(info_regex, "".join(lines))
re_tracks = [reorder_info(track) for track in re_tracks]
print(re_tracks)
for i, track_info in enumerate(re_tracks):
    trackcounter = int(track_info[0]) if track_info[0] is not None else None
    song_name = track_info[1]
    timestamp = track_info[2]

    start = parse_timestamp(timestamp)
    mp3_stream = ffmpeg.input(mp3_path, ss=start)
    if trackcounter is None:
        filename = f"{album_name} - {song_name}.mp3"
    else:
        filename = f"{album_name} - {trackcounter} - {song_name}.mp3"
    save_name = os.path.join(album_name, filename)
    if i < len(re_tracks) - 1:
        end = parse_timestamp(re_tracks[i + 1][2])
        mp3_stream = ffmpeg.output(mp3_stream, save_name, write_xing=0, t=end-start)
    else:
        mp3_stream = ffmpeg.output(mp3_stream, save_name, write_xing=0)
    ffmpeg.run(mp3_stream)

    audiofile = eyed3.load(save_name)
    audiofile.tag.artist = artist_name
    audiofile.tag.album = album_name
    audiofile.tag.title = song_name
    if trackcounter is not None:
        audiofile.tag.track_num = str(trackcounter)

    audiofile.tag.save()
