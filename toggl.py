from dateutil.parser import parse
from tzlocal import get_localzone
import requests
import logging
import json


TOGGL_API = 'https://www.toggl.com/api/v8'
REPORTS_API = 'https://www.toggl.com/reports/api/v2'
LOCALTZ = get_localzone()
LOG = logging.getLogger(__name__)

api_key = None
workspace_id = 425197


def api_get(path, params=None):
    url = TOGGL_API + path
    return requests.get(url, auth=(api_key, 'api_token'), params=params,
                        headers={'content-type': 'application/json'})


def report_get(path, params=None):
    url = REPORTS_API + path
    if not params:
        params = {}
    params['user_agent'] = 'jc-toggl'
    params['workspace_id'] = workspace_id
    return requests.get(url, auth=(api_key, 'api_token'), params=params,
                        headers={'content-type': 'application/json'})


def api_post(path, data=None):
    url = TOGGL_API + path
    return requests.post(url, auth=(api_key, 'api_token'), data=data,
                         headers={'content-type': 'application/json'})


def api_put(path, data=None):
    url = TOGGL_API + path
    return requests.put(url, auth=(api_key, 'api_token'), data=data,
                        headers={'content-type': 'application/json'})


def api_delete(path):
    url = TOGGL_API + path
    return requests.put(url, auth=(api_key, 'api_token'),
                        headers={'content-type': 'application/json'})


class JsonObject(object):
    def __init__(self, data):
        self._data = data
        self._cache = {}

    @property
    def data(self):
        return self._data

    def _get_value(self, field_name):
        return self._data.get(field_name)

    def _get_timestamp(self, field_name):
        val = self._data.get(field_name)
        if val:
            return parse(val).astimezone(LOCALTZ)
        else:
            return val


class TimeEntry(JsonObject):
    @classmethod
    def all(cls):
        '''Retrieve all time entries'''
        resp = api_get('/time_entries')
        #resp = report_get('/details')
        #print json.dumps(resp.json(), indent=2)
        LOG.debug('response: %s', resp)
        return [TimeEntry(e) for e in resp.json()]

    @classmethod
    def retrieve(cls, id):
        '''Retrieve a specific time entry'''
        resp = api_get('/time_entries/{0}'.format(id))
        return TimeEntry(resp.json()['data'])

    @classmethod
    def start(cls, description, project_id=None):
        '''Start a new time entry'''
        data = {'time_entry': {'description': description}}
        if project_id:
            data['time_entry']['pid'] = project_id
        data = json.dumps(data)
        resp = api_post('/time_entries/start', data=data)
        if resp.status_code != 200:
            raise Exception('Unable to start timer: {0}'.format(resp))
        return TimeEntry(resp.json()['data'])

    @classmethod
    def stop(cls, id=None):
        '''Stop a the time entry with the given id'''
        if not id:
            entries = cls.all()
            for entry in entries:
                if entry.is_running:
                    id = entry.id
                    LOG.debug('running entry is {0}'.format(entry))
                    break
        if not id:
            return None
        resp = api_put('/time_entries/{0}/stop'.format(id))
        return resp.json()['data']

    @property
    def id(self):
        return self._get_value('id')

    @property
    def workspace(self):
        return self._workspace

    @property
    def account(self):
        return self._workspace.account

    @property
    def description(self):
        return self._get_value('description')

    @property
    def start_time(self):
        return self._get_timestamp('start')

    @property
    def stop_time(self):
        st = self._get_timestamp('stop')
        if st:
            return st

        import datetime
        delta = datetime.timedelta(seconds=self.duration)
        return self.start_time + delta

    @property
    def duration(self):
        return self._get_value('duration')

    @property
    def tags(self):
        return self._get_value('tags')

    @property
    def pid(self):
        return self._get_value('pid')

    @property
    def is_running(self):
        return self.duration < 0

    def restart(self):
        '''Start a new time entry with the same info as this one'''
        return TimeEntry.start(self.description, pid=self.pid)

    def __str__(self):
        return ('{{TimeEntry: description={0}, running={1}, start={2}, '
                'stop={3}}}'.format(self.description, self.is_running,
                                    self.start_time, self.stop_time))

    def __repr__(self):
        return self.__str__()


class Project(JsonObject):
    @classmethod
    def retrieve(cls, id):
        '''Retrieve a specific project'''
        resp = api_get('/projects/{0}'.format(id))
        return Project(resp.json()['data'])

    @property
    def name(self):
        return self._get_value('name')

    @property
    def id(self):
        return self._get_value('id')

    @property
    def wid(self):
        return self._get_value('wid')

    def __str__(self):
        return '{{Project: name={0}}}'.format(self.name)

    def __repr__(self):
        return self.__str__()


class Workspace(JsonObject):
    @classmethod
    def all(cls):
        '''Retrieve all user workspaces'''
        resp = api_get('/workspaces')
        return [Workspace(w) for w in resp.json()]

    @classmethod
    def retrieve(cls, id):
        '''Retrieve a specific workspace'''
        resp = api_get('/workspaces/{0}'.format(id))
        return Workspace(resp.json()['data'])

    @property
    def name(self):
        return self._get_value('name')

    @property
    def id(self):
        return self._get_value('id')

    @property
    def at(self):
        return self._get_timestamp('at')

    @property
    def projects(self):
        '''Return all workspace projects'''
        resp = api_get('/workspaces/{0}/projects'.format(self.id))
        return [Project(p) for p in resp.json()]

    def get_report(self, kind='weekly', since=None, until=None,
                   project_ids=[], description=None):
        '''Return a particular report'''
        if kind not in ('weekly', 'detailed', 'summary'):
            raise Exception('Invalid report type {0}'.format(kind))

        if since and not isinstance(since, str):
            raise Exception('since must be a string')
        if until and not isinstance(until, str):
            raise Exception('until must be a string')

        if project_ids and not isinstance(project_ids, (list, tuple)):
            raise Exception('non-iterable value for project_ids')

        data = {
            'user_agent': 'jc-toggl Alfred workflow',
            'workspace_id': self.id,
            'rounding': 'on',
            'display_hours': 'decimal'
        }

        if since:
            data['since'] = since
        if until:
            data['until'] = until
        if project_ids:
            data['project_ids'] = project_ids
        if description:
            data['description'] = description

        resp = report_get('{0}/{1}'.format(REPORTS_API, kind), params=data)
        return resp.json()

    def __str__(self):
        return '{{Workspace: id={0}, name={1}, at={2}}}'.format(self.id,
               self.name, self.at)

    def __repr__(self):
        return self.__str__()


class Account(JsonObject):
    @classmethod
    def retrieve(cls):
        resp = api_get('/me')
        Account(resp.json()['data'])

    @property
    def email(self):
        '''Return the user's email address'''
        return self._get_value('email')

    @property
    def at(self):
        '''Return the last time the accout was modified'''
        return self._get_timestamp('at')

    @property
    def timezone(self):
        '''Return the user's time zone'''
        return self._get_value('timezone')

if __name__ == '__main__':
    from sys import argv
    api_key = argv[1]
    workspace = Workspace.all()[0]
    workspace_id = workspace.id
    #print TimeEntry.all()
    TimeEntry.all()
