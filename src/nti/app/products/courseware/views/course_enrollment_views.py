#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.view import view_config

from zope import interface

from zope.traversing.interfaces import IPathAdapter

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.interfaces import IEnrollmentOption
from nti.app.products.courseware.interfaces import IEnrollmentOptionContainer

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.dataserver.authorization import ACT_CONTENT_EDIT

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IPathAdapter)
def options_path_adapter(course, unused_request):
    return IEnrollmentOptionContainer(course)


@view_config(route_name='objects.generic.traversal',
             context=IEnrollmentOptionContainer,
             request_method='PUT',
             permission=ACT_CONTENT_EDIT,
             renderer='rest')
class EnrollmentOptionInsertView(AbstractAuthenticatedView,
                                 ModeledContentUploadRequestUtilsMixin):
    """
    Insert a new :class:`IEnrollmentOption` into the course
    :class:`IEnrollmentOptionContainer`.
    """

    def _do_call(self):
        enrollment_option = self.readCreateUpdateContentObject(self.remoteUser)
        self.context[enrollment_option.ntiid] = enrollment_option
        logger.info('Created enrollment option (%s)', enrollment_option.ntiid)
        return enrollment_option


@view_config(route_name='objects.generic.traversal',
             context=IEnrollmentOption,
             request_method='DELETE',
             permission=ACT_CONTENT_EDIT,
             renderer='rest')
class EnrollmentOptionDeleteView(UGDDeleteView):
    """
    Delete an :class:`IEnrollmentOption` from its container.
    """

    def _do_delete_object(self, option):
        try:
            del self.context.__parent__[option.ntiid]
        except KeyError:
            pass
        logger.info('Deleted enrollment option (%s)', option.ntiid)
        return option


@view_config(route_name='objects.generic.traversal',
             context=IEnrollmentOption,
             request_method='PUT',
             permission=ACT_CONTENT_EDIT,
             renderer='rest')
class EnrollmentOptionPutView(UGDPutView):
    """
    Allow editing of a :class:`IEnrollmentOption`.
    """
