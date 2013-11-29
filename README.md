[Alfred 2][alfred] Workflow for interacting with [Toggl][toggl]
======================================================

<p align="center">
<img alt="Screenshot" src="https://dl.dropboxusercontent.com/s/3h3eb66f3gcfxbr/jc-toggl_screenshot.png" />
</p>

<p align="center">
  <a href="https://dl.dropboxusercontent.com/s/ff7hsrn1og72xey/jc-toggl.alfredworkflow"><img src="http://i.imgur.com/E8I5TfU.png" alt="Download"></a>
</p>

This workflow lets you interact with your account on Toggl. It provides a
fairly basic level of access; you can view time entries for the past 9 days
(the Toggl API default), start/continue and stop entries, and generate some
basic in-Alfred reports. At the moment, this fits my Toggl usage style; no
projects, tasks, or clients, just time entries.

Installation
------------

The easiest way to install the workflow is to download the
[prepackaged workflow][pkg].  Double-click on the downloaded file, or drag
it into the Alfred Workflows window, and Alfred should install it.

Usage
-----

There are a number of commands:

* `toggl/` - List your time entries in descending order by last stop time. Only
  entries for the past 9 days are included. Entries with the same description are
  collapsed into a single Alfred item.
* `toggl#` - List time entries on a specific date. This can be a date like
  8/24, "today", "yesterday", or a weekday name.
* `toggl<` - List time entries from a specific date or date+time until the
  current time.
* `toggl+` - Create an entry with a description.
* `toggl>` - List miscellaneous commands, like opening toggl.com.
* `toggl.` - Quickly stop the currently active timer
* `toggl?` - Get help

When you run the workflow for the first time you will need to input your Toggl
API key. You can find it in your account settings on toggle.com.

Notifier
--------

This packaged version of this workflow also includes a [menu bar notifier
app][notifier] that I wrote. Alfred is great for interacting with Toggl, but I
kept forgetting to stop my timers. The notifier sits in the menu bar and checks
Toggl every 3 minutes to see if you have an active timer. If you do, it turns
red; otherwise it's black. The notifier also responds to notifications from the
workflow, so if you start or stop a timer via the workflow the timer will
change colors immediately.

<p align="center">
<img alt="Screenshot" src="https://dl.dropboxusercontent.com/s/sv3loafccs3iyoc/jc-toggl_notifier_screenshot.png" />
</p>

When a timer is active, clicking on the notifier will show the timer's
description, and the time entry will show up with a highlighted icon in the
Alfred listing. Clicking on the timer's description in the notifier menu will
stop the timer.

You can activate or deactivate the timer with the `toggl>` command.

Requirements
------------

* A Toggl account
* Python 2.7 (standard on Lion and Mountain Lion)
* Some python libraries:
  * requests
  * tzlocal
  * dateutil
  * My [jcalfred][jcalfred] python library

Everything is included in the packaged workflow.

Credits
-------

The workflow was my idea, but it would of course be pretty useless without the
awesome service that is [Toggl][toggl]. It also wouldn't look as snazzy (well,
as snazzy as an Alfred workflow can) without the icon from Toggl's desktop
application. 

[pkg]: https://dl.dropboxusercontent.com/s/ff7hsrn1og72xey/jc-toggl.alfredworkflow
[alfred]: http://www.alfredapp.com
[toggl]: http://www.toggl.com
[jcalfred]: https://github.com/jason0x43/jcalfred
[notifier]: https://github.com/jason0x43/jc-toggl-notifier
