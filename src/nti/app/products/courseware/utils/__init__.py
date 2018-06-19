#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import six
import hashlib
import mimetypes

from datetime import datetime
from collections import Mapping
from six.moves.urllib_parse import urlparse

from requests.structures import CaseInsensitiveDict

import repoze.lru

from pyramid.threadlocal import get_current_request

from zope import component
from zope import lifecycleevent

from zope.component.hooks import getSite

from zope.interface.interfaces import IMethod

from zope.intid.interfaces import IIntIds

from zope.traversing.api import traverse

from zope.traversing.interfaces import IEtcNamespace

from nti.app.assessment.common.evaluations import get_evaluation_courses

from nti.app.products.courseware.enrollment import EnrollmentOptions

from nti.app.products.courseware.interfaces import IEnrollmentOptionProvider

from nti.app.products.courseware.invitations.interfaces import ICourseInvitations

from nti.app.products.courseware.invitations.model import CourseInvitation

from nti.app.products.courseware.utils.decorators import PreviewCourseAccessPredicateDecorator

from nti.assessment.interfaces import IQAssignment

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.common.string import is_true

from nti.contentfile.interfaces import IContentBaseFile

from nti.contentlibrary.interfaces import IContentPackage

from nti.contenttypes.courses import get_course_vendor_info

from nti.contenttypes.courses.interfaces import SCOPE
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import DESCRIPTION
from nti.contenttypes.courses.interfaces import NTI_COURSE_FILE_SCHEME

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_hierarchy
from nti.contenttypes.courses.utils import get_courses_for_packages

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

from nti.dataserver.interfaces import IMemcacheClient

from nti.invitations.interfaces import IDisabledInvitation

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

#: Default memcache expiration time
DEFAULT_EXP_TIME = 86400

#: 1970-01-1
ZERO_DATETIME = datetime.utcfromtimestamp(0)

#: Course meta-info file name.
COURSE_META_NAME = u'meta_info.json'

#: Course meta-info export-hash key.
EXPORT_HASH_KEY  = u'ExportHash'

# BWC exports
PreviewCourseAccessPredicate = PreviewCourseAccessPredicateDecorator

logger = __import__('logging').getLogger(__name__)


def last_synchronized(context=None):
    if context is None:
        context = component.queryUtility(IEtcNamespace, name='hostsites')
    result = getattr(context, 'lastSynchronized', None) or 0
    return result


def memcache_client():
    return component.queryUtility(IMemcacheClient)


def memcache_get(key, client=None):
    if client is None:
        client = component.queryUtility(IMemcacheClient)
    if client is not None:
        try:
            return client.get(key)
        except Exception:
            pass
    return None


def memcache_set(key, value, client=None, exp=DEFAULT_EXP_TIME):
    if client is None:
        client = component.queryUtility(IMemcacheClient)
    if client is not None:
        try:
            client.set(key, value, time=exp)
            return True
        except Exception:
            pass
    return False


@repoze.lru.lru_cache(200)
def encode_keys(*keys):
    result = hashlib.md5()
    for key in keys:
        result.update(str(key).lower())
    return result.hexdigest()


def get_vendor_info(context):
    info = get_course_vendor_info(context, False)
    return info or {}


def get_enrollment_options(context):
    result = EnrollmentOptions()
    entry = ICourseCatalogEntry(context)
    for provider in list(component.subscribers((entry,),
                                               IEnrollmentOptionProvider)):
        for option in provider.iter_options():
            result.append(option)
    return result


def get_enrollment_communities(context):
    vendor_info = get_vendor_info(context)
    result = traverse(vendor_info, 'NTI/Enrollment/Communities', default=False)
    if result and isinstance(result, six.string_types):
        result = result.split()
    return result or ()


def get_enrollment_courses(context):
    vendor_info = get_vendor_info(context)
    result = traverse(vendor_info, 'NTI/Enrollment/Courses', default=False)
    if result and isinstance(result, six.string_types):
        result = result.split()
    return result or ()


def get_enrollment_scopes(context):
    vendor_info = get_vendor_info(context)
    return traverse(vendor_info, 'NTI/Enrollment/Scopes', default=False)


def get_enrollment_for_scope(context, scope):
    scopes = get_enrollment_scopes(context)
    if isinstance(scopes, Mapping):
        result = scopes.get(scope)
        if result and isinstance(result, six.string_types):
            result = result.split()
        return result or ()
    return ()


def get_course_and_parent(context):
    """
    Fetch the course and parent (if available), returning the course first
    in the resulting sequence.
    """
    course = ICourseInstance(context, None)
    parent = get_parent_course(context)
    if parent is not None and parent != course:
        result = (course, parent)
    else:
        result = (course,)
    return result


def get_vendor_thank_you_page(course, key):
    for course in get_course_and_parent(course):
        vendor_info = get_vendor_info(course)
        tracking = traverse(vendor_info,
                           'NTI/VendorThankYouPage',
                           default=False)
        if tracking and key in tracking:
            return tracking.get(key)
    return None


def _get_vendor_invitations(context):
    entry = ICourseCatalogEntry(context, None)
    if entry is None:
        return ()
    for course in get_course_and_parent(context):
        result = None
        vendor_info = get_vendor_info(course)
        invitations = traverse(vendor_info,
                               'NTI/Invitations',
                               default=False)
        # simple string code
        if isinstance(invitations, six.string_types):
            invitations = invitations.split()
        if isinstance(invitations, (list, tuple)):
            result = []
            for value in invitations:
                # simple string code
                if isinstance(value, six.string_types):
                    invitation = CourseInvitation(Code=value,
                                                 Scope=ES_PUBLIC,
                                                 Course=entry.ntiid,
                                                 Description=ES_PUBLIC)
                    result.append(invitation)
                # fully modeled invitation
                elif isinstance(value, Mapping):
                    value = CaseInsensitiveDict(value)
                    code = value.get('Code')
                    scope = value.get(SCOPE) or ES_PUBLIC
                    desc = value.get(DESCRIPTION) or scope
                    isGeneric = is_true(value.get('IsGeneric'))
                    if code:
                        invitation = CourseInvitation(Code=code,
                                                     Scope=scope,
                                                     Description=desc,
                                                     Course=entry.ntiid,
                                                     IsGeneric=isGeneric)
                        result.append(invitation)
        if result:
            return result
    return ()


def get_course_invitations(context):
    """
    Fetch the invitations found in the course or parent, in that order.
    If an invitation is disable, it will not return here.
    """
    result = []
    # Fetch persistent invitations
    # XXX: Do we need to handle parent/section too?
    course = ICourseInstance(context, None)
    if course is not None:
        course_invitations = ICourseInvitations(course)
        course_invitations = course_invitations.get_course_invitations()
        if course_invitations:
            result.extend(course_invitations)
    # Now the vendor invitations
    vendor_invitations = _get_vendor_invitations(context)
    if vendor_invitations:
        result.extend(vendor_invitations)
    return [x for x in result if not IDisabledInvitation.providedBy(x)]


def get_course_invitation(context, code):
    for invitation in get_course_invitations(context):
        if invitation.Code == code:
            return invitation
    return None


def has_course_invitations(context):
    result = get_course_invitations(context)
    return bool(result)


def _get_course_ntiids(courses):
    # Get any courses that match our outline; since the ref may have been
    # indexed or stored from any course.
    results = set()
    for course in courses or ():
        hierarchy = get_course_hierarchy(course)
        root_outline = course.Outline
        # outlines.add( root_outline )
        for child_course in hierarchy or ():
            if child_course.Outline == root_outline:
                entry = ICourseCatalogEntry(child_course, None)
                if entry is not None:
                    results.add(entry.ntiid)
    return results


def _get_ref_target_ntiids(evaluation):
    result = []
    if IQAssignment.providedBy(evaluation):
        # Some refs actually point to assignment qset ntiids.
        for part in evaluation.parts or ():
            if part.question_set is not None:
                result.append(part.question_set.ntiid)
    result.append(evaluation.ntiid)
    return result


def get_evaluation_lessons(evaluation, outline_provided, courses=None, request=None):
    """
    For the given evaluation, get all lessons containing the evaluation.

    `outline_provided` is the outline ref type pointing to the given evaluation.
    """
    request = get_current_request() if request is None else request
    if courses is None:
        # XXX: If we have a request course, we use it.
        # Do we want all courses?
        course = ICourseInstance(request, None)
        courses = (course,)
        if course is None:
            courses = get_evaluation_courses(evaluation)
    target_ntiids = _get_ref_target_ntiids(evaluation)
    container_ntiids = _get_course_ntiids(courses)
    catalog = get_library_catalog()
    if not isinstance(outline_provided, (list, tuple)):
        outline_provided = (outline_provided,)
    sites = get_component_hierarchy_names()
    objs = catalog.search_objects(sites=sites,
                                  target=target_ntiids,
                                  provided=outline_provided,
                                  container_ntiids=container_ntiids,
                                  container_all_of=False)
    lessons = []
    for ref in objs:
        lesson = find_interface(ref, INTILessonOverview, strict=False)
        if lesson is not None:
            lessons.append(lesson)
    return lessons


def associate(obj, filer, key, bucket=None):
    intids = component.getUtility(IIntIds)
    if intids.queryId(obj) is None:
        return
    source = filer.get(key=key, bucket=bucket)
    if IContentBaseFile.providedBy(source):
        source.add_association(obj)
        lifecycleevent.modified(source)
        return filer.get_external_link(source)
    return None


def transfer_resource_from_filer(reference, context, source_filer, target_filer):
    path = urlparse(reference).path
    bucket, name = os.path.split(path)
    bucket = None if not bucket else bucket

    # don't save if already in target filer.
    if target_filer.contains(key=name, bucket=bucket):
        href = associate(context, target_filer, name, bucket)
        return (href, False)

    source = source_filer.get(path)
    if source is not None:
        contentType = getattr(source, 'contentType', None)
        contentType = contentType or mimetypes.guess_type(name)
        href = target_filer.save(name, source,
                                 bucket=bucket,
                                 overwrite=True,
                                 context=context,
                                 contentType=contentType)
        logger.info("%s was saved as %s", reference, href)
        return (href, True)

    return (None, False)


def transfer_resources_from_filer(provided, obj, source_filer, target_filer):
    """
    parse the provided interface field and look for internal resources to
    be gotten from the specified source filer and saved to the target filer
    """
    result = {}
    if source_filer is target_filer:
        return result
    for field_name in provided:
        if field_name.startswith('_'):
            continue
        value = getattr(obj, field_name, None)
        if      value is not None \
            and not IMethod.providedBy(value) \
            and isinstance(value, six.string_types) \
            and value.startswith(NTI_COURSE_FILE_SCHEME):
            # get resource and save it
            href, saved = transfer_resource_from_filer(value, obj,
                                                       source_filer,
                                                       target_filer)
            if not href:
                continue
            setattr(obj, field_name, href)
            if saved:
                result[field_name] = href
    return result


def _get_course_refs(courses, target=None):
    """
    Get all the related work refs for the given courses.
    """
    catalog = get_library_catalog()
    sites = get_component_hierarchy_names()
    container_ntiids = [ICourseCatalogEntry(x).ntiid for x in courses]
    result = catalog.search_objects(target=target,
                                    provided=INTIRelatedWorkRef,
                                    container_ntiids=container_ntiids,
                                    container_all_of=False,
                                    sites=sites)
    return result or ()


def get_content_related_work_refs(unit):
    """
    Pull all `:class:INTIRelatedWorkRefs` the given `:class:IContentUnit` is
    found in.
    """
    result = []
    package = find_interface(unit, IContentPackage, strict=False)
    if package is not None and getSite() is not None: # tests
        courses = get_courses_for_packages(packages=(package.ntiid,))
        if courses:
            result.extend(_get_course_refs(courses, package.ntiid))
    return result
