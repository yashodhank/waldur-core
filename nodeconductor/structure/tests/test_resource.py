import unittest

from rest_framework import test, status

from nodeconductor.core import models as core_models
from nodeconductor.structure.models import NewResource, ServiceSettings
from nodeconductor.structure.tests import factories, fixtures, models as test_models


States = core_models.StateMixin.States


class ResourceRemovalTest(test.APITransactionTestCase):
    def setUp(self):
        self.user = factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.user)

    @unittest.skip('Unlink operation is not supported for new style resources yet.')
    def test_vm_unlinked_immediately_anyway(self):
        vm = factories.TestNewInstanceFactory(state=States.UPDATING)
        url = factories.TestNewInstanceFactory.get_url(vm, 'unlink')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)

    @unittest.skip('Unlink operation is not supported for new style resources yet.')
    def test_new_resource_unlinked_immediately(self):
        vm = factories.TestNewInstanceFactory(state=NewResource.States.OK)
        url = factories.TestNewInstanceFactory.get_url(vm, 'unlink')

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)

    def test_when_virtual_machine_is_deleted_descendant_resources_unlinked(self):
        # Arrange
        vm = factories.TestNewInstanceFactory()
        settings = factories.ServiceSettingsFactory(scope=vm)
        service = factories.TestServiceFactory(settings=settings)
        link = factories.TestServiceProjectLinkFactory(service=service)
        child_vm = factories.TestNewInstanceFactory(service_project_link=link)
        other_vm = factories.TestNewInstanceFactory()

        # Act
        vm.delete()

        # Assert
        self.assertFalse(test_models.TestNewInstance.objects.filter(id=child_vm.id).exists())
        self.assertFalse(test_models.TestService.objects.filter(id=service.id).exists())
        self.assertFalse(ServiceSettings.objects.filter(id=settings.id).exists())
        self.assertTrue(test_models.TestNewInstance.objects.filter(id=other_vm.id).exists())


class ResourceCreateTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.user)
        self.service_project_link = factories.TestServiceProjectLinkFactory()

    def test_resource_cannot_be_created_for_invalid_service_project_link(self):
        self.service_project_link.project.certifications.add(factories.ServiceCertificationFactory())
        self.assertFalse(self.service_project_link.is_valid)
        payload = {
            'service_project_link': factories.TestServiceProjectLinkFactory.get_url(self.service_project_link),
            'name': 'impossible resource',
        }
        url = factories.TestNewInstanceFactory.get_list_url()

        response = self.client.post(url, payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('service_project_link', response.data)


class ResourceTagsTest(test.APITransactionTestCase):
    def setUp(self):
        self.fixture = fixtures.ServiceFixture()
        self.client.force_authenticate(user=self.fixture.staff)

    def test_resource_tags_are_rendered_as_list(self):
        self.fixture.resource.tags.add('tag1')
        self.fixture.resource.tags.add('tag2')

        url = factories.TestNewInstanceFactory.get_url(self.fixture.resource)
        response = self.client.get(url)
        self.assertEqual(response.data['tags'], ['tag1', 'tag2'])

    def test_tags_are_saved_on_resource_provision(self):
        payload = {
            'service_project_link': factories.TestServiceProjectLinkFactory.get_url(self.fixture.service_project_link),
            'name': 'Tagged resource',
            'tags': ['tag1', 'tag2']
        }
        url = factories.TestNewInstanceFactory.get_list_url()

        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertItemsEqual(response.data['tags'], ['tag1', 'tag2'])

    def test_tags_are_saved_on_resource_modification(self):
        resource = self.fixture.resource
        resource.state = test_models.TestNewInstance.States.OK
        resource.save()
        resource.tags.add('tag1')
        resource.tags.add('tag2')
        payload = {'tags': []}
        url = factories.TestNewInstanceFactory.get_url(resource)

        response = self.client.patch(url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['tags'], [])

    def test_resource_can_be_filtered_by_tag(self):
        self.fixture.resource.tags.add('tag1')
        resource2 = factories.TestNewInstanceFactory(service_project_link=self.fixture.service_project_link)
        resource2.tags.add('tag2')

        url = factories.TestNewInstanceFactory.get_list_url()
        response = self.client.get(url, {'tag': 'tag1'})
        self.assertEqual(len(response.data), 1)
