#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=inherit-non-class,expression-not-assigned

from zope.container.constraints import contains

from zope.container.interfaces import IContainer

from nti.app.products.webinar.interfaces import IWebinar

from nti.contenttypes.completion.interfaces import ICompletableItem

from nti.contenttypes.presentation.interfaces import href_schema_field
from nti.contenttypes.presentation.interfaces import IUserCreatedAsset
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTIIDIdentifiable
from nti.contenttypes.presentation.interfaces import INonExportableAsset
from nti.contenttypes.presentation.interfaces import IAssetTitleDescribed
from nti.contenttypes.presentation.interfaces import ICoursePresentationAsset

from nti.schema.field import Text
from nti.schema.field import Object
from nti.schema.field import DecodingValidTextLine as ValidTextLine


class IWebinarAsset(ICoursePresentationAsset,
                    IUserCreatedAsset,
                    IGroupOverViewable,
                    INTIIDIdentifiable,
                    INonExportableAsset,
                    IAssetTitleDescribed,
                    ICompletableItem):
    """
    A presentation asset for webinars. These assets, since they are temporal,
    should not be exported or imported.
    """

    title = ValidTextLine(title=u"The webinar asset title",
                          required=False)

    description = Text(title=u"The webinar asset description",
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
