=====================
Course Archive Format
=====================

This document describes the NextThought Course Archive (course
archive, or more simply archive) format. An archive is a zip* file
containing the structure and assets of the course. The archive format
is designed to be a full representation of course content. It can be
used to backup course content or as a custom intermediate format to
move course content to another system.

Course archives can be extracted from the NextThought LMS using the
"Export Course" functionality.

.. note:: Link to help site on how to do this.

The archive contains a number of structured files in ``json`` and,
``xml`` format (identified by the file extension and contents) as well
as user provided assets (images, documents, pdfs, etc.).

Common Object Properties
========================

Class - A type identifier for the object

MimeType - An RFC-6838 MIME type identifying the type of object

Creator - The creator of the object identified by their unique
Username.

CreatedTime - The created time of the object represented as the time
in seconds since the epoch as a floating point number.

Last Modified - The most recent modification time of the object represented as the time
in seconds since the epoch as a floating point number.

NTIID - A globally unique identifier for the object.

OID - An internal unique identifier for the object.

acclaim_badges.json
===================

A list of AcclaimBadge objects that are awarded to learners upon
successful completion of the course.

Objects with a ``Class`` property of ``AcclaimBadge`` and a
``MimeType`` of ``application/vnd.nextthought.acclaim.badge`` have
the following interface.

.. autointerface:: nti.app.products.acclaim.interfaces.IAcclaimBadge
    :noindex:
    :no-show-inheritance:

assessment_index.json
=====================

.. note:: How does this differ from the evaluation index.

assests (folder)
================

A folder of uploaded course assets

.. note:: Can we link in the help site that describes the assets. This
   is what you get when you upload an image in the course.


assignment_policies.json
========================

Assignment policy overrides in place for this course. These values are merged on top of assignment objects to provide course specific policies.

evaluation_index.json
=====================

An index of all assignment, survey, question sets, questions, and polls in the course.

Documents (folder)
==================

Additional documents uploaded to the course

.. note:: I don't have any clue why some docuemnts are here and others are in assets.

Images (folder)
===============

Additional images uploaded to the course

.. note:: I don't have any clue why some images are here and others are in assets.

Lessons (folder)
================

Contains a ``json`` file for each lesson, describing the overview of the lesson.
The ``json`` files are referenced in ``course_outline.xml`` and ``course_outline.json``, to build the full course structure.

The lesson overview has the following hierarchy:

::

	Lesson Overview
	└── Overview Group(s)
		└── Lesson Asset(s)

Lesson Overview
---------------

The lesson's ``json`` file will contain exactly one lesson overview object.

.. list-table:: Fields
	:header-rows: 1

	* - Name
	  - Type
	  - Description
	* - MimeType
	  - string
	  - "application/vnd.nextthought.ntilessonoverview"
	* - title
	  - string
	  - The name of the lesson (should match the name of the outline node)
	* - Items
	  - array
	  - An array of the overview groups in this lesson
	* - isPublished
	  - boolean
	  - If the contents of the lesson are available to learners.
	* - publishBeginning
	  - date
	  - When the contents of the lesson should become available to learners.
	* - publishEnding
	  - date
	  - When the contents of the lesson should become unavailable to learners.

Overview Group
--------------

The lesson overview's Items will be a zero or more overview groups.

.. list-table:: Fields
	:header-rows: 1

	* - Name
	  - Type
	  - Description
	* - MimeType
	  - string
	  - "application/vnd.nextthought.nticourseoverviewgroup"
	* - title
	  - string
	  - The name of the overview groups
	* - accentColor
	  - string
	  - A color (in `https://en.wikipedia.org/wiki/Web_colors#Hex_triplet <hex format>_`)assigned to the group to help create visual contrast.

Lesson Asset
------------

The assets in a lesson

bundle_dc_metadata.xml
======================

`https://dublincore.org <Dublin Core metadata>_` for the course.

bundle_meta_info.json
=====================

Additional external content referenced by the course.

completable_item_default_required.json
======================================

A list of content types, specified by ``MimeType`` that this course
requires by default.

.. note:: Link in the help.nextthought.com docs where this is
          configured in the platform.

.. autointerface:: nti.contenttypes.completion.interfaces.ICompletableItemDefaultRequiredPolicy
   :no-members:
   :members: mime_types



completable_item_required.json
==============================

A list of required/optional overrides for content in the course.

completion_policies.json
========================

The aggregate completion policy for the course.

content_packages.json
=====================

A list of ContentPackage objects referenced in the course. Contents are gzip, base 64, ReSTructured text.

course_info.json
================

Catalog information for the course.

course_outline.json
===================

A json representation of the course structure (units and lessons)

course_outline.xml
==================

An xml representation of the course structure (units and lessons)

course_tab_preferences.json
===========================

A ``json`` file containing overrides to the course's tab names.
There is only a ``names`` key which maps the tab name to the display name.

.. note:: Enterprise site may have global overrides not accounted for here

.. list-table:: Tabs
	:header-rows: 1

	* - Name
	  - Default display
	* - lessons
	  - Lessons
	* - assignments
	  - Assignments
	* - discussions
	  - Community
	* - info
	  - Course info

dc_metadata.xml
===============

`https://dublincore.org <Dublin Core metadata>_` for the course.

ims_configured_tools.json
=========================

List of configured LTI tools in the course.

.. autointerface:: nti.ims.lti.interfaces.IConfiguredTool

.. autointerface:: nti.ims.lti.interfaces.IToolConfig


meta_info.json
==============

A ``json`` file containing metadata about the export archive. The json
object has the following fields.

.. list-table:: Fields
   :header-rows: 1

   * - Field Name
     - Type
     - Description
   * - CreatedTime
     - String
     - The creation time of this archive in ISO-8601 format.
   * - Creator
     - String
     - The Username of the user that created the export.
   * - ExportHash
     - String
     - An opaque, unique identifier for this archive
   * - MimeType
     - String
     - The MimeType of the object this archive
       represents. e.g. ``application/vnd.nextthought.courses.courseinstance``

For example:

.. code:: json

   {
	"CreatedTime": "2021-12-22T17:06:26Z",
	"Creator": "admin1",
	"ExportHash": "49115848444338989_1640192784.88",
	"MimeType": "application/vnd.nextthought.courses.courseinstance"
   }

presentation-assests
====================

The presentation assets for the course. This includes cover, thumbnail, background, etc. Anything outside the `webapp` folder should be ignored.

.. list-table:: Presentation Assets
   :header-rows: 1

   * - File Name
     - Size
     - Description
   * - contentpackage-thumb-60x60.png
     - 120px X 120px
     - Used in list presentation of courses
   * - contentpackage-landing-232x170.png
     - 464px X 240px
     - Used in card presentation of coursses
   * - background.png
     - 3000px X 2000px
     - Used as the background image when on a course, has a guassian blur to handle
   * - client_image_source.png
     - any
     - The source image used to generate the other images
   * - course-promo-large-16x9.png
     - deprecated
     - deprecated
   * - course-cover-232x170.png
     - deprecated
     - deprecated
   * - contentpackage-cover-256x156
     - deprecated
     - deprecated

role_info.json
==============

A ``json`` file providing a mapping of course roles and the users
assigned to them.

.. note:: Provide the mapping of how these show in the UI to what ends
          up in the role map.

.. code:: json

   {
	"nti.roles.course_content_editor": {
		"allow": [
			"editor1",
			"instructor1"
		]
	},
	"nti.roles.course_instructor": {
		"allow": [
			"instructor1",
			"grader1"
		]
	}
   }


user_assets.json
================

A list of additional assets in the course. Typically videos.

.. autointerface:: nti.contenttypes.presentation.interfaces.INTIVideo

.. list-table:: Video Fields
    :header-rows: 1

    * - Field
      - Type
      - Description
	* - MimeType
	  - string
	  - "application/vnd.nextthought.ntivideo"
    * - title
      - string
      - Name of the video
    * - sources
      - VideoSource[]
      - List of possible sources for the video (typically only one)
    * - transcripts
      - Transcript[]
      - List of transcripts attached to the video

.. autointerface:: nti.contenttypes.presentation.interfaces.INTIVideoSource

.. list-table:: Video Source Fields
    :header-rows: 1

    * - Field
      - Type
      - Description
    * - service
      - string
      - the service hosting the video one of 'kaltura', 'vimeo', 'wistia', 'youtube'
    * - source
      - string
      - the service specific id

To generate the video src combine the source with the service's base URL

.. note:: Youtube

	:service: "youtube"
	:base URL: "https://www.youtube.com/{source}"

	For Example:

	:source: "aqz-KE-bpKQ"
	:video src: https://www.youtube.com/aqz-KE-bpKQ

.. note:: Vimeo

	:service: "vimeo"
	:base URL: "https://www.vimeo.com/{source}"

	For Example:

	:source: "798022"
	:video src: https://www.vimeo.com/798022

.. note:: Wistia

	:service: "wistia"
	:base URL: "https://fast.wistia.com/embed/iframe/{source}"

	For Example:

	:source: s3lqfi0zn7
	:base URL: https://fast.wistia.com/embed/iframe/s3lqfi0zn7



.. autointerface:: nti.contenttypes.presentation.interfaces.INTITranscript

.. list-table:: Transcript
    :header-rows: 1

    * - Field
      - Type
      - Description
    * - lang
      - string
      - The language of the transcript
    * - purpose
      - string
      - The purpose of the transcript (one of 'captions', 'normal')
    * - src (srcjsonp)
      - string
      - the URL of the .vtt file (`specification<https://www.w3.org/TR/webvtt1/>`_)

.. note:: Need to include documentation of the supported services, types, and sources

.. note:: Document inline transcript content format


vendor_info.json
================

Additional vendor related information for the course, if applicable. This file is only applicable in certain legacy courses.
