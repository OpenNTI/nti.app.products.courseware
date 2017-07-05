#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id:
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver import authorization as nauth

from nti.recorder.utils import record_transaction


@view_config(route_name='objects.generic.traversal',
             request_method='POST',
             name="edit",
             context=ICourseCatalogEntry,
             permission=nauth.ACT_CONTENT_EDIT)
class EditCourse(AbstractAuthenticatedView,
                 ModeledContentUploadRequestUtilsMixin):
    """
    Route making ICourseCatalogEntries available for editing.
    Takes attributes to update as parameters.
    """

    def readInput(self, value=None):
        if self.request.body:
            values = super(AbstractAuthenticatedView, self).readInput(value)
        else:
            values = self.request.params
        return values

    def __call__(self):
        # Get input
        values = self.readInput()

        # If any of the arguments given aren't valid attributes,
        # return 400 Bad Reqest
        if not all(hasattr(self.context, att) for att in values.keys()):
            return hexc.HTTPBadRequest()

        # Update the attributes
        for key, value in values.items():
            setattr(self.context, key, value)

        # Record the transaction
        record_transaction(self.context)

        # Ouput information to logger
        logger_str = "".join(["%s: %s\n" % (key, value)
                              for (key, value) in values.items()])
        logger.info(
            "Course catalog %s was modified with values:\n %s" %
            (self.context.ntiid, logger_str))

        # No content needs to be returned
        return hexc.HTTPNoContent()
