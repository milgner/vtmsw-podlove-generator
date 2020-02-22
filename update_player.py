#!/usr/bin/env python3

import pyinotify
import asyncio
import asyncore
import os
import eyed3
from jinja2 import Environment, FileSystemLoader, select_autoescape
from types import SimpleNamespace
from base64 import b64encode

directory = '.'
template_file = 'index.html.j2'
target_file = './index.html'
poster_url = 'https://vtmsw.illunis.net/poster.jpg'

# used to load jinja2 templates
env = Environment(
    loader=FileSystemLoader(directory),
    autoescape=select_autoescape(['html'])
)

def duration_from_seconds(s):
    """Module to get the convert Seconds to a time like format."""
    s = s
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    timelapsed = "{:d}:{:02d}:{:02d}".format(int(h),
                                                      int(m),
                                                      int(s))
    return timelapsed


def data_uri_from_front_cover(tag):
  image_frame = tag.images.get('')
  if image_frame is None:
    return poster_url
  base64 = str(b64encode(image_frame.image_data), 'utf-8')
  return f'data:{image_frame.mime_type};base64,{base64}'

def get_description_comment(tag):
  if len(tag.comments) == 0:
    return None
  return tag.comments[0].text

# TODO once we have an Audacity label track and somehow got it into the file
def get_chapters(tag):
  return []

def determine_publication_date(tag):
  return tag.release_date or tag.recording_date or tag.tagging_date

# read id3 tags
def get_episode_info(filename):
  data = eyed3.load(filename)
  episode_info = {
    'filename': filename,
    'title': data.tag.title,
    'summary': get_description_comment(data.tag),
    'duration': duration_from_seconds(data.info.time_secs),
    'publication_date': determine_publication_date(data.tag),
    'filesize': data.info.size_bytes,
    'poster_url': data_uri_from_front_cover(data.tag),
    'chapters': get_chapters(data.tag)
  }
  return SimpleNamespace(**episode_info)


def update_player():
  episodes = []
  sorted_file_list = sorted(os.listdir(directory), reverse=True)
  for filename in sorted_file_list:
    if filename.endswith(".mp3") or filename.endswith(".mp4"):
      episodes.append(get_episode_info(filename))

  template = env.get_template(template_file)
  html = template.render(episodes=episodes, poster_url=poster_url)
  file = open(target_file, 'w')
  file.write(html)
  file.close()

class EventProcessor(pyinotify.ProcessEvent):
  def process_event(self, event):
    if not event.pathname.endswith('.mp3'):
      return

    update_player()

  process_IN_CLOSE_WRITE = process_IN_MOVED_TO = process_IN_MOVE_SELF = process_IN_DELETE = process_event

wm = pyinotify.WatchManager()
loop = asyncio.get_event_loop()
notifier = pyinotify.AsyncNotifier(wm, EventProcessor())
wm.add_watch(directory, pyinotify.IN_CLOSE_WRITE | pyinotify.IN_MOVED_TO | pyinotify.IN_MOVE_SELF | pyinotify.IN_DELETE)

# update player once at startup to process any changes that happened while watcher wasn't running
update_player()

# Loop indefinetely
asyncore.loop()
notifier.stop()

