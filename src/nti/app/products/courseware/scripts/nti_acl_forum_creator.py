#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import sys
import argparse

from zope import component
from zope import interface

from zope.pluggableauth.interfaces import IPrincipal

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_PURCHASED
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseInstancePublicScopedForum
from nti.contenttypes.courses.interfaces import ICourseInstanceForCreditScopedForum
from nti.contenttypes.courses.interfaces import ICourseInstancePurchasedScopedForum

from nti.contenttypes.courses.utils import get_course_instructors

from nti.dataserver.contenttypes.forums.ace import ForumACE
from nti.dataserver.contenttypes.forums.forum import ACLCommunityForum
from nti.dataserver.contenttypes.forums.interfaces import IACLCommunityForum

from nti.dataserver.contenttypes.forums.interfaces import PERMISSIONS
from nti.dataserver.contenttypes.forums.interfaces import READ_PERMISSION
from nti.dataserver.contenttypes.forums.interfaces import WRITE_PERMISSION

from nti.dataserver.users.entity import Entity

from nti.dataserver.utils import run_with_dataserver
from nti.dataserver.utils.base_script import set_site
from nti.dataserver.utils.base_script import create_context

from nti.ntiids.ntiids import make_specific_safe
from nti.ntiids.ntiids import find_object_with_ntiid

logger = __import__('logging').getLogger(__name__)


def _get_instructors(instance):
    result = set(IPrincipal(x, None) for x in get_course_instructors(instance))
    result.discard(None)
    return result


def _get_acl(instance, permissions, ntiids):
    instructors = _get_instructors(instance)

    # Our instance instructors get all permissions.
    acl = [
        ForumACE(Permissions=("All",),
                 Entities=[i for i in instructors],
                 Action='Allow'),
        ForumACE(Permissions=permissions,
                 Entities=list(ntiids),
                 Action='Allow')
    ]

    # SubInstance instructors get the same permissions as their students.
    if not ICourseSubInstance.providedBy(instance):
        for subinstance in instance.SubInstances.values():
            instructors = _get_instructors(subinstance)
            acl.append(ForumACE(Permissions=permissions,
                                Entities=[i.id for i in instructors],
                                Action='Allow'))
    return acl


def _assign_iface(obj, iface=None):
    if iface is not None and not iface.providedBy(obj):
        interface.alsoProvides(obj, iface)
        logger.info("Added interface to object %s %s", iface, obj)


def _assign_acl(obj, acl, iface=None):
    if iface is not None and not iface.providedBy(obj):
        interface.alsoProvides(obj, iface)
        logger.info("Added interface to object %s %s", iface, obj)

    if not hasattr(obj, 'ACL') or obj.ACL != acl:
        obj.ACL = acl
        logger.info("Set ACL on object %s to %s", obj, acl)


def _creator(course, scope, name, title, permissions, site=None):
    set_site(site)

    context = find_object_with_ntiid(course)
    instance = ICourseInstance(context, None)
    if instance is None:
        catalog = component.getUtility(ICourseCatalog)
        try:
            context = catalog.getCatalogEntry(course)
            instance = ICourseInstance(context, None)
        except KeyError:
            pass
    if instance is None:
        raise ValueError("Course cannot be found")

    # decode title
    title = title.decode('utf-8', 'ignore')

    # Always created by the public community
    # (because legacy courses might have a DFL
    # for the non-public)
    creator = instance.SharingScopes['Public'].NTIID
    creator = Entity.get_entity(creator)

    # get fourm interface
    if scope == ES_PUBLIC:
        forum_interface = ICourseInstancePublicScopedForum
    elif scope == ES_PURCHASED:
        forum_interface = ICourseInstancePurchasedScopedForum
    else:
        forum_interface = ICourseInstanceForCreditScopedForum

    discussions = instance.Discussions

    ntiid = instance.SharingScopes[scope].NTIID
    acl = _get_acl(instance, permissions, (ntiid,))

    name = make_specific_safe(name)
    try:
        forum = discussions[name]
        logger.info("Found existing forum %s", name)
        _assign_iface(forum, forum_interface)
        _assign_acl(forum, acl, IACLCommunityForum)
        if forum.creator is not creator:
            forum.creator = creator
    except KeyError:
        forum = ACLCommunityForum()
        forum.title = title
        forum.creator = creator
        _assign_iface(forum, forum_interface)
        _assign_acl(forum, acl, IACLCommunityForum)

        discussions[name] = forum
        logger.debug('Created forum %s', forum)
    return forum.NTIID


def main():
    arg_parser = argparse.ArgumentParser(description="ACL forum creator")
    arg_parser.add_argument('-v', '--verbose', help="Be verbose", action='store_true',
                                                    dest='verbose')
    arg_parser.add_argument('-c', '--course',
                            dest='course',
                            help="Course entry identifier/ntiid")
    arg_parser.add_argument('-n', '--name',
                            dest='name',
                            help="Forum name")
    arg_parser.add_argument('-t', '--title',
                            dest='title',
                            help="Forum title")
    arg_parser.add_argument('-s', '--scope',
                            dest='scope',
                            help="Scope")
    arg_parser.add_argument('-p', '--permissions',
                            dest='permissions',
                            nargs="+",
                            default=(READ_PERMISSION, WRITE_PERMISSION),
                            help="The permissions")
    arg_parser.add_argument('--site',
                            dest='site',
                            help="Application SITE.")
    args = arg_parser.parse_args()

    env_dir = os.getenv('DATASERVER_DIR')
    if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
        raise IOError("Invalid dataserver environment root directory")

    site = args.site
    course = args.course
    if not course:
        raise ValueError("Please specify a course/catalog entry identifier")

    scope = args.scope
    if not scope:
        raise ValueError("Please specify a scope")
    if scope not in ENROLLMENT_SCOPE_VOCABULARY.by_token.keys():
        raise ValueError("Please specify a valid scope")

    name = args.name
    if not name:
        raise ValueError("Please specify a fourum name")
    title = args.title or name

    permissions = args.permissions or ()
    permissions = [x.capitalize() for x in permissions if x]
    for perm in permissions:
        if perm not in PERMISSIONS:
            raise ValueError("%s is an invalid permission" % perm)
    if not permissions:
        raise ValueError("Please specify forum permissions")

    conf_packages = ('nti.appserver',)
    context = create_context(env_dir, with_library=True)

    run_with_dataserver(environment_dir=env_dir,
                        xmlconfig_packages=conf_packages,
                        verbose=args.verbose,
                        context=context,
                        function=lambda: _creator(site=site,
                                                  course=course,
                                                  name=name,
                                                  title=title,
                                                  scope=scope,
                                                  permissions=permissions))
    sys.exit(0)


if __name__ == '__main__':
    main()
