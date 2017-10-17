#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os

from requests.structures import CaseInsensitiveDict

from zope import component
from zope import interface
from zope import lifecycleevent

from zope.intid.interfaces import IIntIds

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import get_safe_source_filename
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentfile import validate_sources

from nti.app.contentfolder import ASSETS_FOLDER

from nti.app.contentfolder.resources import is_internal_file_link

from nti.app.contentfolder.utils import get_unique_file_name

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.discussions import get_topic_key
from nti.app.products.courseware.discussions import create_topics
from nti.app.products.courseware.discussions import auto_create_forums

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.app.products.courseware.views import VIEW_COURSE_DISCUSSIONS

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.common.string import is_true

from nti.contenttypes.courses.discussions.interfaces import NTI_COURSE_BUNDLE

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.discussions.parser import parse_discussions
from nti.contenttypes.courses.discussions.parser import path_to_discussions

from nti.contenttypes.courses.interfaces import DISCUSSIONS

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstancePublicScopedForum
from nti.contenttypes.courses.interfaces import ICourseInstanceForCreditScopedForum

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import ILinkExternalHrefOnly

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.links.externalization import render_link

from nti.links.links import Link

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


def render_to_external_ref(resource):
    link = Link(target=resource)
    interface.alsoProvides(link, ILinkExternalHrefOnly)
    return render_link(link)


def _handle_multipart(context, user, discussion, sources):
    filer = get_course_filer(context, user)
    for name, source in sources.items():
        if name in ICourseDiscussion:
            # remove existing
            location = getattr(discussion, name, None)
            if location and is_internal_file_link(location):
                filer.remove(location)
            # save a in a new file
            key = get_safe_source_filename(source, name)
            location = filer.save(key, source, overwrite=False,
                                  bucket=ASSETS_FOLDER, context=discussion)
            setattr(discussion, name, location)


@view_config(context=ICourseDiscussions)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_CONTENT_EDIT)
class CourseDiscussionsGetView(GenericGetView):

    def _do_call(self, discussions):
        result = LocatedExternalDict()
        result[MIMETYPE] = discussions.mimeType
        result[CLASS] = getattr(discussions, '__external_class_name__',
                                discussions.__class__.__name__)
        items = result[ITEMS] = []
        for discussion in sorted(discussions.values()):
            ext_obj = to_external_object(discussion)
            ext_obj['href'] = render_to_external_ref(discussion)
            items.append(ext_obj)
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        result.__parent__ = self.context
        result.__name__ = self.request.view_name
        result.lastModified = discussions.lastModified
        return result

    def __call__(self):
        return self._do_call(self.context)


@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name=VIEW_COURSE_DISCUSSIONS,
               permission=nauth.ACT_CONTENT_EDIT)
class CatalogEntryCourseDiscussionView(CourseDiscussionsGetView):

    def __call__(self):
        course = ICourseInstance(self.context)
        discussions = ICourseDiscussions(course)
        return self._do_call(discussions)


@view_config(context=ICourseDiscussions)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_CONTENT_EDIT)
class CourseDiscussionsPostView(AbstractAuthenticatedView,
                                ModeledContentUploadRequestUtilsMixin):

    content_predicate = ICourseDiscussion.providedBy

    def readCreateUpdateContentObject(self, user):
        result = super(CourseDiscussionsPostView, self).readCreateUpdateContentObject(user)
        sources = get_all_sources(self.request)
        return result, sources

    def _do_call(self):
        creator = self.remoteUser
        discussion, sources = self.readCreateUpdateContentObject(creator)
        discussion.creator = creator.username
        discussion.updateLastMod()
        # register discussion
        intids = component.getUtility(IIntIds)
        doc_id = intids.register(discussion)
        # get a unique file nane
        name = get_unique_file_name("%s.json" % doc_id, self.context)
        lifecycleevent.created(discussion)
        self.context[name] = discussion
        # set a proper NTI course bundle id
        course = ICourseInstance(self.context)
        path = path_to_discussions(course)
        path = os.path.join(path, name)
        iden = "%s://%s" % (NTI_COURSE_BUNDLE, path)
        discussion.id = iden
        # handle multi-part data
        if sources:
            validate_sources(self.remoteUser, discussion, sources)
            _handle_multipart(self.context, self.remoteUser,
                              discussion, sources)
        self.request.response.status_int = 201
        return discussion


@view_config(context=ICourseDiscussion)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_CONTENT_EDIT)
class CourseDiscussionPutView(UGDPutView):

    def updateContentObject(self, contentObject, externalValue, set_id=False, notify=True):
        result = UGDPutView.updateContentObject(self,
                                                contentObject,
                                                externalValue,
                                                set_id=set_id,
                                                notify=notify)
        sources = get_all_sources(self.request)
        if sources:
            validate_sources(self.remoteUser, result, sources)
            _handle_multipart(self.context, self.remoteUser,
                              self.context, sources)
        return result


@view_config(context=ICourseDiscussion)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               permission=nauth.ACT_CONTENT_EDIT)
class CourseDiscussionDeleteView(UGDDeleteView):
    
    def _do_delete_object(self, theObject):
        container = theObject.__parent__
        del container[theObject.__name__]
        return theObject


# admin


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name="CreateDiscussionTopics",
               permission=nauth.ACT_CONTENT_EDIT)
class CreateCourseDiscussionTopicsView(AbstractAuthenticatedView):

    def __call__(self):
        result = LocatedExternalDict()
        items = result[ITEMS] = {}
        course = ICourseInstance(self.context)
        entry = ICourseCatalogEntry(course)
        data = items[entry.ntiid] = []
        auto_create_forums(course)  # always
        discussions = ICourseDiscussions(course)
        for discussion in discussions.values():
            data.extend(create_topics(discussion, False))
        result[TOTAL] = result[ITEM_COUNT] = len(data)
        return result


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name="SyncDiscussions",
               permission=nauth.ACT_CONTENT_EDIT)
class SyncCourseDiscussionsView(AbstractAuthenticatedView,
                                ModeledContentUploadRequestUtilsMixin):

    def readInput(self, value=None):
        if self.request.body:
            values = super(SyncCourseDiscussionsView, self).readInput(value)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    def __call__(self):
        values = self.readInput()
        force = is_true(values.get('force'))
        course = ICourseInstance(self.context)
        root = course.root
        if root is not None:
            ds_bucket = root.getChildNamed(DISCUSSIONS)
            if ds_bucket is not None:
                parse_discussions(course, ds_bucket, force)
        return hexc.HTTPNoContent()


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name="DropDiscussions",
               permission=nauth.ACT_CONTENT_EDIT)
class DropCourseDiscussionsView(AbstractAuthenticatedView,
                                ModeledContentUploadRequestUtilsMixin):

    def readInput(self, value=None):
        if self.request.body:
            values = super(SyncCourseDiscussionsView, self).readInput(value)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    def __call__(self):
        result = LocatedExternalDict()
        items = result[ITEMS] = {}
        course = ICourseInstance(self.context)
        entry = ICourseCatalogEntry(course)
        data = items[entry.ntiid] = {}
        # loop and drop
        discussions = ICourseDiscussions(course)
        discussions = {get_topic_key(d) for d in discussions.values()}
        for forum in course.Discussions.values():
            if      not ICourseInstancePublicScopedForum.providedBy(forum) \
                and not ICourseInstanceForCreditScopedForum.providedBy(forum):
                continue
            for key in discussions:
                if key in forum:
                    del forum[key]
                    data.setdefault(forum.__name__, [])
                    data[forum.__name__].append(key)
        result[TOTAL] = result[ITEM_COUNT] = len(data)
        return result
