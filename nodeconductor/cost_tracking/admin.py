from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.utils.lru_cache import lru_cache

from nodeconductor.cost_tracking import models
from nodeconductor.structure import models as structure_models, admin as structure_admin


@lru_cache(maxsize=1)
def _get_service_content_type_queryset():
    """ Get list of services content types """
    services = structure_models.Service.get_all_models()
    service_content_type_ids = [ContentType.objects.get_for_model(s).id for s in services]
    return ContentType.objects.filter(id__in=service_content_type_ids)


class PriceListItemAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'key', 'item_type', 'value', 'units', 'service')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "content_type":
            kwargs["queryset"] = _get_service_content_type_queryset()
        return super(PriceListItemAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


class DefaultPriceListItemAdmin(structure_admin.ChangeReadonlyMixin, admin.ModelAdmin):
    list_display = ('uuid', 'key', 'item_type', 'value', 'units', 'service_content_type')
    change_readonly_fields = ('service_content_type',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "service_content_type":
            kwargs["queryset"] = _get_service_content_type_queryset()
        return super(DefaultPriceListItemAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.register(models.PriceListItem, PriceListItemAdmin)
admin.site.register(models.DefaultPriceListItem, DefaultPriceListItemAdmin)
