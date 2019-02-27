# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os
import shutil
from multiprocessing import Process, Queue
from multiprocessing.pool import ThreadPool

import requests
from argparse import ArgumentParser

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


def _export_to_queue(queue, url, username, password):
    common_cartridge = get_common_cartridge(url=url, username=username, password=password)
    if common_cartridge is not None:
        queue.put(common_cartridge)


def _export(url,
            username,
            password,
            course_ntiid,
            course_title,
            course_last_modified,
            destination):
    course_url = '%s/dataserver2/Objects/%s/@@common_cartridge' % (url, course_ntiid)
    q = Queue()
    p = Process(target=_export_to_queue, args=(q, course_url, username, password))
    p.start()
    p.join()
    fd = q.get()
    filepath = os.path.join(destination, '%s_%s' % (course_title, course_last_modified))
    with open(filepath, 'w') as fp:
        shutil.copyfileobj(fd, fp)


def main():
    args = _parse_args()

    tp = ThreadPool(None)  # Defaults to the number of CPU cores
    all_courses_url = '%s/dataserver2/users/%s/Courses/AllCourses' % (args.source,
                                                                      args.username)
    all_courses = requests.get(all_courses_url,
                               verify=False,
                               auth=(args.username, args.password))
    json_courses = all_courses.json()['Items']
    for json_course in json_courses:
        course_ntiid = json_course.get('CourseNTIID')
        course_title = json_course.get('title')
        course_last_modified = json_course.get('Last Modified')
        if None in (course_ntiid, course_last_modified, course_title):
            continue
        tp.apply_async(_export, (args.source,
                                 args.username,
                                 args.password,
                                 course_ntiid,
                                 course_title,
                                 course_last_modified,
                                 args.destination))

    tp.close()
    tp.join()
    exit()

if __name__ == '__main__':
    main()
