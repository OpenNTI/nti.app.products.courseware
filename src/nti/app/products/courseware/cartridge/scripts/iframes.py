#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import csv
import os
import shutil
import subprocess
import tempfile
import zipfile
from multiprocessing import Process

import requests
import time
from argparse import ArgumentParser
from bs4 import BeautifulSoup

from nti.app.products.courseware.cartridge.scripts.canvas import get_iframes

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

access_token = '8808~s6T7Mrd73LABgnKZJIK7uotak0oReoRHP0z5AbyUmyl5bOqTmZF6ogNzPSm8ubJO'

WORKING_DIRECTORY = '/Users/sheldon.smith/Documents/iframe_fix'


def get_course(course_url):
    course_id = course_url.rsplit('/', 1)[-1]
    res = requests.get('https://canvas.ou.edu/api/v1/courses/%s' % course_id,
                       headers={'Authorization': 'Bearer %s' % access_token})
    course_title = res.json()['name']
    course_code = res.json()['course_code']
    url = 'https://canvas.ou.edu/api/v1/courses/%s/content_exports' % course_id
    res = requests.post(url,
                        headers={'Authorization': 'Bearer %s' % access_token},
                        json={'export_type': 'common_cartridge'})
    wait_for_completion(res.json()['progress_url'])
    filename, path = download_export(course_id, res.json()['id'])
    path = unzip_path(path, filename)
    patch_iframes(path)
    course_id = create_canvas_course(course_title, course_code)
    do_content_migration(course_id, path)


def do_content_migration(course_id, common_cartridge_path):
    common_cartridge = shutil.make_archive(common_cartridge_path, 'zip', common_cartridge_path)
    common_cartridge = open(common_cartridge, 'r')
    link ='https://canvas.ou.edu/api/v1/courses/%s/content_migrations' % course_id
    params = {'migration_type': 'common_cartridge_importer',
              'pre_attachment': {'name': 'nti_common_cartridge.imscc'}}
    # Tell canvas we want to do a migration to get a upload destination
    req = requests.post(link, json=params, headers={'Authorization': 'Bearer %s' % access_token})
    migration_json = req.json()
    progress_url = migration_json['progress_url']
    file_upload_url = migration_json['pre_attachment']['upload_url']
    upload = requests.post(file_upload_url,
                           data=migration_json['pre_attachment']['upload_params'],
                           files={'file': common_cartridge})
    while(True):
        check = requests.get(progress_url, headers={'Authorization': 'Bearer %s' % access_token})
        if check.json()['workflow_state'] == 'completed':
            url = 'https://canvas.ou.edu/api/v1/courses/%s/content_migrations/%s' % (course_id, check.json()['context_id'])
            result = requests.get(url, headers={'Authorization': 'Bearer %s' % access_token})
            break
        time.sleep(10)
    common_cartridge.close()


def create_canvas_course(course_title, course_code):
    link = 'https://canvas.ou.edu/api/v1/accounts/2/courses'
    req = requests.post(link,
                        json={'course': {'name': course_title + ' New Iframes',
                                         'course_code': course_code},
                              'enroll_me': True},
                        headers={'Authorization': 'Bearer %s' % access_token})
    course_id = req.json()['id']
    return course_id


FULLSCREEN_PARAMS = {'allow': "autoplay *; fullscreen* ; encrypted-media *",
                     'allowfullscreen': "allowfullscreen",
                     'mozallowfullscreen': "mozallowfullscreen",
                     'webkitallowfullscreen': "webkitallowfullscreen"}


def patch_iframes(path):
    wiki = os.path.join(path, 'wiki_content')
    for subdir, dirs, files in os.walk(wiki):
        for wikipage in files:
            path_to = os.path.join(wiki, subdir, wikipage)
            with open(path_to, 'r') as wp:
                soup = BeautifulSoup(wp, features='html5lib')
                iframes = soup.find_all('iframe')
                for iframe in iframes:
                    iframe.attrs.update(FULLSCREEN_PARAMS)
            with open(path_to, 'w') as wp:
                wp.write(soup.prettify('utf-8'))


def unzip_path(path, filename):
    extract_to = os.path.join(WORKING_DIRECTORY, filename)
    os.makedirs(extract_to)
    with zipfile.ZipFile(path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    os.remove(path)
    return extract_to


def wait_for_completion(progress_url):
    res = requests.get(progress_url,
                       headers={'Authorization': 'Bearer %s' % access_token})
    while res.json()['workflow_state'] != 'completed':
        res = requests.get(progress_url,
                           headers={'Authorization': 'Bearer %s' % access_token})
        time.sleep(5)


def download_export(course_id, export_id):
    url = 'https://canvas.ou.edu/api/v1/courses/%s/content_exports/%s' % (course_id, export_id)
    res = requests.get(url,
                       headers={'Authorization': 'Bearer %s' % access_token})

    download_url = res.json()['attachment']['url']

    req = requests.get(download_url, stream=True,
                       headers={'Authorization': 'Bearer %s' % access_token})
    local_filename = res.json()['attachment']['filename']
    # Convert imscc to zip
    base = os.path.splitext(local_filename)[0]
    local_filename = base + '.zip'
    path = os.path.join(WORKING_DIRECTORY, local_filename)

    iframe_fix = open(path, 'w')
    for chunk in req.iter_content(chunk_size=1024):
        iframe_fix.write(chunk)
    iframe_fix.close()
    return base, path


def _parse_args():
    arg_parser = ArgumentParser()
    arg_parser.add_argument('-f', '--file', dest='filename',
                            help='CSV file')


    return arg_parser.parse_args()

def main():
    args = _parse_args()
    FNULL = open(os.devnull, 'w')
    processes = []
    with open(args.filename, 'rb') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            p = Process(target=get_course, args=(row[0],))
            p.start()
            processes.append(p)
    for i, p in enumerate(processes):
        p.join()
        print("Process %s of %s completed" % (i, len(processes)))
    FNULL.close()


def post_process_cartridge(path):
    p = subprocess.Popen(['grep -l -r -e cdnapisec -e player.vimeo -e youtube.com/embed *'],
                         stdout=subprocess.PIPE,
                         shell=True,
                         cwd=path)
    out, err = p.communicate()
    iframes = []
    for filename in out.split('\n')[:-1]:
        if 'kaltura' in filename:
            continue
        tmp_path = os.path.join(path, filename)
        iframes.append(get_iframes(tmp_path))
    name = os.path.basename(os.path.normpath(path))
    with open(os.path.join(WORKING_DIRECTORY, 'iframes', name + '.csv'), 'w') as iframe_csv:
        writer = csv.writer(iframe_csv)
        writer.writerows(iframes)


def get_csv():
    for subdir in os.listdir(WORKING_DIRECTORY):
        if subdir == 'iframes':
            continue
        path = os.path.join(WORKING_DIRECTORY, subdir)
        if os.path.isdir(path):
            post_process_cartridge(path)

if __name__ == '__main__':
    get_csv()



