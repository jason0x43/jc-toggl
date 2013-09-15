# -*- coding: utf-8 -*-

from jcalfred import Workflow, Item, JsonFile, LINE
from tzlocal import get_localzone
import datetime
import toggl
import logging
import os.path


LOG = logging.getLogger(__name__)
CACHE_LIFETIME = 300
LOCALTZ = get_localzone()
DATE_FORMAT = '%m/%d'


COMMANDS = {
    'since': 'List timers started since the given time',
    'start': 'Start a new timer'
}


def to_hours(delta, quantized=True):
    if isinstance(delta, datetime.timedelta):
        hours = delta.days * 24
        hours += delta.seconds / (60 * 60.0)
    else:
        hours = delta / (60*60.0)

    if quantized:
        # round to nearest quarter hour
        hours = round(hours * 4) / 4
        if hours == 0:
            hours = 0.25

    return hours


def to_approximate_time(delta, ago=False):
    postfix = ' ago' if ago else ''
    units = None

    if delta.days < 1:
        if delta.seconds > 60*60:
            units = 'hours'
            value = delta.seconds / (60*60.0)
        elif delta.seconds > 60:
            units = 'minutes'
            value = delta.seconds / 60.0
        else:
            units = 'seconds'
            value = delta.seconds
    elif delta.days == 1:
        return 'yesterday'
    else:
        units = 'days'
        value = delta.days

    return '{0:.0f} {1}{2}'.format(value, units, postfix)


def serialize_entries(entries):
    '''Serialize a list of TimeEntries into a list of dicts'''
    return [entry.data for entry in entries]


def deserialize_entries(dicts):
    '''Deserialize a list of dicts into a list of TimeEntries'''
    return [toggl.TimeEntry(d) for d in dicts]


def get_today():
    '''Return a datetime for midnight, today'''
    today = datetime.date.today()
    return datetime.datetime(today.year, today.month, today.day)


def get_start(query):
    today = get_today()
    query = query.lower()
    from dateutil.parser import parse

    if query == 'today':
        start = datetime.datetime.combine(today, datetime.time.min)

    elif query == 'yesterday':
        day = today - datetime.timedelta(days=1)
        start = datetime.datetime.combine(day, datetime.time.min)

    elif query == 'this week':
        # starting on Monday
        day = today - datetime.timedelta(days=today.weekday())
        start = datetime.datetime.combine(day, datetime.time.min)

    elif query[:3] in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'):
        start = parse(query)
        if start >= today:
            start -= datetime.timedelta(days=7)
    else:
        start = parse(query)

    return LOCALTZ.localize(start)


def get_end(query):
    if query in ('today', 'this week'):
        end = datetime.datetime.now()

    elif query == 'yesterday':
        today = datetime.date.today()
        end = datetime.datetime.combine(
            datetime.datetime(today.year, today.month, today.day),
            datetime.time.min
        )

    else:
        from dateutil.parser import parse
        today = get_today()

        if query[:3] in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'):
            end = parse(query)
            if end >= today:
                end -= datetime.timedelta(days=7)
            end += datetime.timedelta(days=1)
        else:
            end = parse(query)
            if end == today:
                end = datetime.datetime.now()
            else:
                end += datetime.timedelta(days=1)

    return LOCALTZ.localize(end)


class TogglWorkflow(Workflow):
    def __init__(self, *args, **kw):
        super(TogglWorkflow, self).__init__(*args, **kw)
        self.cache = JsonFile(os.path.join(self.cache_dir, 'cache.json'),
                              ignore_errors=True)
        if 'use_notifier' not in self.config:
            self.config['use_notifier'] = False

        if 'api_key' not in self.config:
            self.show_message('First things first...',
                              'Before you can use this workflow, you need '
                              'to set your Toggl API key. You can find your '
                              'key on the My Profile page at Toggl.com')

            answer, key = self.get_from_user('Set an API key', 'Toggl API key')
            if answer == 'Ok':
                self.config['api_key'] = key
                self.show_message('Good to go', 'Your key has been set!')

        toggl.api_key = self.config['api_key']
        if self.config['use_notifier']:
            self.run_script('tell application "TogglNotifier" to '
                            'set api key to "{0}"'.format(
                            self.config['api_key']))

    def tell_query(self, query, start=None, end=None):
        '''List entries that match a query.

        Note that an end time without a start time will be ignored.'''
        LOG.info('telling query with "{0}", start={1}, end={2}'.format(
                 query, start, end))
        if not start:
            end = None

        needs_refresh = False
        query = query.strip()

        if len(query) > 0 and query[0] == '/':
            LOG.info('manual refresh')
            query = query[1:]
            needs_refresh = True
        else:
            last_load_time = self.cache.get('time')
            if last_load_time:
                LOG.info('last load was %s', last_load_time)
                import time
                now = int(time.time())
                if now - last_load_time > CACHE_LIFETIME:
                    LOG.info('automatic refresh')
                    needs_refresh = True
            else:
                LOG.info('last load was null')
                needs_refresh = True

        if needs_refresh:
            LOG.info('getting data...')

            try:
                all_entries = toggl.TimeEntry.all()
            except Exception:
                LOG.exception('Error getting time entries')
                raise Exception('Problem talking to toggl.com')

            import time
            self.cache['time'] = int(time.time())
            self.cache['time_entries'] = serialize_entries(all_entries)
        else:
            all_entries = deserialize_entries(self.cache['time_entries'])

        if start:
            if end:
                all_entries = [e for e in all_entries if e.start_time < end
                               and e.stop_time > start]
            else:
                all_entries = [e for e in all_entries if e.stop_time > start]

        entries = {}

        for entry in all_entries:
            if entry.description not in entries:
                entries[entry.description] = {'entries': [],
                                              'seconds': 0}
            entries[entry.description]['entries'].append(entry)
            if entry.duration >= 0:
                duration = entry.duration
                if start and entry.start_time < start:
                    duration -= (start - entry.start_time).total_seconds()
                if end and entry.stop_time >= end:
                    duration -= (entry.stop_time - end - 1).total_seconds()
                entries[entry.description]['seconds'] += duration

        latest_entries = []

        for desc in entries:
            subentries = entries[desc]['entries']

            subentries = sorted(subentries, key=lambda e: e.start_time)
            entries[desc]['latest'] = subentries[-1]
            entries[desc]['first'] = subentries[0]
            latest_entries.append(subentries[-1])

        latest_entries = sorted(latest_entries, reverse=True,
                                key=lambda e: e.start_time)

        items = []

        if start:
            if len(latest_entries) > 0:
                total_time = sum(entries[e.description]['seconds'] for e in
                                 latest_entries)
                total_time = to_hours(total_time)

                if end:
                    item = Item('{0} hours on {1}'.format(
                                total_time,
                                start.date().strftime(DATE_FORMAT)),
                                subtitle=LINE)
                else:
                    item = Item('{0} hours since {1}'.format(
                                total_time,
                                start.date().strftime(DATE_FORMAT)),
                                subtitle=LINE)
            else:
                item = Item('Nothing to report')

            items.append(item)

        for entry in latest_entries:
            item = Item(entry.description, valid=True)
            now = LOCALTZ.localize(datetime.datetime.now())

            if entry.is_running:
                item.icon = 'running.png'
                started = entry.start_time
                delta = to_approximate_time(now - started)

                seconds = entries[entry.description]['seconds']
                total = ''
                if seconds > 0:
                    hours = to_hours(seconds)
                    total = ' ({0} hours total)'.format(hours)
                item.subtitle = 'Running for {0}{1}'.format(delta, total)
                item.arg = 'stop|{0}|{1}'.format(entry.id,
                                                 entry.description)
            else:
                seconds = entries[entry.description]['seconds']
                hours = to_hours(datetime.timedelta(seconds=seconds))

                if start:
                    item.subtitle = ('{0:.2f} hours'.format(hours))
                else:
                    stop = entry.stop_time
                    if stop:
                        delta = to_approximate_time(now - stop, ago=True)
                    else:
                        delta = 'recently'
                    since = entries[entry.description]['first'].start_time
                    since = since.strftime('%m/%d')
                    item.subtitle = ('{0:.2f} hours since {1}, '
                                     'stopped {2}'.format(hours, since, delta))

                item.arg = 'continue|{0}|{1}'.format(entry.id,
                                                     entry.description)

            items.append(item)

        if len(query.strip()) > 1:
            # there's a filter
            test = query[1:].strip()
            items = self.fuzzy_match_list(test, items,
                                          key=lambda t: t.title)

        if len(items) == 0:
            items.append(Item("Nothing found"))

        return items

    def tell_since(self, query):
        '''Return info about entries since a time

        A time may be:
            - a date
            - one of {'today', 'yesterday', 'this week'}
        '''
        query = query.strip()
        if not query:
            return [Item('Enter a start time', subtitle='This can be a time, '
                         'date, datetime, "yesterday", "tuesday", ...')]
        return self.tell_query('', start=get_start(query))

    def tell_on(self, query):
        '''Return info about entries over a span

        A span may be:
            - a single start date, which denotes a span from that date to now
            - one of {'today', 'yesterday', 'this week'}
            - a week day name
        '''
        query = query.strip()
        if not query:
            return [Item('Enter a date', subtitle='9/8, yesterday, monday, '
                         '...')]
        return self.tell_query('', start=get_start(query), end=get_end(query))

    def tell_start(self, query):
        LOG.info('adding a new time entry...')
        items = []
        desc = query.strip()
        if desc:
            items.append(Item('Creating timer "{0}"...'.format(desc),
                              arg='start|' + desc, valid=True))
        else:
            items.append(Item('Waiting for description...'))
        return items

    def tell_help(self, query):
        items = []
        items.append(Item("Use '/' to list existing timers",
                          subtitle='Type some text to filter the results'))
        items.append(Item("Use '//' to force a cache refresh",
                          subtitle='Data from Toggl is normally cached for '
                                   '{0} seconds'.format(CACHE_LIFETIME)))
        items.append(Item("Use '<' to list timers started since a time",
                          subtitle='9/2, 9/2/13, 2013-9-2T22:00-04:00, ...'))
        items.append(Item("Use '@' to list time spent on a particular date",
                          subtitle='9/2, 9/2/13, 2013-9-2T22:00-04:00, ...'))
        items.append(Item("Use '+' to start a new timer",
                          subtitle="Type a description after the '+'"))
        items.append(Item("Use '>' to access other commands",
                          subtitle='Enable menubar icon, go to toggl.com, '
                                   '...'))
        items.append(Item("Select an existing timer to toggle it"))
        return items

    def tell_cmd(self, query):
        LOG.info('telling cmd with "{0}"'.format(query))
        items = []
        items.append(Item('Open toggl.com',
                          arg='open|https://new.toggl.com/app',
                          subtitle='Open a browser tab for toggl.com',
                          valid=True))

        items.append(Item('Open the debug log',
                          arg='open|' + self.log_file,
                          subtitle='Open a browser tab for toggl.com',
                          valid=True))
        if self.config['use_notifier']:
            items.append(Item('Disable the menubar notifier',
                              subtitle='Exit and disable the menubar notifier',
                              arg='disable_notifier', valid=True))
        else:
            items.append(Item('Enable the menubar notifier',
                              subtitle='Start and enable the menubar notifier',
                              arg='enable_notifier', valid=True))

        if 'api_key' in self.config:
            items.append(Item('Forget your API key',
                              subtitle='Forget your stored API key, allowing '
                              'you to change it', arg='clear_key', valid=True))

        if len(query.strip()) > 1:
            # there's a filter
            items = self.fuzzy_match_list(query.strip(), items,
                                          key=lambda t: t.title)
        if len(items) == 0:
            items.append(Item("Invalid command"))

        return items

    def do_action(self, query):
        LOG.info('doing action with %s', query)
        cmd, sep, arg = query.partition('|')

        if cmd == 'start':
            entry = toggl.TimeEntry.start(arg)
            self.schedule_refresh()

            if self.config['use_notifier']:
                self.run_script('tell application "TogglNotifier" to set '
                                'active timer to "{0}|{1}"'.format(entry.id,
                                                                   arg))
            self.puts('Started {0}'.format(arg))

        elif cmd == 'continue':
            tid, sep, desc = arg.partition('|')
            entry = toggl.TimeEntry.start(desc)
            self.schedule_refresh()

            if self.config['use_notifier']:
                self.run_script('tell application "TogglNotifier" to set '
                                'active timer to "{0}|{1}"'.format(entry.id,
                                                                   desc))
            self.puts('Continued {0}'.format(desc))

        elif cmd == 'stop':
            tid, sep, desc = arg.partition('|')
            toggl.TimeEntry.stop(tid)
            self.schedule_refresh()

            if self.config['use_notifier']:
                self.run_script('tell application "TogglNotifier" to be '
                                'stopped')

            self.puts('Stopped {0}'.format(desc))

        elif cmd == 'enable_notifier':
            self.config['use_notifier'] = True
            self.run_script('tell application "TogglNotifier" to activate')
            self.run_script('tell application "TogglNotifier" to set api key '
                            'to "{0}"'.format(toggl.api_key))
            self.puts('Notifier enabled')

        elif cmd == 'disable_notifier':
            self.config['use_notifier'] = False
            self.run_script('tell application "TogglNotifier" to quit')
            self.puts('Notifier disabled')

        elif cmd == 'clear_key':
            del self.config['api_key']
            self.run_script('tell application "TogglNotifier" to quit')
            self.puts('Cleared API key')

        elif cmd == 'open':
            from subprocess import call
            call(['open', arg])

        else:
            self.puts('Unknown command "{0}"'.format(cmd))

    def schedule_refresh(self):
        '''Force a refresh next time Toggl is queried'''
        self.cache['time'] = 0
