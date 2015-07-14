import mock
import time

from django.core import mail
from django import setup
from django.test import TestCase
from django.test.utils import override_settings

from nodeconductor.logging import models as logging_models
from nodeconductor.logging.tasks import process_event
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.log import event_logger
from nodeconductor.structure.tests import factories as structure_factories


class TestHookService(TestCase):
    @override_settings(LOGGING={
        'version': 1,

        'handlers': {
            'hook': {
                'class': 'nodeconductor.logging.log.HookHandler'
            }
        },
        'loggers': {
            'nodeconductor': {
                'level': 'DEBUG',
                'handlers': ['hook']
            }
        }
    })
    def setUp(self):
        setup()
        self.owner = structure_factories.UserFactory()
        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)
        self.other_user = structure_factories.UserFactory()

        self.event_type = 'customer_update_succeeded'
        self.other_event = 'customer_deletion_succeeded'
        self.message = 'Customer {customer_name} has been updated.'
        self.event = {
            'message': self.message,
            'type': self.event_type,
            'context': event_logger.customer.compile_context(customer=self.customer),
            'timestamp': time.time()
        }

    @mock.patch('celery.app.base.Celery.send_task')
    def test_logger_handler_sends_task(self, mocked_task):
        event_logger.customer.warning(self.message,
                                      event_type=self.event_type,
                                      event_context={'customer': self.customer})

        mocked_task.assert_called_with('nodeconductor.logging.process_event', mock.ANY, {})

    def test_email_hook_filters_events_by_user_and_event_type(self):
        # Create email hook for customer owner
        email_hook = logging_models.EmailHook.objects.create(user=self.owner,
                                                             email=self.owner.email,
                                                             event_types=[self.event_type])

        # Create email hook for another user
        other_hook = logging_models.EmailHook.objects.create(user=self.other_user,
                                                             email=self.owner.email,
                                                             event_types=[self.event_type])

        # Trigger processing
        process_event(self.event)

        # Test that one message has been sent for email hook of customer owner
        self.assertEqual(len(mail.outbox), 1)

        # Verify that destination address of message is correct
        self.assertEqual(mail.outbox[0].to, [email_hook.email])

    @mock.patch('requests.post')
    def test_webhook_makes_post_request_against_destination_url(self, requests_post):

        # Create web hook for customer owner
        self.web_hook = logging_models.WebHook.objects.create(user=self.owner,
                                                              destination_url='http://example.com/',
                                                              event_types=[self.event_type])

        # Trigger processing
        process_event(self.event)

        # Event is captured and POST request is triggererd because event_type and user_uuid match
        requests_post.assert_called_once_with(self.web_hook.destination_url, json=mock.ANY, verify=False)
