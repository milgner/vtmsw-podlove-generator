#!/usr/bin/env python3

"""Watches a directory of MP3 files and renders a template from the list"""

import asyncio
import asyncore
import logging
import os
from base64 import b64encode
from types import SimpleNamespace
import eyed3
import pyinotify
from jinja2 import Environment, FileSystemLoader, select_autoescape

DIRECTORY = '.'
TEMPLATE_FILE = 'index.html.j2'
TARGET_FILE = './index.html'
POSTER_URL = 'https://vtmsw.illunis.net/poster.jpg'

logging.basicConfig(filename='update_player.log',
                    level=logging.DEBUG,
                    format='%(asctime)s %(message)s')

# used to load jinja2 templates
env = Environment(
    loader=FileSystemLoader(DIRECTORY),
    autoescape=select_autoescape(['html'])
)


def duration_from_seconds(seconds):
    """Converts a number of seconds to a time like format string."""
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    timelapsed = "{:d}:{:02d}:{:02d}".format(int(hours),
                                             int(minutes),
                                             int(seconds))
    return timelapsed


def data_uri_from_front_cover(tag):
    """Gets a URI from a cover image embedded in the file."""
    image_frame = tag.images.get('')
    if image_frame is None:
        return POSTER_URL
    base64 = str(b64encode(image_frame.image_data), 'utf-8')
    return f'data:{image_frame.mime_type};base64,{base64}'


def get_description_comment(tag):
    """Returns the first comment from the MP3."""
    if len(tag.comments) == 0:
        return None
    return tag.comments[0].text

def get_chapters(tag):
    """Currently not implemented"""
    # TODO once we have an Audacity label track and somehow got it into the file
    return []


def determine_publication_date(tag):
    """Returns the first matching date from the MP3"""
    return tag.release_date or tag.recording_date or tag.tagging_date


def get_episode_info(filename):
    """ Extracts the metadata so that it can be used to fill the template"""
    data = eyed3.load(filename)
    if data is None:
        return None
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
    """Updates the HTML with the current list of MP3s"""
    episodes = []
    sorted_file_list = sorted(os.listdir(DIRECTORY), reverse=True)
    for filename in sorted_file_list:
        if filename.endswith(".mp3") or filename.endswith(".mp4"):
            episode = get_episode_info(filename)
            if episode is not None:
                episodes.append(episode)

    template = env.get_template(TEMPLATE_FILE)
    html = template.render(episodes=episodes, poster_url=POSTER_URL)
    file = open(TARGET_FILE, 'w')
    file.write(html)
    file.close()


class EventProcessor(pyinotify.ProcessEvent):
    """Watches the directory and triggers a player update"""
    def process_event(self, event):
        """Invoked when any of the events below are detected"""
        logging.info("Received event %s for %s",
                     event.maskname, event.pathname)
        if not event.pathname.endswith('.mp3'):
            return

        update_player()

    process_IN_CLOSE_WRITE = \
    process_IN_MOVED_TO = \
    process_IN_MOVE_SELF = \
    process_IN_DELETE = \
    process_event


wm = pyinotify.WatchManager()
loop = asyncio.get_event_loop()
notifier = pyinotify.AsyncNotifier(wm, EventProcessor())
wm.add_watch(DIRECTORY, pyinotify.IN_CLOSE_WRITE |
             pyinotify.IN_MOVED_TO | pyinotify.IN_MOVE_SELF | pyinotify.IN_DELETE)

# update player once at startup to process any changes that happened while watcher wasn't running
update_player()

# Loop indefinetely
asyncore.loop()
notifier.stop()
