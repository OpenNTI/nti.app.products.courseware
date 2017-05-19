#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views related to administration of courses.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from requests.structures import CaseInsensitiveDict

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware import VIEW_COURSE_ADMIN_LEVELS

from nti.app.products.courseware.views import MessageFactory as _

from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.contenttypes.courses.creator import install_admin_level

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel

from nti.contenttypes.courses.interfaces import ICourseCatalog

from nti.dataserver import authorization as nauth

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseCatalog,
             name=VIEW_COURSE_ADMIN_LEVELS,
             request_method='GET',
             permission=nauth.ACT_NTI_ADMIN)
class AdminLevelsGetView(AbstractAuthenticatedView):
    """
    Fetch the administrative levels under the course catalog.
    """

    def __call__(self):
        result = LocatedExternalDict()
        admin_levels = self.context.get_admin_levels()
        result[ITEMS] = {x:to_external_object(y, name='summary')
                         for x, y in admin_levels.items()}
        result[ITEM_COUNT] = len(admin_levels)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseCatalog,
             name=VIEW_COURSE_ADMIN_LEVELS,
             request_method='POST',
             permission=nauth.ACT_NTI_ADMIN)
class AdminLevelsPostView(AbstractAuthenticatedView,
                          ModeledContentUploadRequestUtilsMixin):
    """
    A view to create a new ICourseAdministrativeLevel, given as
    a 'key' param.
    """

    def readInput(self):
        if self.request.body:
            values = read_body_as_external_object(self.request)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    def _get_admin_key(self):
        values = self.readInput()
        result =   values.get('name') \
                or values.get('level') \
                or values.get('key')
        if not result:
            raise hexc.HTTPUnprocessableEntity(_('Must supply admin level key.'))
        return result

    def _insert(self, admin_key):
        # Do not allow children levels to mask parent levels.
        admin_levels = self.context.get_admin_levels()
        if admin_key in admin_levels:
            raise hexc.HTTPUnprocessableEntity(_('Admin key already exists.'))
        result = install_admin_level(admin_key, catalog=self.context)
        return result

    def __call__(self):
        admin_key = self._get_admin_key()
        new_level = self._insert(admin_key)
        logger.info("Created new admin level (%s)", admin_key)
        return new_level


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseAdministrativeLevel,
             request_method='DELETE',
             permission=nauth.ACT_NTI_ADMIN)
class AdminLevelsDeleteView(UGDDeleteView):
    """
    Currently only allow deletion of admin levels if it is empty.
    """

    def _do_delete_object(self, theObject):
        del theObject.__parent__[theObject.__name__]
        return theObject

    def __call__(self):
        if len(self.context):
            raise hexc.HTTPUnprocessableEntity(
                        _('Cannot delete admin level with underlying objects.'))
        result = super(AdminLevelsDeleteView, self).__call__()
        logger.info('Deleted %s', self.context)
        return result


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               permission=nauth.ACT_NTI_ADMIN)
class DeleteCourseView(AbstractAuthenticatedView):

    def __call__(self):
        course = ICourseInstance(self.context)
        logger.info('Deleting course (%s)', ICourseCatalogEntry(course).ntiid)
        del course.__parent__[course.__name__]
        return hexc.HTTPNoContent()