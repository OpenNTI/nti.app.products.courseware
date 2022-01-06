=====================
Course Archive Format
=====================

This document describes the NextThought Course Archive ("course
archives", or more simply, "archive") format. An archive is a zip* file
containing the structure and assets of the course. The archive format
is designed to be a full representation of course content. It can be
used to back up course content or as a custom intermediate format to
move course content to another system.

Course archives can be extracted from the NextThought LMS using the
"Export Course" functionality.

.. note:: Link to help site on how to do this.

The archive contains a number of structured files in ``json`` and,
``xml`` format (identified by the file extension and contents) as well
as folders containing user-provided assets (where those assets are images, documents, pdfs, etc.).

Common Object Properties
========================

Class - A type identifier for the object

MimeType - An RFC-6838 MIME type identifying the type of object

Creator - The creator of the object identified by their unique
Username.

CreatedTime - The time the object was created, represented as the time
in seconds since the epoch (a floating point number)

Last Modified - The most recent modification time of the object, represented as the time
in seconds since the epoch (a floating point number)

NTIID - A global, unique identifier for the object

OID - An internal, unique identifier for the object

Publication
-----------

Certain object's track publication state. While publication semantics
may vary based on the type of object, publication state is most
commonly used to control the visibilty of the object. Objects
supporting publication provide the following attributes.


.. list-table:: Fields
   :header-rows: 1

   * - Field Name
     - Type
     - Description
   * - isPublished
     - Boolean
     - Whether or not the object is published.
   * - publishLastModified
     - Timestamp
     - The timestamp at which this object updated its publication state.

Additionally some objects may have publication state driven by
calendar dates. For example this object is published at a particular
date and time. These objects supporting calendar based publication
provide the following *additional* attributes.

.. list-table:: Fields
   :header-rows: 1

   * - Field Name
     - Type
     - Description
   * - publishBeginning
     - DateTime
     - When present, this specifies the time instant at which this
       object is to be available.
   * - publishEnding
     - DateTime
     - When present, this specifies the last instance at which this
       object is to be available.


acclaim_badges.json
===================

A list of AcclaimBadge objects that are awarded to learners upon
successful completion of the course

Objects with a ``Class`` property of ``AcclaimBadge`` and a
``MimeType`` of ``application/vnd.nextthought.acclaim.badge`` have
the following interface.

.. autointerface:: nti.app.products.acclaim.interfaces.IAcclaimBadge
    :noindex:
    :no-show-inheritance:
	
..warning: Needs more detail, including listing the attributes kept for each badge (eg, name, organization_id, state, visibility)

assessment_index.json
=====================

.. note:: How does this differ from the evaluation index. (SMH: I have yet to find a course with one of these files, so once we do, can update this section.)

assests (folder)
================

A folder of uploaded course assets that are used within lessons and readings

.. note:: Can we link in the help site that describes the assets. This
   is what you get when you upload an image in the course.


assignment_policies.json
========================

Assignment policy overrides in place for this course
These values are merged on top of assignment objects to provide course-specific policies.

..warning: Needs more detail, especially in clarifying meaning of the second line. Might be helpful to include an example translation from a block of json file representing one assignment to its meaning for the course.

evaluation_index.json
=====================

An index of all assignments, surveys, question sets, questions, and polls in the course

..warning: Needs more detail, including listing the attributes kept in that index for each assignment, poll, etc. (the Class, CreatedTime, Creator, etc.)

Documents (folder)
==================

Additional documents uploaded to the course

.. note:: I don't have any clue why some documents are here and others are in assets. (SMH: the definition above has been modified according to my theory of why these are divided; I believe it turns on whether a file is within, or itself, a lesson.)

Images (folder)
===============

Additional images uploaded to the course

.. note:: I don't have any clue why some images are here and others are in assets. (SMH: again, this definition now reflects my theory.)

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

A list of required/optional overrides for content in the course

..warning: Needs more detail; not sure what the contents of this document indicate. Perhaps we should add an example for the user and a translation?

completion_policies.json
========================

The aggregate completion policy for the course

content_packages.json
=====================

A list of ContentPackage objects referenced in the course. Contents are gzip, base 64, ReSTructured text files.

..warning: Needs more detail

course_info.json
================

Catalog information for the course

..warning: Needs more detail.

course_outline.json
===================

A json representation of the course outline, lesson structure, of the
course. The course outline is a tree structure of course outline nodes
representing the nodes in a course. Outline nodes containing other
nodes are sometimes referred to as ``Units``. Leaf nodes in the tree,
``CourseOutlineContentNode`` objects point to lesson content instead
of other nodes.

.. list-table:: Fields
   :header-rows: 1

   * - Field Name
     - Type
     - Description
   * - AvailableBeginning
     -
     -
   * - AvailableEnding
     -
     -
   * - title
     -
     -
   * - Items
     -
     -


Additionally ``CourseOutlineContentNode`` objects add a ``src`` field
that references the ``LessonOverview`` json file from the ``Lessons`` folder.

.. list-table:: Fields
   :header-rows: 1

   * - Field Name
     - Type
     - Description
   * - src
     -
     -


.. note:: In practice the CourseOutline is typically 2 levels, the
          first level maps to ``Units`` and the second level maps to
          ``Lessons``. Some legacy courses may have ``CourseOutlineNode``
          objects that nest more than 2 levels.

Course Outline Node Publication
-------------------------------

The publication properties on course outline nodes drive the
visibility of those outline nodes to learners. Only published
outline nodes are visible in the Course's lesson structure for learners. All nodes are visible to instructors and editors when in editing mode.

course_outline.xml
==================

.. warning:: This file is deprecated and replaced by `course_outline.json`_.

An xml representation of the course structure (units and
lessons). This is a legacy format. In general we recommend using the
`course_outline.json`_ representation as it is more verbose.

course_tab_preferences.json
===========================

A ``json`` file containing overrides to the course's default tab names (as displayed on the Course page)
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
	  
..warning: Should we also mention the ``order`` list that (I presume) sets the order in which the tabs are listed?

dc_metadata.xml
===============

`https://dublincore.org <Dublin Core metadata>_` for the course.

..warning: Needs more detail; see the above warning for the bundle_dc_metadata.xml file.

ims_configured_tools.json
=========================

List of configured LTI tools in the course

.. autointerface:: nti.ims.lti.interfaces.IConfiguredTool

.. autointerface:: nti.ims.lti.interfaces.IToolConfig

..warning: Needs more detail

meta_info.json
==============

A ``json`` file containing metadata about the export archive.
The json object has the following fields::

.. list-table:: Fields
   :header-rows: 1

   * - Field Name
     - Type
     - Description
   * - CreatedTime
     - String
     - The creation time of this archive in ISO-8601 format
   * - Creator
     - String
     - The Username of the user that created the export
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

presentation-assests (folder)
=============================

The presentation assets for the course. This includes cover, thumbnail, background, etc. Anything outside the `webapp` folder (which is found within presentation-assets) should be ignored.

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
     - Deprecated
     - Deprecated
   * - course-cover-232x170.png
     - Deprecated
     - Deprecated
   * - contentpackage-cover-256x156
     - Deprecated
     - Deprecated

..warning: I'm not sure what it implies, but I found these allegedly deprecated images within the webapp folder.

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

A list of additional assets in the course, typically videos

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
      - The service hosting the video; either 'kaltura,' 'vimeo,' 'wistia,' or 'youtube'
    * - source
      - string
      - The service-specific ID

To generate the video src, combine the source with the service's base URL

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
      - The purpose of the transcript (either 'captions' or 'normal')
    * - src (srcjsonp)
      - string
      - the URL of the .vtt file (`specification<https://www.w3.org/TR/webvtt1/>`_)

.. note:: Need to include documentation of the supported services, types, and sources

.. note:: Document inline transcript content format


vendor_info.json
================

Additional vendor-related information for the course, if applicable (only applicable in certain legacy courses)

.. warning:: Needs more detail

ScormContent (folder)
=====================

The SCORM content files uploaded as part of this course. The folder
contains a unique folder for each SCORM package in the course
containing metadata about the package and the original SCORM content package itself.

::

	ScormContent
	└── tag_nextthought.com_2011-10_NTI-ScormContentInfo-1BC4CCEA431F1E6166205A94AC39402C174C67AF4E1CBEEB692E501C5D17F8AF_0087
		└── scorm_content.json
		└── myscorm_package.zip

The metadata for this scorm package is found in the
``scorm_content.json`` file and has the following structure.

.. list-table:: scorm_content.json
    :header-rows: 1

    * - Field
      - Type
      - Description
    * - NTIID
      - string
      - The unique identifier for this scorm package.
    * - ScormArchiveFilename
      - string
      - The filename of the SCORM content file.

For example:

.. code:: json
	  
	  {
	  "NTIID": "tag:nextthought.com,2011-10:NTI-ScormContentInfo-1BC4CCEA431F1E6166205A94AC39402C174C67AF4E1CBEEB692E501C5D17F8AF_0087",
	  "ScormArchiveFilename": "myscorm_package.zip"
	  }
