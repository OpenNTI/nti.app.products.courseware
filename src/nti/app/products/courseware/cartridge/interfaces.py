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

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.schema.field import Object
from nti.schema.field import DecodingValidTextLine as TextLine


class ICommonCartridge(interface.Interface):
    course = Object(ICourseInstance, title=u"The course")

    archive = TextLine(
        title=u"A valid directory location for the archive data"
    )


class IManifestBuilder(interface.Interface):
    cartridge = Object(ICommonCartridge, title=u"The cartridge")


class IElementHandler(interface.Interface):
    """
    Adapter to handle an asset within a common cartridge
    """
    cartridge = Object(ICommonCartridge, title=u"The cartridge")
