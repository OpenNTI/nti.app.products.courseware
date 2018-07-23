#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=inherit-non-class,expression-not-assigned

from zope import interface

from zope.container.constraints import contains

from zope.container.interfaces import IContained
from zope.container.interfaces import IContainer

from nti.app.products.webinar.interfaces import IWebinar

from nti.base.interfaces import ICreated
from nti.base.interfaces import ILastModified

from nti.contenttypes.completion.interfaces import ICompletableItem

from nti.contenttypes.presentation.interfaces import href_schema_field
from nti.contenttypes.presentation.interfaces import IUserCreatedAsset
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTIIDIdentifiable
from nti.contenttypes.presentation.interfaces import INonExportableAsset
from nti.contenttypes.presentation.interfaces import ICoursePresentationAsset

from nti.coremetadata.interfaces import IUser

from nti.schema.field import Int
from nti.schema.field import Bool
from nti.schema.field import Number
from nti.schema.field import Object
from nti.schema.field import HTTPURL
from nti.schema.field import DateTime
from nti.schema.field import ValidText
from nti.schema.field import ListOrTuple
from nti.schema.field import ValidDatetime
from nti.schema.field import DecodingValidTextLine as ValidTextLine


class IWebinarAsset(ICoursePresentationAsset,
                    IUserCreatedAsset,
                    IGroupOverViewable,
                    INTIIDIdentifiable,
                    INonExportableAsset,
                    ICompletableItem):
    """
    A presentation asset for webinars. These assets, since they are temporal,
    should not be exported or imported.
    """

    title = ValidTextLine(title=u"The webinar asset title",
                          required=False)

    description = ValidTextLine(title=u"The webinar asset description",
                                required=False)

    webinar = Object(IWebinar, required=True)

    icon = href_schema_field(title=u"Webinar asset icon href",
                             required=False)



class ICourseWebinarContainer(IContainer):
    """
    A storage container for :class:`IWebinar` objects, accessible on the course context.
    """
    contains(IWebinar)

    def get_or_create_webinar(webinar):
        """
        Normalize the given :class:`IWebinar` in our container.
        """
