# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os
import tempfile

import requests

import shutil

from argparse import ArgumentParser

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


UA_STRING = 'NextThought Bulk Export Utility'


def _parse_args():
    arg_parser = ArgumentParser(description=UA_STRING)
    arg_parser.add_argument('-u', '--username', dest='username',
                            help="User to authenticate with the server.")
    arg_parser.add_argument('-p', '--password', dest='password',
                            help="User to authenticate password")
    arg_parser.add_argument('-s', '--source', dest='source',
                            help="Url to server")
    arg_parser.add_argument('-d', '--destination', dest='destination',
                            help='Destination directory')
    return arg_parser.parse_args()


def _export_to_queue(url, username, password, filepath):
    if os.path.exists(filepath):
        return
    try:
        export_resp = requests.get(url, verify=False, auth=(username, password), stream=True, timeout=10000.0)
        if export_resp.status_code != 200:
            return
        export = tempfile.NamedTemporaryFile()
        for chunk in export_resp.iter_content(chunk_size=1024):
            if chunk:
                export.write(chunk)
        export.seek(0)
    except:
        return
    try:
        with open(filepath + '.zip', 'w') as fp:
            shutil.copyfileobj(export, fp)
    except:
        return

def _export(url,
            username,
            password,
            course_ntiid,
            course_title,
            course_last_modified,
            destination):
    course_url = '%s/dataserver2/Objects/%s/@@Export' % (url, course_ntiid)
    filepath = os.path.join(destination, '%s_%s' % (course_title, course_last_modified))
    _export_to_queue(course_url, username, password, filepath)


def main():
    args = _parse_args()

    all_courses_url = '%s/dataserver2/users/%s/Courses/AllCourses' % (args.source,
                                                                      args.username)
    all_courses = requests.get(all_courses_url,
                               verify=False,
                               auth=(args.username, args.password))
    json_courses = all_courses.json()['Items']
    for json_course in json_courses:
        course_ntiid = json_course.get('CourseNTIID')
        course_title = json_course.get('title')
        course_last_modified = str(int(json_course.get('Last Modified')))
        if None in (course_ntiid, course_last_modified, course_title):
            continue
        _export(args.source,
                args.username,
                args.password,
                course_ntiid,
                course_title,
                course_last_modified,
                args.destination)

    exit()


if __name__ == '__main__':
    main()
