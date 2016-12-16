#!/usr/bin/python3
import argparse
import collections
import hashlib
import os
import shutil
import struct
import subprocess
import sys

import mutagen  # audio metadata module

parser = argparse.ArgumentParser(description=
	'Script for building the track and playlist database '
	'for the iPod shuffle 4g.')
parser.add_argument('mount_path', help='mount path of the iPod')
parser.add_argument('-vo', action='store_true', help='generate voice-overs for tracks and playlists')
parser.add_argument('-tts', choices=('svox', 'espeak'), help='generate voice-overs using specified tts provider')
args = parser.parse_args()

mount_path = args.mount_path

if not os.path.isdir(mount_path):
	sys.exit("Couldn't find mount path.")

if not os.access(mount_path, os.W_OK):
	sys.exit('No write permissions to mount path.')

os.chdir(mount_path)  # so that we don't have to alter all paths

for path in ('iTunes', 'Music', 'Speakable/Playlists', 'Speakable/Tracks'):
	if not os.path.exists('iPod_Control/' + path):
		os.makedirs('iPod_Control/' + path)

pjoin = os.path.join

def rmfiles(folder):
	for file in os.listdir(folder):
		file_path = pjoin(folder, file)
		if os.path.isfile(file_path):
			os.unlink(file_path)

# remove existing voice-over files
rmfiles('iPod_Control/Speakable/Playlists')
rmfiles('iPod_Control/Speakable/Tracks')

playlists = []
tracks = []

def get_audio_type(ext):
	ext = ext.lower()
	if ext in ('.mp3', '.mpg'):
		return 1
	elif ext in ('.m4a', '.m4b', '.m4p', '.aa'):
		return 2
	elif ext == '.wav':
		return 4
	else:
		return None

for (dirpath, dirnames, filenames) in os.walk('iPod_Control/Music'):
	for filename in filenames:
		base, ext = os.path.splitext(filename)
		filepath = pjoin(dirpath, filename)

		if get_audio_type(ext):
			tracks.append(filepath)
		elif ext.lower() == '.m3u':
			with open(filepath) as f:
				playlist = []

				for line in f.readlines():
					line = line.strip()

					if line and line[0] != '#':
						trackpath = pjoin(dirpath, line)
						
						if os.path.isfile(trackpath):
							playlist.append(trackpath)

				if playlist:
					print('found playlist', filepath)
					playlists.append((base, playlist))

if not tracks:
	sys.exit('No tracks found, copy your music to your iPod.')

tracks.sort()  # ensures that iTunesSD is the same for the same files
playlists.insert(0, (None, tracks))  # create master playlist

tts = collections.OrderedDict([
	('svox', ('pico2wave', '-w')),
	('espeak', ('espeak', '-w'))
])

enabled_tts = None

if args.tts:
	enabled_tts = args.tts
elif args.vo:
	for key, tupl in tts.items():
		if shutil.which(tupl[0]):
			print('using', key)
			enabled_tts = key
			break
	else:
		sys.exit('No text-to-speech provider found. Install either svox or espeak.')

# a voice-over is identified by its dbid
def get_dbid(text):
	return hashlib.md5(text.encode()).digest()[:8]

def create_voiceover(text, dbid, output_dir):
	name = ''.join(['{0:02X}'.format(x) for x in reversed(dbid)]) + '.wav'
	output_path = pjoin('iPod_Control/Speakable', output_dir, name)

	cmd = [*tts[enabled_tts], output_path, text]
	status = subprocess.call(cmd)
	if status:
		sys.exit('Command failed:', ' '.join(cmd))

def bjoin(*args):
	return b''.join(args)

header_len = 64
track_header_len = 20 + 4*len(tracks)
track_len = 372

db = b''

# header
db+= bjoin(
	b'bdhs',
	b'\x03\x00\x00\x02',
	struct.pack('<I', header_len),
	struct.pack('<I', len(tracks)),
	struct.pack('<I', len(playlists)),
	b'\x00'*8,
	b'\x00', # max_volume
	b'\x01', # always enable track_voiceover
	b'\x00'*2,
	struct.pack('<I', len(tracks)), # doesn't include podcasts or audiobooks
	struct.pack('<I', header_len), # track header offset
	struct.pack('<I', header_len + track_header_len + len(tracks)*track_len), # playlist header offset
	b'\x00'*20
)

# track header
db += bjoin(
	b'hths',
	struct.pack('<I', track_header_len),
	struct.pack('<I', len(tracks)),
	b'\x00'*8
)
for track_idx in range(len(tracks)):
	db += struct.pack('<I', header_len + track_header_len + track_len*track_idx)

albums, artists = [], []

# track body
for path in tracks:
	audio = mutagen.File(path, easy = True)

	title = audio.get('title', [''])[0]
	album = audio.get('album',['Unknown'])[0]
	artist = audio.get('artist',['Unknown'])[0]
	stop_pos = int(audio.info.length * 1000)

	text = title + ' - ' + artist
	dbid = get_dbid(text)

	if enabled_tts:
		create_voiceover(text, dbid, 'Tracks')

	filetype = get_audio_type(os.path.splitext(path)[1])

	if album in albums:
		album_id = albums.index(album)
	else:
		album_id = len(albums)
		albums.append(album)

	if artist in artists:
		artist_id = artists.index(artist)
	else:
		artist_id = len(artists)
		artists.append(artist)

	db += bjoin(
		b'rths',
		struct.pack('<I', 372), # total length
		struct.pack('<I', 0),  # start pos ms
		struct.pack('<I', stop_pos), # stop pos ms
		struct.pack('<I', 0), # volume gain
		struct.pack('<I', filetype),
		struct.pack('256s', ('/'+path).encode()),
		struct.pack('<I', 0), # bookmark
		b'\x01', # dont skip
		b'\x00', # remember playing pos
		b'\x00', # part_of_uninterruptable_album
		b'\x00',
		b'\x00\x02\x00\x00'*2,
		struct.pack('<I', 0),
		struct.pack('<I', 0),
		struct.pack('<I', 0),
		struct.pack('<I', 0),
		struct.pack('<I', album_id),
		b'\x01\x00', # track number
		b'\x00\x00', # disc number
		b'\x00' * 8,
		struct.pack('8s', dbid),
		struct.pack('<I', artist_id),
		b'\x00' * 32
	)

# playlist header
db += bjoin(
	b'hphs',
	struct.pack('<I', 20 + 4*len(playlists)),
	struct.pack('<I', len(playlists)), # number of playlists
	b'\xff\xff', # number of non podcast playlists
	b'\x01\x00', # number of master playlists
	b'\xff\xff', # number of non audiobook playlists
	b'\x00'*2
)

playlist_body = b''

db_len = len(db)

for name, pl_tracks in playlists:
	db += struct.pack('<I', db_len + 4*len(playlists) + len(playlist_body))  # add offset of current playlist

	if name is None:  # is master playlist
		pl_type = 1

		if enabled_tts:
			name = 'All songs'
			create_voiceover(name, dbid, 'Playlists')
		else:
			dbid = b'\x00'  # "All songs" built-in voice-over
	else:
		pl_type = 2
		dbid = get_dbid(name)
		if enabled_tts:
			create_voiceover(name, dbid, 'Playlists')
		

	playlist_body += bjoin(
		b'lphs',
		struct.pack('<I', 44 + 4*len(pl_tracks)), # total length
		struct.pack('<I', len(pl_tracks)), # number of tracks
		struct.pack('<I', len(pl_tracks)), # number of non podcast or audiobook songs
		struct.pack('8s', dbid),
		struct.pack('<I', pl_type),
		b'\x00' * 16
	)

	for track in pl_tracks:
		playlist_body += struct.pack('<I', tracks.index(track))

db += playlist_body

with open('iPod_Control/iTunes/iTunesSD', 'wb') as f:
	f.write(db)