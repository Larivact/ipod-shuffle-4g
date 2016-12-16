# iPod Shuffle 4g DB generator

The iPod shuffle 4g requires a database to find tracks and playlists,
this simple script generates said database based on the music files stored in `iPod_Control/Music`.
It can also handle M3U playlists and create voice-over tracks.

This script is a rewrite of [nims11/IPod-Shuffle-4g](https://github.com/nims11/IPod-Shuffle-4g).
It requires Python 3 and the [Mutagen](https://mutagen.readthedocs.io/en/latest/) package.
To generate voice-overs sVox or espeak is required.

Usage:

1. Connect and mount your iPod.
2. Copy your music into the Music directory of your iPod.
3. Run the script, pass the mount path and `-vo` if you want to generate voice-overs.

```
usage: ipod_shuffle_4g.py [-h] [-vo] [-tts {svox,espeak}] mount_path

positional arguments:
  mount_path          mount path of the iPod

optional arguments:
  -h, --help          show this help message and exit
  -vo                 generate voice-overs for tracks and playlists
  -tts {svox,espeak}  generate voice-overs using specified tts provider
```

Issues and pull requests are welcome, the project is licensed under the GPLv2.