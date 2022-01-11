=====================
Course Archive Format
=====================

This document describes the NextThought Course Archive ("course
archives", or more simply, "archive") format. An archive is a ``ZIP`` file
containing the structure and assets of the course. The archive format
is designed to be a full representation of course content. It can be
used to back up course content or as a custom intermediate format to
move course content to another system.

Course archives can be extracted from the NextThought LMS using the
`"Export Course" <https://help.nextthought.com/hc/en-us/articles/4415136825108>`_ functionality.

The archive contains a number of structured files in ``json`` and,
``XML`` format (identified by the file extension and contents) as well
as folders containing user-provided assets (where those assets are images, documents, PDFs, etc.).

Common Object Properties
========================

Many of the ``json`` and ``XML`` documents in the archive represent
*objects* or collections of *objects*. The objects have a set of
common properties useful for identifying the type of object, as well
as other metadata about the object. Common properties include:

``Class`` - A type identifier for the object

``MimeType`` - An RFC-6838 MIME type identifying the type of object

``Creator`` - The creator of the object identified by their unique
Username.

``CreatedTime`` - The time the object was created, represented as the time
in seconds since the epoch (a floating point number)

``Last Modified`` - The most recent modification time of the object, represented as the time
in seconds since the epoch (a floating point number)

``NTIID`` - A global, unique identifier for the object

``OID`` - An internal, unique identifier for the object

Publication
-----------

Certain object's track publication state. While publication semantics
may vary based on the type of object, publication state is most
commonly used to control the visibility of the object. Objects
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

A list of ``AcclaimBadge`` objects that are awarded to learners upon
successful completion of the course. These objects model
``BadgeTemplates`` linked via the Credly/Acclaim integration.

See `credly documentation
<https://www.credly.com/docs/badge_templates>`_ for more information.

assessment_index.json
=====================

This file is deprecated in favor of :ref:`evaluation_index.json`.

assets (folder)
===============

A folder of user-uploaded assets that are used within lessons and readings. This folder is exposed to course admins, and may contain sub-directories or unused assets.

assignment_policies.json
========================

Assignment policy information that controls how the included
evaluations (see :ref:`evaluation_index.json`) behave in the
system. In general values here are *merged on top* of the corresponding
values on the assignment to override behavior the assignment related settings.

This structure provides a mapping from evaluation NTIID to a
dictionary of settings with the following possible keys.

.. list-table:: Fields
   :header-rows: 1

   * - Name
     - Type
     - Description
   * - auto_grade
     - Dict
     - See below
   * - available_for_submission_beginning
     - String
     - The ISO-8601 datetime string controlling when submissions begin being accepted for the assignment.
   * - available_for_submission_ending
     - String
     - The ISO-8601 datetime string controlling when submissions are no longer accepted for the assignment.
   * - completion_passing_percent
     - Number [0, 1]
     - The percentage of questions the learner must get correct for
       the assignment to be considered completed successfully
       e.g. passed. For example a value of ``0.80`` would result in
       successful completion if a learner gets at least 8 of 10
       questions correct.
   * - disclosure
     - 'never', 'always', 'termination', 'submission'
     - Only applicable to polls and surveys, controls when users
       should be able to see the results associated with the
       pull/survey.
   * - locked
     - Bool
     - Deprecated
   * - max_submissions
     - Number
     - The maximum number of submission attempts this assignment
       allows. Assignments with a ``max_submissions > 2`` is said to be a
       `multiattempt assignment <https://help.nextthought.com/hc/en-us/articles/360049442252-Assignment-Advanced-Settings>`_.
   * - maximum_time_allowed
     - Number
     - The number of seconds a learner has to complete the assignment
       after starting it. A `maximum_time_allowed > 0` is indicative of a timed assignment.
   * - submission_buffer
     - Number
     - The number of seconds of grace period beyond
       ``available_for_submission_ending`` that submissions will still
       be allowed. See `Late Submissions
       <https://help.nextthought.com/hc/en-us/articles/360049442252-Assignment-Advanced-Settings>`_
     
.. list-table:: auto_grade Fields
   :header-rows: 1

   * - Name
     - Type
     - Description
   * - disable
     - Bool
     - Is auto grading disabled
   * - total_points
     - Number
     - The total number of points this assignment is worth.
 

.. _evaluation_index.json:
	     
evaluation_index.json
=====================

Lists all the evaluation items in the course. The ``Items`` array contains zero or more of the following:

Question
--------

.. list-table:: Fields
	:header-rows: 1

	* - Name
	  - Type
	  - Description
	* - MimeType
	  - string
	  - "application/vnd.nextthought.naquestion", "application/vnd.nextthought.question"
	* - content
	  - string
	  - The prompt for the question (May contain HTML).
	* - parts
	  - array
	  - the list of inputs,limited to 1 input per question.


Poll
----

Have the same fields as questions. Polls aggregate the response of every learner, rather than test one learner.


.. list-table:: Fields
	:header-rows: 1

	* - Name
	  - Type
	  - Description
	* - MimeType
	  - string
	  - "application/vnd.nextthought.napoll"

Question Set
------------

A collection of questions, used for learners to self test their own knowledge.

.. list-table:: Fields
	:header-rows: 1

	* - Name
	  - Type
	  - Description
	* - MimeType
	  - string
	  - "application/vnd.nextthought.questionset"
	* - questions
	  - array
	  - the list of questions in the question set

Survey
------

A collection of polls, used to aggregate results from all learners.
Has the same fields as a question set plus:

.. list-table:: Fields
	:header-rows: 1

	* - Name
	  - Type
	  - Description
	* - MimeType
	  - string
	  - "application/vnd.nextthought.nasurvey"
	* - title
	  - string
	  - The name of the survey
	* - description
	  - string
	  - Summary of the purpose of the survey
	* - contents
	  - string
	  - An optional RST string providing rich content to the survey, with ``napollref`` directives indicating the location of the polls found in the ``questions``property.


Assignment
----------

A wrapper around a question set, provides a score contributing to the learner's course grade.

.. list-table:: Fields
	:header-rows: 1

	* - Name
	  - Type
	  - Description
	* - MimeType
	  - string
	  - "application/vnd.nextthought.assessment.assignment"
	* - total_points
	  - number
	  - how many points the assignment is worth
	* - parts
	  - array
	  - a list of assignment parts containing the question sets

Documents (folder)
==================

The default folder for storing user-uploaded documents used as lesson content. This folder is exposed to course admins. It may contain other documents, and some documents may have been moved to other directories. 

Images (folder)
===============

The default folder for storing user-uploaded images used as cover images for lesson content. This folder is exposed to the user. It may contain other documents, and some images may have been moved to other directories. 

.. _lessons:

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
	  - A color (in `hex format
            <https://en.wikipedia.org/wiki/Web_colors#Hex_triplet>`_)assigned
            to the group to help create visual contrast.

Lesson Asset
------------

The overview group's Items will be zero or more lesson assets.

Lesson assets are broken into two categories references and assets.
References point to other assets in the course.

Assessment Reference
````````````````````

:MimeType: "application/vnd.nextthought.questionsetref"
:Target-NTIID: Points to a QuestionSet in the ``evaluation_index.json``

Assignment Reference
````````````````````

:MimeType: "application/vnd.nextthought.assignmentref"
:Target-NTIID: Points to an Assignment in the ``evaluation_index.json``


Discussion Reference
````````````````````

:MimeType: "application/vnd.nextthought.discussionref"
:Target-NTIID: Points to a Discussion in one of the ``json`` files in the ``Discussions`` folder.

Related Work Reference
``````````````````````

Point to either a reading in the course, an uploaded document, or an external URL.

Readings can be found in ``content_packages.json``
Documents can be round in the ``Documents`` folder

:MimeType: "application/vnd.nextthought.relatedworkref"
:targetMimeType: Tells type of content the ref points to. Either "application/vnd.nextthought.content", "application/vnd.nextthought.externallink", or the MimeType of the document it points to.
:href: Either the external URL, or internal NTIID pointing to the resource.

SCORM Content Reference
```````````````````````

:MimeType: "application/vnd.nextthought.scormcontentref"
:Target-NTIID: Points to a folder in the ``ScormContent`` folder.

Survey Reference
````````````````

:MimeType: "application/vnd.nextthought.surveyref"
:Target-NTIID: Points to a Survey in the ``evaluation_index.json``

LTI Tool Asset
``````````````

:MimeType: "application/vnd.nextthought.ims.consumer.configuredtool"
:title: Name of the tool
:description: Summary of the tool
:launch_url: the URL to launch the LTI tool

Video Asset
```````````

A :ref:`Video Object`

Webinar Asset
`````````````

A reference to a `Goto Webinar <https://www.goto.com/webinar>`_ webinar.

:MimeType: "application/vnd.nextthought.webinar"
:description: summary of the webinar
:Links: an array of link object, one will have a rel of ``JoinWebinar`` that href will launch the webinar
:webinarID: the id of the webinar
:webinarKey: the GotoWebinar key
:organizerKey: the GotoWebinar account





bundle_dc_metadata.xml
======================

Incomplete `Dublin Core metadata <https://dublincore.org>`_ for the
course. See :ref:`course_info.json` for more complete catalog information.

bundle_meta_info.json
=====================

Additional external content referenced by the course. This is only
applicable to a subset of legacy enterprise courses.

completable_item_default_required.json
======================================

A list of content types, specified by ``MimeType`` that this course
requires completion of by default.

completable_item_required.json
==============================

A list of required/optional overrides for content in the
course. 

.. list-table:: Interesting Fields
	:header-rows: 1

	* - Name
	  - Type
	  - Description
	* - optional
	  - String[]
	  - List of NTIIDs for course objects that are explicitly marked as optional.
	* - required
	  - String[]
	  - List of NTIIDs for course objects that are explicitly marked as required.


completion_policies.json
========================

The aggregate completion policy for the course. The ``context_policy``
field is an ``AggregateCompletionPolicy`` modeling the aggregate completion requirement for
the course as well as whether or not a certificate is awarded on completion.

.. list-table:: AggregateCompletionPolicy
	:header-rows: 1

	* - Name
	  - Type
	  - Description
	* - percentage
	  - Number
	  - The percentage of required items a learner must
            *successfully* complete to complete the course.
	* - offers_completion_certificate
	  - Bool
	  - If true, when successfully completed learners are awarded
            a certificate.

content_packages.json
=====================

A list of all the ContentPackages in the course. ContentPackages contain one and only one reading.

.. list-table:: Fields
	:header-rows: 1

	* - Name
	  - Type
	  - Description
	* - MimeType
	  - string
	  - "application/vnd.nextthought.renderablecontentpackage"
	* - title
	  - string
	  - the name of the content package
	* - content
	  - string
	  - A base 64 encoded, gzipped, ReSTructured text

To decode the content, base 64 decode it and unzip the contents. `Online tools <https://codebeautify.org/gzip-decompress-online>`_ exist to help with that process.

RST Primer
----------

`RST <https://docutils.sourceforge.io/rst.html>`_ is a markup format that adds additional semantic information.

One powerful feature of RST, is the ability to add `custom directives. <https://docutils.sourceforge.io/docs/ref/rst/directives.html>`_
The reading content utilizes custom directives for NextThought specific content blocks.

Code Block
``````````

:Directive Name: ``code-block``
:Arguments: the language
:Body: code block

Photo
`````

:Directive Name: ``course-figure``
:Arguments: the URL for the image, points to a file in the ``assets`` folder

Video
`````

:Directive Name: ``ntivideoref``
:Arguments: NTIID of the video, in the ``user_assets.json`` file

Iframe
```````

:Directive Name: ``nti:embedwidget``
:Arguments: src of the iframe
:Options:
	:width: how wide the iframe should be
	:height: how tall the iframe should be
	:...others: other options are passed as attributes to the iframe tag

Sidebar
```````

:Directive Name: ``sidebar``
:Body: the contents of the sidebar




.. _course_info.json:

course_info.json
================

Metadata and presentation information used to represent this course in
the course catalog.

.. list-table:: Fields
	:header-rows: 1

	* - Name
	  - Type
	  - Description
	* - additionalProperties
	  - Deprecated
	  - Deprecated
	* - awardableCredits
	  - CourseAwardableCredit[]
	  - Credit that will be awarded to a user's transcript on successful completion.
	* - credit
	  - Deprecated
	  - Deprecated
	* - description
	  - String
	  - An optional plain text description of the course.
	* - duration
	  - Deprecated
	  - Deprecated
	* - endDate
	  - String
	  - The anticipated datetime this course will end in ISO-8601 timestamp format.
	* - id
	  - String
	  - The course identifier given to this course.
	* - instructors
	  - Instructor[]
	  - The published instructors for this course.
	* - isPreview
	  - Bool
	  - When true, this course is not avaialble to learners.
	* - is_anonymously_but_not_publicly_accessible
	  - Deprecated
	  - Deprecated
	* - is_non_public
	  - Bool
	  - When true, the course is not listed in the catalog for enrollment.
	* - prerequisites
	  - Deprecated
	  - Deprecated
	* - richDescription
	  - String
	  - An optional rich text (html) description of the course.
	* - schedule
	  - Deprecated
	  - Deprecated
	* - school
	  - Deprecated
	  - Deprecated
	* - startDate
	  - String
	  - The anticipated datetime this course will begin in ISO-8601 timestamp format.
	* - tags
	  - String[]
	  - A list of tags associated with this course.
	* - title
	  - String
	  - The title for this course.
	* - video
	  - URL
	  - The embed url of this course's promotional video.

CourseAwardableCredit
---------------------

``CourseAwardableCredit`` defines the type and amount of credit a user
will be awarded upon successful completion of the course.

.. list-table:: Interesting Fields
	:header-rows: 1

	* - Name
	  - Type
	  - Description
	* - amount
	  - Number
	  - The amount of credit to be awarded.
	* - credit_definition
	  - CreditDefinition
	  - The type of credit to be awarded including type, units, and precision.

Instructor
----------

The ``instructors`` field defines the set of instructors that show up
when viewing course information in the catalog. These instructors are
distinct from users actually granted elevated permissions in the
course (see role_info.json).

.. list-table:: Fields
	:header-rows: 1

	* - Name
	  - Type
	  - Description
	* - biography
	  - Deprecated
	  - Deprecated
	* - email
	  - String
	  - The public email for the instructor.
	* - jobTitle
	  - String
	  - The instructors job title. For example: Chief Training Officer
	* - name
	  - String
	  - The display name for this instructor.
	* - suffix
	  - String
	  - The isntructors suffix. For example: PhD.
	* - title
	  - Deprecated
	  - Deprecated
	* - userid
	  - Deprecated
	  - Deprecated
	* - username
	  - String
	  - The optional NextThought username for the user this
            instructor item is associated with.


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
     - String
     - An ISO-8601 datetime string for the start of when the contents
       of this lesson are anticipated to be covered. This is purely
       a display construct. See :ref:`outlinenodepublication` for
       details on node visibility
   * - AvailableEnding
     - String
     - An ISO-8601 datetime string for the end of when the contents
       of this lesson are anticipated to be covered. This is purely
       a display construct. See :ref:`outlinenodepublication` for
       details on node visibility
   * - title
     - String
     - The display name for the lesson/unit in the outline
   * - Items
     - CourseOutlineNode[]
     - Child nodes of this nod


Additionally ``CourseOutlineContentNode`` objects add a ``src`` field
that references the ``LessonOverview`` json file from the ``Lessons`` folder.

.. list-table:: Fields
   :header-rows: 1

   * - Field Name
     - Type
     - Description
   * - src
     - String
     - The filename of the lesson definition file found in the :ref:`lessons`.


.. note:: In practice the CourseOutline is typically 2 levels, the
          first level maps to ``Units`` and the second level maps to
          ``Lessons``. Some legacy courses may have ``CourseOutlineNode``
          objects that nest more than 2 levels.

.. _outlinenodepublication:

Course Outline Node Publication
-------------------------------

The publication properties on course outline nodes drive the
visibility of those outline nodes to learners. Only published outline
nodes are visible in the Course's lesson structure for learners. All
nodes are visible to instructors and editors when in editing mode.

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

dc_metadata.xml
===============

Incomplete `Dublin Core metadata <https://dublincore.org>`_ for the
course. See :ref:`course_info.json` for more complete catalog
information.

ims_configured_tools.json
=========================

A mapping of configured LTI tools in the course keyed by NTIID. Each
LTI tools is represented by ``ConfguredTool`` which itself contains a ``PersistentToolConfig``

.. list-table:: ConfiguredTool
      :header-rows: 1

      * - Field Name
	- Type
	- Description
      * - config
	- PersistentToolConfig
	- See below.
      * - config_xml
	- String
	- The xml representation of the LTI configuration
      * - consumer_key
	- String
	- The consumer key associated with this LTI tool
      * - deleted
	- Bool
	- Was this tool deleted. Deleted tools don't show in the UI.
      * - secret
	- String
	- The consumer secret associated with this LTI tool


.. list-table:: PersistentToolConfig
      :header-rows: 1

      * - Field Name
	- Type
	- Description
      * - title
	- String
	- A displayable title of the tool
      * - description
	- String
	- A plain text description of the tool
      * - launch_url
	- URL
	- A fully qualified url that can be used to launch the tool
      * - secure_launch_url
	- URL
	- A fully qualified https url that can be used to launch the tool

meta_info.json
==============

A ``json`` file containing metadata about the export archive.
The json object has the following fields:

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
     - ``application/vnd.nextthought.courses.courseinstance``

For example:

.. code:: json

   {
	"CreatedTime": "2021-12-22T17:06:26Z",
	"Creator": "admin1",
	"ExportHash": "49115848444338989_1640192784.88",
	"MimeType": "application/vnd.nextthought.courses.courseinstance"
   }

presentation-assets (folder)
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
     - Used in card presentation of courses
   * - background.png
     - 3000px X 2000px
     - Used as the background image when on a course, has a Gaussian blur to handle
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

.. _Video Object:

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
      - the URL of the .vtt file (`specification <https://www.w3.org/TR/webvtt1/>`_)

.. note:: Need to include documentation of the supported services, types, and sources

.. note:: Document inline transcript content format


vendor_info.json
================

Additional custom vendor information specific to the NextThought
Platform. This data structure is deprecated.

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
      - The filename of the SCORM original content file.

For example:

.. code:: json

	  {
	  "NTIID": "tag:nextthought.com,2011-10:NTI-ScormContentInfo-1BC4CCEA431F1E6166205A94AC39402C174C67AF4E1CBEEB692E501C5D17F8AF_0087",
	  "ScormArchiveFilename": "myscorm_package.zip"
	  }

..  LocalWords:  PDFs MimeType CreatedTime NTIID OID isPublished Bool
     - Child nodes of this node..  LocalWords:  publishLastModified
     - Child nodes of this node..  LocalWords:  publishBeginning RST
     - Child nodes of this node..  LocalWords:  DateTime datetime xml
     - Child nodes of this node..  LocalWords:  publishEnding href px
     - Child nodes of this node..  LocalWords:  multiattempt SCORM UI
     - Child nodes of this node..  LocalWords:  napollref accentColor
     - Child nodes of this node..  LocalWords:  QuestionSet LTI nti
     - Child nodes of this node..  LocalWords:  targetMimeType NTIIDs
     - Child nodes of this node..  LocalWords:  ScormContent gzipped
     - Child nodes of this node..  LocalWords:  completable Iframe KE
     - Child nodes of this node..  LocalWords:  AggregateCompletionPolicy
     - Child nodes of this node..  LocalWords:  ContentPackages src
     - Child nodes of this node..  LocalWords:  ReSTructured iframe
     - Child nodes of this node..  LocalWords:  ntivideoref endDate
     - Child nodes of this node..  LocalWords:  embedwidget isPreview
     - Child nodes of this node..  LocalWords:  additionalProperties
     - Child nodes of this node..  LocalWords:  awardableCredits html
     - Child nodes of this node..  LocalWords:  CourseAwardableCredit
     - Child nodes of this node..  LocalWords:  avaialble startDate
     - Child nodes of this node..  LocalWords:  richDescription url
     - Child nodes of this node..  LocalWords:  CreditDefinition ims
     - Child nodes of this node..  LocalWords:  jobTitle isntructors
     - Child nodes of this node..  LocalWords:  userid LessonOverview
     - Child nodes of this node..  LocalWords:  CourseOutlineContentNode
     - Child nodes of this node..  LocalWords:  AvailableBeginning zn
     - Child nodes of this node..  LocalWords:  outlinenodepublication
     - Child nodes of this node..  LocalWords:  AvailableEnding png
     - Child nodes of this node..  LocalWords:  CourseOutlineNode aqz
     - Child nodes of this node..  LocalWords:  CourseOutline webapp
     - Child nodes of this node..  LocalWords:  autointerface kaltura
     - Child nodes of this node..  LocalWords:  ExportHash vimeo bpKQ
     - Child nodes of this node..  LocalWords:  contentpackage wistia
     - Child nodes of this node..  LocalWords:  VideoSource youtube
     - Child nodes of this node..  LocalWords:  lqfi lang srcjsonp
     - Child nodes of this node..  LocalWords:  vtt nextthought CCEA
     - Child nodes of this node..  LocalWords:  ScormContentInfo
     - Child nodes of this node..  LocalWords:  CBEEB scorm myscorm
     - Child nodes of this node..  LocalWords:  ScormArchiveFilename
     - Child nodes of this node..  LocalWords:  ConfiguredTool config
     - Child nodes of this node..  LocalWords:  PersistentToolConfig
     - Child nodes of this node..  LocalWords:  https
