from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _
from rest_framework import status, response

from nodeconductor.core import models


class AsyncExecutor(object):
    async_executor = True


class CreateExecutorMixin(AsyncExecutor):
    create_executor = NotImplemented

    def perform_create(self, serializer):
        instance = serializer.save()
        self.create_executor.execute(instance, async=self.async_executor)
        instance.refresh_from_db()


class UpdateExecutorMixin(AsyncExecutor):
    update_executor = NotImplemented

    def perform_update(self, serializer):
        instance = self.get_object()
        # Save all instance fields before update.
        # To avoid additional DB queries - store foreign keys as ids.
        # Warning! M2M fields will be ignored.
        before_update_fields = {f: getattr(instance, f.attname) for f in instance._meta.fields}
        super(UpdateExecutorMixin, self).perform_update(serializer)
        instance.refresh_from_db()
        updated_fields = {f.name for f, v in before_update_fields.items() if v != getattr(instance, f.attname)}
        self.update_executor.execute(instance, async=self.async_executor, updated_fields=updated_fields)
        serializer.instance.refresh_from_db()


class DeleteExecutorMixin(AsyncExecutor):
    delete_executor = NotImplemented

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.delete_executor.execute(
            instance, async=self.async_executor, force=instance.state == models.StateMixin.States.ERRED)
        return response.Response(
            {'detail': _('Deletion was scheduled.')}, status=status.HTTP_202_ACCEPTED)


class ExecutorMixin(CreateExecutorMixin, UpdateExecutorMixin, DeleteExecutorMixin):
    """ Executer create/update/delete operation with executor """
    pass


class EagerLoadMixin(object):
    """ Reduce number of requests to DB.

        Serializer should implement static method "eager_load", that selects
        objects that are necessary for serialization.
    """

    def get_queryset(self):
        queryset = super(EagerLoadMixin, self).get_queryset()
        serializer_class = self.get_serializer_class()
        if self.action in ('list', 'retrieve') and hasattr(serializer_class, 'eager_load'):
            queryset = serializer_class.eager_load(queryset)
        return queryset
