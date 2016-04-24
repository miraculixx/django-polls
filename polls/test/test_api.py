from datetime import timedelta
import json
import logging
import uuid

from django.contrib.auth.models import Permission, User
from django.utils import timezone
from tastypie.test import ResourceTestCase
from tastypie.utils import make_naive

from polls.models import Poll, Choice


logger = logging.getLogger(__name__)
# or '/polls/api/v1' in the case when we don't set 'urls' attribute
URL = '/api/v1'


class PollsApiTest(ResourceTestCase):
    urls = 'polls.urls'

    def setUp(self):
        super(PollsApiTest, self).setUp()
        self.username = 'test'
        self.password = 'password'
        self.user = User.objects.create_user(
            self.username, 'user@nomail.com', self.password)
        self.admin = User.objects.create_user(
            'admin', 'admin@nomail.com', self.password)
        # user can't add/change/delete poll model without permissions
        permissions = (Permission.objects.get(codename=p)
                       for p in ['add_poll', 'change_poll', 'delete_poll',
                                 'add_choice', 'change_choice', 'delete_choice'])
        self.admin.user_permissions.add(*permissions)

    def tearDown(self):
        self.api_client.client.logout()

    def getURL(self, resource, id=None):
        if id:
            return "%s/%s/%s/" % (URL, resource, id)
        return "%s/%s/" % (URL, resource)

    def get_credentials(self, admin=False):
        if admin:
            username = self.admin.username
        else:
            username = self.user.username
        return self.create_basic(username=username, password=self.password)

    def test_create_poll(self):
        self.assertTrue(self.admin.has_perm('polls.add_poll'))
        poll_data = self.poll_data()
        resp = self.create_poll(poll_data)
        self.assertHttpCreated(resp)
        pk = Poll.objects.order_by('-id')[0].pk
        resp = self.api_client.get(
            self.getURL('poll'), authentication=self.get_credentials(admin=True))
        # logger.debug(resp)
        self.assertValidJSONResponse(resp)
        deserialized = self.deserialize(resp)['objects']
        self.assertEqual(deserialized[0], {
            u'id': pk,
            u'choices': [],
            u'description': poll_data['description'],
            u'question': poll_data['question'],
            u'reference': deserialized[0]['reference'],
            u'is_anonymous': poll_data['is_anonymous'],
            u'is_closed': poll_data['is_closed'],
            u'is_multiple': poll_data['is_multiple'],
            u'resource_uri': deserialized[0]['resource_uri'],
            u'start_votes': poll_data['start_votes'],
            u'end_votes': poll_data['end_votes'],
            u'allow_multi_votes': False,
        })
        # check that 'reference' is correct uuid string
        try:
            uuid.UUID('{' + deserialized[0]['reference'] + '}')
        except ValueError:
            self.fail('badly formed UUID string')

    def test_create_poll_unauthenticated(self):
        resp = self.api_client.post(self.getURL('poll'), format='json')
        self.assertHttpUnauthorized(resp)

    def test_put_poll(self):
        poll_data = self.poll_data()
        poll_data['is_anonymous'] = True
        resp = self.create_poll(poll_data)
        self.assertHttpCreated(resp)
        pk = Poll.objects.order_by('-id')[0].pk
        resp = self.api_client.put(
            self.getURL('poll', pk), data=poll_data, authentication=self.get_credentials(admin=True))
        self.assertHttpOK(resp)
        resp = self.api_client.get(
            self.getURL('poll', pk), authentication=self.get_credentials(admin=True))
        self.assertEqual(self.deserialize(resp)['is_anonymous'], True)

    def test_voting(self):
        # create a poll
        poll_data = self.poll_data()
        resp = self.create_poll(poll_data)
        self.assertHttpCreated(resp)
        pk = Poll.objects.order_by('-id')[0].pk
        choice_data = self.choice_data(poll_id=pk)
        # create 3 choices
        self.create_choices(choice_data, quantity=3)
        resp = self.api_client.get(
            self.getURL('poll', pk), authentication=self.get_credentials())
        self.assertHttpOK(resp)
        deserialized = self.deserialize(resp)
        self.assertEqual(len(deserialized['choices']), 3)
        # vote
        choice_pk = Choice.objects.order_by('-id')[1].pk
        vote_data = self.vote_data(poll_id=pk, choices=[choice_pk])
        resp = self.api_client.post(self.getURL('vote'), data=vote_data, format='json',
                                    authentication=self.get_credentials())
        self.assertHttpCreated(resp)
        resp = self.api_client.get(self.getURL('result', id=pk), format='json',
                                   authentication=self.get_credentials())
        deserialized = self.deserialize(resp)
        self.assertDictEqual(deserialized['stats'],
                             {u'labels': [u'choice0', u'choice1', u'choice2'],
                              u'votes': 1,
                              u'codes': [u'choice0', u'choice1', u'choice2'],
                              u'values': [0.0, 1.0, 0.0]})

    def test_anonymous_voting(self):
        poll_data = self.poll_data(anonymous=True)
        resp = self.create_poll(poll_data)
        self.assertHttpCreated(resp)
        pk = Poll.objects.order_by('-id')[0].pk
        choice_data = self.choice_data(poll_id=pk)
        self.create_choices(choice_data, quantity=3)
        vote_data = self.vote_data(poll_id=1, choices=[1])
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpCreated(resp)

    def test_anonymous_voting_multiple(self):
        poll_data = self.poll_data(anonymous=True)
        resp = self.create_poll(poll_data)
        self.assertHttpCreated(resp)
        pk = Poll.objects.order_by('-id')[0].pk
        choice_data = self.choice_data(poll_id=pk)
        self.create_choices(choice_data, quantity=3)
        vote_data = self.vote_data(poll_id=1, choices=[1])
        # try based on IP
        # -- first vote should be ok
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpCreated(resp)
        # -- second vote should be refused
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpForbidden(resp)
        # try the same based on client id
        # -- first vote should be ok
        self.api_client.client.cookies['quickpollscid'] = uuid.uuid4().hex
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpCreated(resp)
        # -- second vote should be refused
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpForbidden(resp)

    def test_voting_with_data(self):
        poll_data = self.poll_data(anonymous=True)
        resp = self.create_poll(poll_data)
        self.assertHttpCreated(resp)
        pk = Poll.objects.order_by('-id')[0].pk
        choice_data = self.choice_data(poll_id=pk)
        self.create_choices(choice_data, quantity=3)
        vote_data = self.vote_data(poll_id=1, choices=[1])
        vote_data['data'] = {
            'foo': 'bar'
        }
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpCreated(resp)
        rdata = json.loads(self.deserialize(resp)['data'])
        self.assertDictEqual(rdata, vote_data['data'])

    def test_voting_with_comment(self):
        poll_data = self.poll_data(anonymous=True)
        resp = self.create_poll(poll_data)
        self.assertHttpCreated(resp)
        pk = Poll.objects.order_by('-id')[0].pk
        choice_data = self.choice_data(poll_id=pk)
        self.create_choices(choice_data, quantity=3)
        vote_data = self.vote_data(poll_id=1, choices=[1])
        vote_data['data'] = {
            'foo': 'bar',
        }
        vote_data['comment'] = 'this is a comment'
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpCreated(resp)
        rdata = json.loads(self.deserialize(resp)['data'])
        rcomment = self.deserialize(resp)['comment']
        self.assertDictEqual(rdata, vote_data['data'])
        self.assertEqual(rcomment, vote_data['comment'])

    def test_voting_no_choice(self):
        poll_data = self.poll_data(anonymous=True)
        resp = self.create_poll(poll_data)
        self.assertHttpCreated(resp)
        pk = Poll.objects.order_by('-id')[0].pk
        choice_data = self.choice_data(poll_id=pk)
        self.create_choices(choice_data, quantity=3)
        vote_data = self.vote_data(poll_id=1, choices=[1])
        del vote_data['choice']
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpBadRequest(resp)
        vote_data['choice'] = None
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpBadRequest(resp)

    def test_voting_by_code(self):
        poll_data = self.poll_data(anonymous=True)
        resp = self.create_poll(poll_data)
        self.assertHttpCreated(resp)
        pk = Poll.objects.order_by('-id')[0].pk
        choice_data = self.choice_data(poll_id=pk)
        self.create_choices(choice_data, quantity=3)
        vote_data = self.vote_data(poll_id=1, choices=[1])
        # invalid choice
        vote_data['choice'] = ['xchoice']
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpBadRequest(resp)
        vote_data['choice'] = ['choice1']
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpCreated(resp)

    def test_voting_multiple_polls_exist(self):
        # create multiple polls with choices
        for ref in ['one', 'two']:
            poll_data = self.poll_data(anonymous=True)
            poll_data['reference'] = ref
            resp = self.create_poll(poll_data)
            self.assertHttpCreated(resp)
            pk = Poll.objects.order_by('-id')[0].pk
            choice_data = self.choice_data(poll_id=pk)
            self.create_choices(choice_data, quantity=3)
        vote_data = self.vote_data(poll_id='two', choices=[1])
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpCreated(resp)

    def test_voting_multiple_votes_not_allowed(self):
        # create poll with vote, allow only one vote by user
        poll_data = self.poll_data(anonymous=True)
        poll_data['allow_multi_votes'] = False
        resp = self.create_poll(poll_data)
        self.assertHttpCreated(resp)
        pk = Poll.objects.order_by('-id')[0].pk
        choice_data = self.choice_data(poll_id=pk)
        self.create_choices(choice_data, quantity=3)
        # try voting twice, second should fail
        vote_data = self.vote_data(poll_id=pk, choices=[1])
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpCreated(resp)
        vote_data = self.vote_data(poll_id=pk, choices=[1])
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpForbidden(resp)

    def test_voting_multiple_votes_allowed(self):
        # create poll with vote, allow multiple multiple votes
        poll_data = self.poll_data(anonymous=True)
        poll_data['allow_multi_votes'] = True
        resp = self.create_poll(poll_data)
        self.assertHttpCreated(resp)
        pk = Poll.objects.order_by('-id')[0].pk
        choice_data = self.choice_data(poll_id=pk)
        self.create_choices(choice_data, quantity=3)
        # try voting twice, second should fail
        vote_data = self.vote_data(poll_id=pk, choices=[1])
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpCreated(resp)
        vote_data = self.vote_data(poll_id=pk, choices=[1])
        resp = self.api_client.post(
            self.getURL('vote'), data=vote_data, format='json')
        self.assertHttpCreated(resp)

    def create_poll(self, poll_data):
        return self.api_client.post(self.getURL('poll'), format='json',
                                    data=poll_data, authentication=self.get_credentials(admin=True))

    def create_choice(self, choice_data):
        return self.api_client.post(self.getURL('choice'), format='json',
                                    data=choice_data, authentication=self.get_credentials(admin=True))

    def create_choices(self, choice_data, quantity):
        for x in xrange(quantity):
            choice_data['choice'] = 'choice' + str(x)
            resp = self.api_client.post(self.getURL('choice'), format='json',
                                        data=choice_data, authentication=self.get_credentials(admin=True))
            self.assertHttpCreated(resp)

    def poll_data(self, anonymous=False, multiple=False, closed=False):
        now = timezone.now()
        # delete microseconds
        start_votes = make_naive(now) - timedelta(microseconds=now.microsecond)
        end_votes = start_votes + timedelta(days=10)
        return {
            'question': u'question',
            'description': u'desc',
            'is_anonymous': anonymous,
            'is_multiple': multiple,
            'is_closed': closed,
            'start_votes': unicode(start_votes.isoformat(), 'utf-8'),
            'end_votes': unicode(end_votes.isoformat(), 'utf-8'),
        }

    def choice_data(self, poll_id):
        return {
            'poll': self.getURL('poll', id=poll_id),
            'choice': 'choice'
        }

    def vote_data(self, poll_id, choices):
        return {
            'choice': choices,
            'poll': self.getURL('poll', id=poll_id)
        }
