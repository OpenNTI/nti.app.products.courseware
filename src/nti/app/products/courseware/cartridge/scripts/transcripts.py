from pprint import pprint

import sys

from bs4 import BeautifulSoup
from urlparse import urlparse


def patch_transcripts_for_video(video_file):
    fd = open(video_file, 'r')
    soup = BeautifulSoup(fd, 'html5lib')
    videos = soup.find_all('source')
    for video in videos:
        src = video.attrs['src']
        path = urlparse(src).path
        split = path.split('/')
        partner_id, entry_id = (None, None)
        for i, part in enumerate(split):
            if part == 'p':
                partner_id = split[i+1]
            if part == 'entryId':
                entry_id = split[i+1]
            if partner_id and entry_id:
                fd.close()
                return partner_id, entry_id


if __name__ == '__main__':
    results = {}
    for filename in sys.stdin:
        results[filename] = patch_transcripts_for_video(filename)
    partner_ids = dict()
    for result in results.values():
        for p_id in result[1]:
            pid = p_id[0]
            partner_ids(p_id[0])
    pprint(partner_ids)
    pprint(results)
