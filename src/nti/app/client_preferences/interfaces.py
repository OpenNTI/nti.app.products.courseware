#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Temporary home for the schemas that define the preferences
for apps on the platform. (A temporary home is fine because these
are only in the ZCA, not the database---unless a ZCA site is
persisted. Ultimately expect this and the ZCML file to be moved
to zope-style products.)

The :mod:`zope.preference` package has great documentation, check
it out.

Things to remember:

* The schema interfaces can only have fields, and they should
  generally be primitive types. Never use an interface that is already
  a model object.
* The preferences are arranged in a tree, beginning with the (empty) root.
  This tree is expressed in the ZCML file in the way groups are named.
  Children of the tree have no dots in their name, sub-children have
  one dot and so on. These names are extremely important and become
  part of the URL and data and should not change.
* When to make a new child (group) versus add settings to an existing
  schema? Because children can be fetched and edited independently,
  settings that are frequently updated together (or not updated when
  other settings are) are a good candidate for a group. When parent
  data is fetched, all (recursive) children are also fetched. A sub-group
  is the easiest way to introduce modeled preferences that go together; otherwise,
  you are limited to what you can define for the Dict or Mapping types.
* If you add a group, you must add it to the ZCML file.
* Preferences can have defaults specified in the schema. They can also
  have defaults specified on a site-by-site basis, and even at particular
  nodes in the URL tree (for example, the default sort order for
  forums might be different than for UGD).
* When defining fields, prefer the objects in :mod:`nti.utils.schema`
  over similar objects in :mod:`zope.schema` for better error messages,
  censoring support, etc.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.interface import Interface
from zope.interface.interface import taggedValue
from nti.utils import schema

from . import MessageFactory as _

TAG_EXTERNAL_PREFERENCE_GROUP = '__external_preference_group__'

class IWebAppUserSettings(Interface):
	"""
	The root of the settings tree for browser-application
	specific preferences. See comments in the ZCML file for
	naming.
	"""

	preferFlashVideo = schema.Bool(
		title=_('Prefer Flash-based video instead of native HTML video when possible'),
		default=False)

	taggedValue( TAG_EXTERNAL_PREFERENCE_GROUP, 'write' )

from nti.chatserver.interfaces import IUnattachedPresenceInfo
IUnattachedPresenceInfo.setTaggedValue( TAG_EXTERNAL_PREFERENCE_GROUP, 'write' )
from nti.contentfragments.interfaces import PlainTextContentFragment

class IChatPresenceSettings(Interface):
	"""
	A child of the root, specifying chat presence defaults.

	This interface itself is blank; instead, its values
	are defined as child groups. Each group corresponds to
	a "preset" that the user can choose from. The "Active"
	preset is the one to use when the user enters the application;
	the other presets define what happens when the user selects the
	corresponding preset.

	When the user picks a preset, the Active group should be updated
	by copying the preset. If the user customizes their state, those
	customizations can be recorded in the Active group.

	Subgroups may include: DND, Available, Away (but see the ZCML
	file for definitions).

	"""
	taggedValue(TAG_EXTERNAL_PREFERENCE_GROUP, 'write')

# Below we're going out of our way to reuse the existing
# presence info class and fields so that we're sure
# they match the constraints actually enforced by the
# chatserver. Most new preferences won't need to do this

class IAvailableChatPresenceSettings(IUnattachedPresenceInfo):
	"""Provide the defaults for the Available state"""

	show = IUnattachedPresenceInfo['show'].bind(None)
	status = IUnattachedPresenceInfo['status'].bind(None)
	taggedValue(TAG_EXTERNAL_PREFERENCE_GROUP, 'write')

IAvailableChatPresenceSettings['status'].default = PlainTextContentFragment('Available')

class IAwayChatPresenceSettings(IUnattachedPresenceInfo):
	"""Provide the defaults for the Away state"""

	show = IUnattachedPresenceInfo['show'].bind(None)
	status = IUnattachedPresenceInfo['status'].bind(None)
	taggedValue(TAG_EXTERNAL_PREFERENCE_GROUP, 'write')

IAwayChatPresenceSettings['status'].default = PlainTextContentFragment('Away')
IAwayChatPresenceSettings['show'].default = 'away'


class IDNDChatPresenceSettings(IUnattachedPresenceInfo):
	"""Provide the defaults for the DND state"""

	show = IUnattachedPresenceInfo['show'].bind(None)
	status = IUnattachedPresenceInfo['status'].bind(None)
	taggedValue(TAG_EXTERNAL_PREFERENCE_GROUP, 'write')

IDNDChatPresenceSettings['status'].default = PlainTextContentFragment('Do Not Disturb')
IDNDChatPresenceSettings['show'].default = 'dnd'

for iface in IAvailableChatPresenceSettings, IAwayChatPresenceSettings, IDNDChatPresenceSettings:
	for name in 'show', 'status':
		iface[name].interface = iface
		if iface[name].__dict__['default'] != iface[name].default:
			del iface[name].defaultFactory
	iface.changed(iface)
