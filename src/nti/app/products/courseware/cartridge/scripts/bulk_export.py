# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os

import requests

import shutil

from argparse import ArgumentParser

from multiprocessing import Process

from multiprocessing.pool import ThreadPool

from nti.app.products.courseware.cartridge.scripts.canvas import get_common_cartridge

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


UA_STRING = 'NextThought Bulk Common Cartridge Export Utility'


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
    filepath += '.zip'
    if os.path.exists(filepath):
        return
    try:
        common_cartridge = get_common_cartridge(url=url, username=username, password=password)
    except:
        return
    if common_cartridge is None:
        return
    try:
        with open(filepath + '.zip', 'w') as fp:
            shutil.copyfileobj(common_cartridge, fp)
    except:
        return

def _export(url,
            username,
            password,
            course_ntiid,
            course_title,
            course_last_modified,
            destination):
    course_url = '%s/dataserver2/Objects/%s/@@common_cartridge' % (url, course_ntiid)
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
