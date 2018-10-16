#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getpass
import sys
import tempfile
import urllib2
import requests
import time


def _check_url(url):
    # Check valid url
    try:
        urllib2.urlopen(nti_url)
        print "Connection to %s successful!" % nti_url
        return True
    except Exception:
        print "URL %s is invalid" % nti_url
        return False


def _validate_credentials(username, password):
    dataserver2 = nti_url + '/dataserver2/users/' + username
    req = requests.get(dataserver2, auth=(username, password))
    if req.status_code != 200:
        print "Your credentials are invalid"
        return False
    print "Authentication successful!"
    return True


def _validate_course_entry(ntiid):
    course_href = nti_url + '/dataserver2/Objects/' + ntiid
    req = requests.get(course_href, auth=(nti_username, nti_password))
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
        # Legacy compat
        course_title = json.get('ContentPackageBundle', {}).get('DCTitle', None) or json.get('title')
        print "Access to course '%s' verified." % course_title
        return True
    else:
        print "Unable to access course (status code: %s)" % status_code
        exit(1)


def _validate_canvas_token(token, course_id):
    url = canvas_url + '/api/v1/courses/%s?access_token=%s' % (course_id, token)
    req = requests.get(url)
    if req.status_code == 200:
        print "Canvas access verified for course '%s'" % req.json()['name']
        return True
    print "Failed to verify access to course id '%s'" % course_id
    return False


def get_common_cartridge():
    # TODO update to our course cc export link
    link = "https://topkit.org/wp-content/uploads/2016/09/dev-topkit-sample-course-bauer-s-67-export.imscc"
    imscc = tempfile.NamedTemporaryFile()
    req = requests.get(link, stream=True)
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
    if upload.status_code != 200:
        print "An error occurred while uploading the course\n%s" % upload.text
        exit(1)
    print "Successfully uploaded course export!"
    print "Your import is now being processed by canvas. This can take some time. You can check on the status of " \
          "your import at %s/courses/%s/content_migrations" % (canvas_url, course_id)
    exit(0)


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
    course_id = raw_input("Input your canvas course id: ")
    if _validate_canvas_token(access_token, course_id):
        break

verify = raw_input("Are you sure you want to migrate '%s' to Canvas? (Y/N): " % course_title)
if verify != 'Y':
    exit(0)

print "Beginning course migration..."
print "Downloading course export..."
common_cartridge = get_common_cartridge()
print "Download complete."
print "Beginning canvas migration..."
do_content_migration()


