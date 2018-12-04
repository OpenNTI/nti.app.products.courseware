#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getpass
import os
import requests
import ssl
import sys
import tempfile
import time
import urllib2

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
    dataserver2 = nti_url + '/dataserver2/users/' + username
    req = requests.get(dataserver2, auth=(username, password), verify=False)
    if req.status_code != 200:
        print "Your credentials are invalid"
        return False
    print "Authentication successful!"
    return True


def _validate_course_entry(ntiid):
    global catalog_href
    catalog_href = nti_url + '/dataserver2/Objects/' + ntiid
    req = requests.get(catalog_href, auth=(nti_username, nti_password), verify=False)
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
        from IPython.terminal.debugger import set_trace;set_trace()

        course_title = json.get('DCTitle')
        global course_instructors
        course_instructors = [name['Name'] for name in json.get('Instructors')]
        global course_href
        course_href = nti_url + '/dataserver2/Objects/%s' % json.get('CourseNTIID')
        print "Access to course '%s' verified." % course_title
        return True
    else:
        print "Unable to access course (status code: %s)" % status_code
        exit(1)


def _validate_canvas_token(token):
    url = canvas_url + '/api/v1/courses?access_token=%s' % token
    req = requests.get(url)
    if req.status_code == 200:
        print "Canvas access verified"
        return True
    print "Failed to verify access to canvas API"
    return False


def get_common_cartridge(url=None):
    link = url if url else course_href + '/@@common_cartridge'
    imscc = tempfile.NamedTemporaryFile()
    req = requests.get(link, stream=True, verify=False, auth=(nti_username, nti_password))
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


def upload_file(filepath):
    url = canvas_url + '/api/v1/courses/%s/files' % course_id
    filename = os.path.basename(filepath)
    filesize = os.stat(filepath).st_size
    req = requests.post(url,
                        json={'name': filename,
                              'size': filesize},
                        headers={'Authorization': 'Bearer %s' % access_token})
    if req.status_code != 200:
        print 'An error occurred while creating the course through Canvas API\n%s' % req.text
        exit(1)
    upload_json = req.json()
    file_upload_url = upload_json['upload_url']
    print "Uploading %s to canvas..." % filename
    file_upload = open(filepath, 'r')
    upload = requests.post(file_upload_url,
                           data=upload_json['upload_params'],
                           files={'file': file_upload})
    file_upload.close()
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
    url = canvas_url + '/api/v1/courses/%s/front_page' % course_id
    requests.put(url,
                 json={'wiki_page':
                           {'title': course_title,
                            'body': soup.prettify(),
                            'editing_roles': 'teachers'}},
                 headers={'Authorization': 'Bearer %s' % access_token})
    url = canvas_url + '/api/v1/courses/%s' % course_id
    requests.put(url,
                 json={'course': {'default_view': 'wiki'}},
                 headers={'Authorization': 'Bearer %s' % access_token})


def create_canvas_course():
    link = canvas_url + '/api/v1/accounts/2/courses'
    req = requests.post(link,
                        json={'course': {'name': course_title}, 'enroll_me': True},
                        headers={'Authorization': 'Bearer %s' % access_token})
    if req.status_code != 200:
        print 'An error occurred while creating the course through Canvas API\n%s' % req.text
        exit(1)
    global course_id
    course_id = req.json()['id']


def update_course_settings():
    url = canvas_url + '/api/v1/courses/%s/tabs/' % course_id
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
    link = canvas_url + '/api/v1/courses/%s/content_migrations' % course_id
    params = {'migration_type': 'common_cartridge_importer',
              'pre_attachment': {'name': 'nti_common_cartridge.imscc'}}
    # Tell canvas we want to do a migration to get a upload destination
    req = requests.post(link, json=params, headers={'Authorization': 'Bearer %s' % access_token})
    if req.status_code != 200:
        print "An error occurred while requesting this migration\n'%s'" % req.text
        exit(1)
    migration_json = req.json()
    file_upload_url = migration_json['pre_attachment']['upload_url']
    print "Beginning upload to canvas at %s" % file_upload_url
    upload = requests.post(file_upload_url,
                           data=migration_json['pre_attachment']['upload_params'],
                           files={'file': common_cartridge})
    if upload.status_code != 200 and upload.status_code != 201:
        print "An error occurred while uploading the course\n%s" % upload.text
        exit(1)
    print "Successfully uploaded course export!"
    print "Your import is now being processed by canvas. This can take some time. You can check on the status of " \
          "your import at %s/courses/%s/content_migrations" % (canvas_url, course_id)
    common_cartridge.close()

# Get the NTI url
while(True):
    nti_url = raw_input("Input a NextThought URL (https://janux.ou.edu, etc): ")
    if _check_url(nti_url):
        break

# Get the Canvas url
while(True):
    canvas_url = raw_input("Input a Canvas URL (https://canvas.ou.edu, etc): ")
    if _check_url(canvas_url):
        break

# Get NTI Credentials
while(True):
    nti_username = raw_input("Input your NextThought username: ")
    nti_password = getpass.getpass("Input your NextThought password: ")
    if _validate_credentials(nti_username, nti_password):
        break

# Get the Catalog Entry NTIID
while(True):
    catalog_ntiid = raw_input("Input a course catalog entry ntiid: ")
    if _validate_course_entry(catalog_ntiid):
        break

# Get the canvas access token
while(True):
    access_token = raw_input("Input your canvas access token: ")
    if _validate_canvas_token(access_token):
        break

verify = raw_input("Are you sure you want to migrate '%s' to Canvas? (Y/N): " % course_title)
if verify != 'Y':
    exit(0)

print "Beginning course migration..."
print "Downloading course export..."
common_cartridge = get_common_cartridge()
print "Download complete."
print "Beginning canvas migration..."
print "Creating canvas course via API..."
create_canvas_course()
print "Migrating content..."
do_content_migration()
print "Creating Home Page..."
create_home_page()
print "Updating course settings..."
update_course_settings()
print "Migration Complete"
exit(0)
