#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import subprocess
import zipfile

import requests
import ssl
import sys
import tempfile
import time
import urllib2

from argparse import ArgumentParser
import unicodecsv as csv
from bs4 import BeautifulSoup

# These map to the tab id in Canvas. We use the id to make
# an HTTP request for enabling/disabling the visibility to students
# The order in the tuple will be the order in canvas
DEFAULT_TABS = ('home',
                'announcements',
                'syllabus',
                'modules',
                'grades',
                'people')
DISABLE_TABS = ('discussions',
                'pages',
                'quizzes',
                'conferences',
                'collaborations',
                'files',
                'assignments',
                'outcomes')

course_id = '147346'
UA_STRING = 'NextThought Canvas Migrator Utility'


def _check_url(url):
    # Check valid url
    try:
        if '.dev' in url:
            # From Stack Overflow to disable certificate verfication
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            # add /app because base url is broken locally
            urllib2.urlopen(url+'/app/', context=ctx)
        else:
            urllib2.urlopen(url)
        print "Connection to %s successful!" % url
        return True
    except Exception:
        print "URL %s is invalid" % url
        return False


def _validate_credentials(username, password):
    dataserver2 = source + '/dataserver2/users/' + username
    req = requests.get(dataserver2, auth=(username, password), verify=False)
    if req.status_code != 200:
        print "Your credentials are invalid"
        return False
    print "Authentication successful!"
    return True


def _validate_course_entry(ntiid):
    global catalog_href
    catalog_href = source + '/dataserver2/Objects/' + ntiid
    req = requests.get(catalog_href, auth=(username, password), verify=False)
    status_code = req.status_code
    if status_code == 401 or status_code == 403:
        print "Your credentials are invalid to access this course"
        exit(1)
    elif status_code == 404:
        print "The catalog ntiid '%s' was unable to be found" % ntiid
        return False
    elif status_code == 200:
        global course_title
        json = req.json()
        course_title = json.get('DCTitle')
        global course_code
        course_code = json.get('ProviderDisplayName')
        global course_instructors
        course_instructors = [name['Name'] for name in json.get('Instructors', [])]
        global course_href
        course_href = source + '/dataserver2/Objects/%s' % json.get('CourseNTIID')
        if not verbose:
            enablePrint()
            print "Access to course '%s' verified." % course_title
            blockPrint()
        return True
    else:
        print "Unable to access course (status code: %s)" % status_code
        exit(1)


def _validate_canvas_token(token):
    url = dest + '/api/v1/courses?access_token=%s' % token
    req = requests.get(url)
    if req.status_code == 200:
        print "Canvas access verified"
        return True
    print "Failed to verify access to canvas API"
    return False


def get_iframes(video_file):
    fd = open(video_file, 'r')
    soup = BeautifulSoup(fd, 'html5lib')
    iframe = soup.find('iframe')
    fd.close()
    return [soup.find('title').text.encode('utf-8'), iframe.prettify('utf-8')]


def post_process_cartridge(imscc):
    directory = tempfile.mkdtemp()
    with zipfile.ZipFile(imscc, 'r') as zipref:
        zipref.extractall(directory)
    p = subprocess.Popen(['grep -l -r -e cdnapisec -e player.vimeo -e youtube.com/embed *'],
                         stdout=subprocess.PIPE,
                         shell=True,
                         cwd=directory)
    out, err = p.communicate()
    iframes = []
    for filename in out.split('\n')[:-1]:
        path = os.path.join(directory, filename)
        iframes.append(get_iframes(path))
    iframe_csv = tempfile.NamedTemporaryFile()
    iframe_csv.name = 'video_iframes.csv'
    writer = csv.writer(iframe_csv)
    writer.writerows(iframes)
    iframe_csv.flush()
    iframe_csv.seek(0)
    upload_file(iframe_csv.name, iframe_csv)
    imscc.seek(0)


def get_common_cartridge(url=None):
    link = url if url else course_href + '/@@common_cartridge'
    imscc = tempfile.NamedTemporaryFile()
    req = requests.get(link, stream=True, verify=False, auth=(username, password), timeout=10000.0)
    size = int(req.headers['Content-Length'])
    imported = 0
    increments = 1
    sys.stdout.write("[")
    sys.stdout.flush()
    for chunk in req.iter_content(chunk_size=1024):
        if chunk:
            imscc.write(chunk)
            imported += 1024
            if imported > (size/10)*increments:
                time.sleep(.5)
                sys.stdout.write(" * ")
                sys.stdout.flush()
                increments += 1
    sys.stdout.write(" * ]\n")
    sys.stdout.flush()
    imscc.seek(0) # important
    return imscc


def upload_file(filepath, filedescriptor=None):
    url = dest + '/api/v1/courses/%s/files' % course_id
    filename = os.path.basename(filepath)
    if filedescriptor is not None:
        filesize = len(filedescriptor.read())
        filedescriptor.seek(0)
    else:
        filesize = os.stat(filepath).st_size
    req = requests.post(url,
                        json={'name': filename,
                              'size': filesize,
                              'parent_folder_path': 'miscellaneous'},
                        headers={'Authorization': 'Bearer %s' % access_token})
    if req.status_code != 200:
        print 'An error occurred while creating the course through Canvas API\n%s' % req.text
        exit(1)
    upload_json = req.json()
    file_upload_url = upload_json['upload_url']
    print "Uploading %s to canvas..." % filename
    file_upload = open(filepath, 'r') if filedescriptor is None else filedescriptor
    upload = requests.post(file_upload_url,
                           data=upload_json['upload_params'],
                           files={'file': file_upload})
    try:
        file_upload.close()
    except OSError:
        pass
    get_url = upload.headers['Location']
    location = requests.get(get_url,
                            headers={'Authorization': 'Bearer %s' % access_token})
    return location.json()['id']


def create_home_page():
    html = open('home_page.html', 'r')
    soup = BeautifulSoup(html, features='html.parser')
    banner_id = upload_file('generic_banner.jpg')
    for banner_img in soup.find_all('img', {'class': 'banner_img'}):
        src = banner_img.attrs['src']
        banner_img.attrs['src'] = src % (course_id, banner_id)
        banner_img.replace_with(banner_img)
    modules_id = upload_file('icon_assess.png')
    for module_img in soup.find_all('img', {'class': 'module_img'}):
        src = module_img.attrs['src']
        module_img.attrs['src'] = src % (course_id, modules_id)
        module_img.replace_with(module_img)
    syllabus_id = upload_file('icon_syllabus.png')
    for syllabus_img in soup.find_all('img', {'class': 'syllabus_img'}):
        src = syllabus_img.attrs['src']
        syllabus_img.attrs['src'] = src % (course_id, syllabus_id)
        syllabus_img.replace_with(syllabus_img)
    for a in soup.find_all('a', {'class': ['modules_href', 'syllabus_href']}):
        href = a.attrs['href']
        a.attrs['href'] = href % course_id
        a.replace_with(a)
    soup.find(True, {'id': 'course_name'}).string = course_title
    tag = soup.find(True, {'id': 'professor_name'})
    for i, instructor in enumerate(course_instructors):
        tag.append(soup.new_string(instructor))
        if i != len(course_instructors) - 1:
            tag.append(soup.new_tag('br'))
    url = dest + '/api/v1/courses/%s/front_page' % course_id
    requests.put(url,
                 json={'wiki_page':
                           {'title': course_title,
                            'body': soup.prettify(),
                            'editing_roles': 'teachers'}},
                 headers={'Authorization': 'Bearer %s' % access_token})
    url = dest + '/api/v1/courses/%s' % course_id
    requests.put(url,
                 json={'course': {'default_view': 'wiki'}},
                 headers={'Authorization': 'Bearer %s' % access_token})


def create_canvas_course():
    link = dest + '/api/v1/accounts/2/courses'
    req = requests.post(link,
                        json={'course': {'name': course_title + ' QA',
                                         'course_code': course_code},
                              'enroll_me': True},
                        headers={'Authorization': 'Bearer %s' % access_token})
    if req.status_code != 200:
        print 'An error occurred while creating the course through Canvas API\n%s' % req.text
        exit(1)
    global course_id
    course_id = req.json()['id']


def update_course_settings():
    url = dest + '/api/v1/courses/%s/tabs/' % course_id
    for tab in DISABLE_TABS:
        requests.put(url + tab,
                     json={'hidden': True},
                     headers={'Authorization': 'Bearer %s' % access_token},
                     verify=False)
    for i, tab in enumerate(DEFAULT_TABS):
        requests.put(url + tab,
                     json={'hidden': False,
                           'position': i + 1,
                           'visibility': 'public'},
                     headers={'Authorization': 'Bearer %s' % access_token},
                     verify=False)


def do_content_migration():
    link = dest + '/api/v1/courses/%s/content_migrations' % course_id
    params = {'migration_type': 'common_cartridge_importer',
              'pre_attachment': {'name': 'nti_common_cartridge.imscc'}}
    # Tell canvas we want to do a migration to get a upload destination
    req = requests.post(link, json=params, headers={'Authorization': 'Bearer %s' % access_token})
    if req.status_code != 200:
        print "An error occurred while requesting this migration\n'%s'" % req.text
        exit(1)
    migration_json = req.json()
    progress_url = migration_json['progress_url']
    file_upload_url = migration_json['pre_attachment']['upload_url']
    print "Beginning upload to canvas at %s" % file_upload_url
    upload = requests.post(file_upload_url,
                           data=migration_json['pre_attachment']['upload_params'],
                           files={'file': common_cartridge})
    if upload.status_code != 200 and upload.status_code != 201:
        print "An error occurred while uploading the course\n%s" % upload.text
        exit(1)
    if not verbose:
        enablePrint()
        print "Successfully uploaded course export!"
        print "Your import is now being processed by canvas. This can take some time. You can check on the status of " \
              "your import at %s/courses/%s/content_migrations" % (dest, course_id)
        blockPrint()
    print "Beginning verification..."
    while(True):
        check = requests.get(progress_url, headers={'Authorization': 'Bearer %s' % access_token})
        if check.json()['workflow_state'] == 'completed':
            enablePrint()
            print "Import Success."
            url = '%s/api/v1/courses/%s/content_migrations/%s' % (dest, course_id, check.json()['context_id'])
            result = requests.get(url, headers={'Authorization': 'Bearer %s' % access_token})
            if result.json()['migration_issues_count'] > 0:
                issues = requests.get(result.json()['migration_issues_url'], headers={'Authorization': 'Bearer %s' % access_token})
                for issue in issues.json():
                    print '%s' % issue['description']
                    print '%s%s\n' % (dest, issue['fix_issue_html_url'])
            break
        if check.json()['workflow_state'] == 'failed':
            enablePrint()
            print "Import Failed"
            break
        print "Waiting on import to complete..."
        time.sleep(10)
    common_cartridge.close()


def _verify_node(json, modules, errors):
    if json['Class'] == 'CourseOutline':
        return
    elif json['Class'] == 'CourseOutlineNode':
        # Check for this in the modules
        module = next((d for d in modules if json['title'] in d.values()), None)
        if module is None:
            errors.append(json['title'] + ' is missing.')
        return module
    elif json['Class'] == 'LessonOverview':
        return



def verify_export():
    url = course_href + '/@@CourseSkeleton'
    course_skeleton = requests.get(url, auth=(username, password), verify=False)

    base_url = source + '/dataserver2/Objects/'
    errors = []
    modules_url = dest + '/api/v1/courses/%s/modules' % course_id
    modules = requests.get(modules_url, headers={'Authorization': 'Bearer %s' % access_token})
    modules_json = modules.json()
    def _recur_course(skeleton):
            for k, v in skeleton.items():
                node_url = base_url + k
                node = requests.get(node_url, auth=(username, password), verify=False)
                _verify_node(node.json(), modules_json, errors)
                for obj in v:
                    if isinstance(obj, dict):
                        _recur_course(obj)
                    else:
                        for ntiid in skeleton:
                            node_url = base_url + ntiid
                            node = requests.get(node_url, auth=(username, password), verify=False)
                            _verify_node(node.json(), modules_json, errors)
    _recur_course(course_skeleton.json())


# Disable
def blockPrint():
    sys.stdout = open(os.devnull, 'w')

# Restore
def enablePrint():
    sys.stdout = sys.__stdout__


def _parse_args():
    arg_parser = ArgumentParser(description=UA_STRING)
    arg_parser.add_argument('-n', '--ntiid', dest='ntiid',
                            help="Catalog Entry NTIID of the course to copy.")
    arg_parser.add_argument('-s', '--source-server', dest='source',
                            help="Source server (https://janux.ou.edu, etc).")
    arg_parser.add_argument('-d', '--dest-server', dest='dest',
                            help="Destination server (https://canvas.ou.edu, etc).")
    arg_parser.add_argument('-u', '--username', dest='username',
                            help="User to authenticate with the server.")
    arg_parser.add_argument('-p', '--password', dest='password',
                            help="User to authenticate password")
    arg_parser.add_argument('-k' '--key', dest='access_token',
                            help="Canvas Developer Key.")
    arg_parser.add_argument('-v', '--verbose', dest='verbose',
                            help='Additional information as script runs',
                            default=False)

    return arg_parser.parse_args()


def migrate(ntiid,
            username,
            password,
            source,
            dest,
            access_token,
            verbose):
    if not verbose:
        blockPrint()
    print "Checking urls..."
    _check_url(source)
    _check_url(dest)
    print "Validating credentials..."
    _validate_credentials(username, password)
    print "Validating catalog ntiid..."
    _validate_course_entry(ntiid)
    print "Validating canvas token..."
    _validate_canvas_token(access_token)
    print "Beginning course migration..."
    print "Downloading course export..."
    create_canvas_course()

    global common_cartridge
    common_cartridge = get_common_cartridge()
    post_process_cartridge(common_cartridge)
    print "Download complete."
    print "Beginning canvas migration..."
    print "Creating canvas course via API..."
    print "Creating Home Page..."
    create_home_page()
    print "Updating course settings..."
    update_course_settings()
    print "Migrating content..."
    do_content_migration()
    # verify_export()
    print "Migration Complete"
    exit(0)
    

def main():
    args = _parse_args()
    globals().update(args.__dict__)
    migrate(**args.__dict__)


if __name__ == '__main__':
    main()
