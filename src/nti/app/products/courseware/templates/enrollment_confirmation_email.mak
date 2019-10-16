Dear ${informal_username},

Thank you for signing up for "${course.Title}".

You are about to embark on a one-of-a-kind learning experience through
${brand}. More importantly, you are joining a true learning community
built to connect, engage, and inspire all who wish to learn.

% if not course_archived and not course_preview:
The course is currently in progress. You are welcome to join our
learning community and to experience the lectures and discussions on ${brand}.
% endif

% if course_archived:
Although the course has already formally concluded, you still have access to
all course materials. These materials will be available to you indefinitely,
as long as you are enrolled in the course. Please note, however, that this
course is no longer monitored by the professor. You are welcome to join our
learning community and to experience the lectures and discussions on ${brand}.
% endif

Feel free to spread the word around about the course by forwarding
this email or sharing about it through social media. Encourage your
friends to join, add them as a friend, and then form a study group on
the platform.

I look forward to seeing you in our community!

All the Best,

${course.InstructorsSignature}

If you feel this email was sent in error, or this account was created
without your consent, you may email ${support_email}.
