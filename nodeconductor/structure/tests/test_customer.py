from __future__ import unicode_literals

from unittest import TestCase
import unittest

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.structure.models import CustomerRole
from nodeconductor.structure.tests import factories


class UrlResolverMixin(object):
    def _get_customer_url(self, customer):
        return 'http://testserver' + reverse('customer-detail', kwargs={'uuid': customer.uuid})


class CustomerRoleTest(TestCase):
    def setUp(self):
        self.customer = factories.CustomerFactory()

    def test_owner_customer_role_is_created_upon_customer_creation(self):
        self.assertTrue(self.customer.roles.filter(role_type=CustomerRole.OWNER).exists(),
                        'Owner role should have been created')


class CustomerApiPermissionTest(UrlResolverMixin, test.APITransactionTestCase):
    def setUp(self):
        self.users = {
            'staff': factories.UserFactory(is_staff=True),
            'owner': factories.UserFactory(),
            'not_owner': factories.UserFactory(),
        }

        self.customers = {
            'owned': factories.CustomerFactory.create_batch(2),
            'inaccessible': factories.CustomerFactory.create_batch(2),
        }

        for customer in self.customers['owned']:
            customer.add_user(self.users['owner'], CustomerRole.OWNER)

    # List filtration tests
    def test_user_can_list_customers_he_is_owner_of(self):
        self.client.force_authenticate(user=self.users['owner'])

        self._check_user_list_access_customers(self.customers['owned'], 'assertIn')

    def test_user_cannot_list_customers_he_is_not_owner_of(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        self._check_user_list_access_customers(self.customers['inaccessible'], 'assertNotIn')

    def test_user_can_list_customers_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        self._check_user_list_access_customers(self.customers['owned'], 'assertIn')

        self._check_user_list_access_customers(self.customers['inaccessible'], 'assertIn')

    # Direct instance access tests
    def test_user_can_access_customers_he_is_owner_of(self):
        self.client.force_authenticate(user=self.users['owner'])

        self._check_user_direct_access_customer(self.customers['owned'], status.HTTP_200_OK)

    def test_user_cannot_access_customers_he_is_not_owner_of(self):
        self.client.force_authenticate(user=self.users['not_owner'])
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self._check_user_direct_access_customer(self.customers['inaccessible'], status.HTTP_404_NOT_FOUND)

    def test_user_can_access_customers_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        self._check_user_direct_access_customer(self.customers['owned'], status.HTTP_200_OK)

        self._check_user_direct_access_customer(self.customers['inaccessible'], status.HTTP_200_OK)

    # Helper methods
    def _check_user_list_access_customers(self, customers, test_function):
        response = self.client.get(reverse('customer-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        urls = set([instance['url'] for instance in response.data])
        for customer in customers:
            url = self._get_customer_url(customer)

            getattr(self, test_function)(url, urls)

    def _check_user_direct_access_customer(self, customers, status_code):
        for customer in customers:
            response = self.client.get(self._get_customer_url(customer))

            self.assertEqual(response.status_code, status_code)


class CustomerApiManipulationTest(UrlResolverMixin, test.APISimpleTestCase):
    def setUp(self):
        self.users = {
            'staff': factories.UserFactory(is_staff=True),
            'owner': factories.UserFactory(),
            'not_owner': factories.UserFactory(),
        }

        self.customers = {
            'owner': factories.CustomerFactory(),
            'inaccessible': factories.CustomerFactory(),
        }

        self.customers['owner'].add_user(self.users['owner'], CustomerRole.OWNER)

    # Deletion tests
    def test_user_cannot_delete_customer_he_is_not_owner_of(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        response = self.client.delete(self._get_customer_url(self.customers['inaccessible']))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_delete_customer_he_is_owner_of(self):
        self.client.force_authenticate(user=self.users['owner'])

        response = self.client.delete(self._get_customer_url(self.customers['owner']))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_can_delete_customer_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.delete(self._get_customer_url(self.customers['owner']))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.delete(self._get_customer_url(self.customers['inaccessible']))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    # Creation tests
    def test_user_cannot_create_customer_if_he_is_not_staff(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        response = self.client.post(reverse('customer-list'), self._get_valid_payload())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_can_create_customer_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.post(reverse('customer-list'), self._get_valid_payload())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # Mutation tests
    def test_user_cannot_change_customer_as_whole_he_is_not_owner_of(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        response = self.client.put(self._get_customer_url(self.customers['inaccessible']),
                                   self._get_valid_payload())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_change_customer_he_is_owner_of(self):
        self.client.force_authenticate(user=self.users['owner'])

        response = self.client.put(self._get_customer_url(self.customers['owner']),
                                   self._get_valid_payload())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_can_change_customer_as_whole_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.put(self._get_customer_url(self.customers['owner']),
                                   self._get_valid_payload())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.put(self._get_customer_url(self.customers['inaccessible']),
                                   self._get_valid_payload())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_change_single_customer_field_he_is_not_owner_of(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        self._check_single_customer_field_change_permission(self.customers['inaccessible'], status.HTTP_404_NOT_FOUND)

    def test_user_cannot_change_customer_field_he_is_owner_of(self):
        self.client.force_authenticate(user=self.users['owner'])

        self._check_single_customer_field_change_permission(self.customers['owner'], status.HTTP_403_FORBIDDEN)

    def test_user_can_change_single_customer_field_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        self._check_single_customer_field_change_permission(self.customers['owner'], status.HTTP_200_OK)

        self._check_single_customer_field_change_permission(self.customers['inaccessible'], status.HTTP_200_OK)

    # Helper methods
    def _get_valid_payload(self, resource=None):
        resource = resource or factories.CustomerFactory()

        return {
            'name': resource.name,
            'abbreviation': resource.abbreviation,
            'contact_details': resource.contact_details,
        }

    def _check_single_customer_field_change_permission(self, customer, status_code):
        payload = self._get_valid_payload(customer)

        for field, value in payload.items():
            data = {
                field: value
            }

            response = self.client.patch(self._get_customer_url(customer), data)
            self.assertEqual(response.status_code, status_code)