from django.db import models

from nodeconductor.quotas.fields import QuotaField
from nodeconductor.quotas.models import QuotaModelMixin
from nodeconductor.structure import models as structure_models


class TestService(structure_models.Service):
    projects = models.ManyToManyField(structure_models.Project, through='TestServiceProjectLink')

    @classmethod
    def get_url_name(cls):
        return 'test'


class TestServiceProjectLink(structure_models.ServiceProjectLink):
    service = models.ForeignKey(TestService)

    class Quotas(QuotaModelMixin.Quotas):
        vcpu = QuotaField(default_limit=20, is_backend=True)
        ram = QuotaField(default_limit=51200, is_backend=True)
        storage = QuotaField(default_limit=1024000, is_backend=True)
        instances = QuotaField(default_limit=30, is_backend=True)
        security_group_count = QuotaField(default_limit=100, is_backend=True)
        security_group_rule_count = QuotaField(default_limit=100, is_backend=True)
        floating_ip_count = QuotaField(default_limit=50, is_backend=True)


class TestInstance(structure_models.VirtualMachineMixin,
                   structure_models.PaidResource,
                   structure_models.Resource):

    service_project_link = models.ForeignKey(TestServiceProjectLink, on_delete=models.PROTECT)