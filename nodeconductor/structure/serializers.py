from __future__ import unicode_literals

import re

from django.db import models as django_models
from django.contrib import auth
from django.core.exceptions import ValidationError
from rest_framework import serializers

from nodeconductor.core import serializers as core_serializers, utils as core_utils
from nodeconductor.core.fields import MappedChoiceField
from nodeconductor.quotas import serializers as quotas_serializers
from nodeconductor.structure import models, filters
from nodeconductor.structure.filters import filter_queryset_for_user


User = auth.get_user_model()


# TODO: cleanup after migration to drf 3. Assures that non-nullable fields get empty value
def fix_non_nullable_attrs(attrs):
    non_nullable_char_fields = [
        'job_title',
        'organization',
        'phone_number',
        'description',
        'full_name',
        'native_name',
        'contact_details',
    ]
    for source in attrs:
        if source in non_nullable_char_fields:
            value = attrs[source]
            if value is None:
                attrs[source] = ''
    return attrs


class PermissionFieldFilteringMixin(object):
    """
    Mixin allowing to filter related fields.

    In order to constrain the list of entities that can be used
    as a value for the field:

    1. Make sure that the entity in question has corresponding
       Permission class defined.

    2. Implement `get_filtered_field_names()` method
       in the class that this mixin is mixed into and return
       the field in question from that method.
    """
    def get_fields(self):
        fields = super(PermissionFieldFilteringMixin, self).get_fields()

        try:
            request = self.context['request']
            user = request.user
        except (KeyError, AttributeError):
            return fields

        for field_name in self.get_filtered_field_names():
            fields[field_name].queryset = filter_queryset_for_user(
                fields[field_name].queryset, user)

        return fields

    def get_filtered_field_names(self):
        raise NotImplementedError(
            'Implement get_filtered_field_names() '
            'to return list of filtered fields')


class BasicUserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = User
        fields = ('url', 'uuid', 'username', 'full_name', 'native_name',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class BasicProjectSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.Project


class BasicProjectGroupSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.ProjectGroup
        fields = ('url', 'name', 'uuid')
        read_only_fields = ('name', 'uuid')


class ProjectGroupProjectMembershipSerializer(serializers.ModelSerializer):

    name = serializers.ReadOnlyField(source='projectgroup.name')
    url = serializers.HyperlinkedRelatedField(
        source='projectgroup',
        lookup_field='uuid',
        view_name='projectgroup-detail',
        queryset=models.ProjectGroup.objects.all(),
    )

    class Meta(object):
        model = models.ProjectGroup.projects.through
        fields = ('url', 'name',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }
        view_name = 'projectgroup-detail'

    def restore_object(self, attrs, instance=None):
        return attrs['projectgroup']

    def to_native(self, obj):
        memberships = list(models.ProjectGroup.projects.through.objects.filter(projectgroup=obj).all())
        return [super(ProjectGroupProjectMembershipSerializer, self).to_native(member) for member in memberships]


class ProjectSerializer(core_serializers.AugmentedSerializerMixin,
                        serializers.HyperlinkedModelSerializer):
    project_groups = BasicProjectGroupSerializer(many=True, read_only=True)
    quotas = quotas_serializers.QuotaSerializer(many=True, read_only=True)
    # These fields exist for backward compatibility
    resource_quota = serializers.SerializerMethodField('get_resource_quotas')
    resource_quota_usage = serializers.SerializerMethodField('get_resource_quotas_usage')

    class Meta(object):
        model = models.Project
        fields = (
            'url', 'uuid',
            'name',
            'customer', 'customer_uuid', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'project_groups',
            'description',
            'quotas',
            'resource_quota', 'resource_quota_usage',
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }
        related_paths = {
            'customer': ('uuid', 'name', 'native_name', 'abbreviation')
        }

    def get_related_paths(self):
        return 'customer',

    # TODO: cleanup after migration to drf 3
    def validate(self, attrs):
        return fix_non_nullable_attrs(attrs)

    def get_resource_quotas(self, obj):
        return models.Project.get_sum_of_quotas_as_dict(
            [obj], ['ram', 'storage', 'max_instances', 'vcpu'], fields=['limit'])

    def get_resource_quotas_usage(self, obj):
        quota_values = models.Project.get_sum_of_quotas_as_dict(
            [obj], ['ram', 'storage', 'max_instances', 'vcpu'], fields=['usage'])
        # No need for '_usage' suffix in quotas names
        return {
            key[:-6]: value for key, value in quota_values.iteritems()
        }


class ProjectCreateSerializer(PermissionFieldFilteringMixin,
                              core_serializers.AugmentedSerializerMixin,
                              serializers.HyperlinkedModelSerializer):
    # TODO: Reimplement using custom object save logic in view
    project_groups = ProjectGroupProjectMembershipSerializer(many=True, write_only=True, required=False)

    class Meta(object):
        model = models.Project
        fields = ('url', 'name', 'customer', 'description', 'project_groups')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }

    def get_filtered_field_names(self):
        return 'customer',

    # TODO: cleanup after migration to drf 3
    def validate(self, attrs):
        attrs = super(ProjectCreateSerializer, self).validate(attrs)

        user = self.context['request'].user
        if 'project_groups' not in attrs and self.object is not None:
            project_groups = self.object.project_groups.all()
        else:
            project_groups = attrs.get('project_groups', [])
            # remove project groups if nothing is specified to avoid m2m serializer errors (NC-366)
            if project_groups is None:
                del attrs['project_groups']
        customer = attrs['customer'] if 'customer' in attrs else self.object.customer

        if user.is_staff:
            return fix_non_nullable_attrs(attrs)

        if customer.has_user(user, models.CustomerRole.OWNER):
            return fix_non_nullable_attrs(attrs)

        if project_groups is not None:
            project_groups_access = [
                project_group.has_user(user, models.ProjectGroupRole.MANAGER)
                for project_group in project_groups
            ]
            if project_groups_access and all(project_groups_access):
                return fix_non_nullable_attrs(attrs)

        raise ValidationError('You cannot create project with such data')


class CustomerSerializer(core_serializers.AugmentedSerializerMixin,
                         serializers.HyperlinkedModelSerializer):
    projects = serializers.SerializerMethodField('get_customer_projects')
    project_groups = serializers.SerializerMethodField('get_customer_project_groups')
    owners = BasicUserSerializer(source='get_owners', many=True, read_only=True)

    class Meta(object):
        model = models.Customer
        fields = (
            'url',
            'uuid',
            'name', 'native_name', 'abbreviation', 'contact_details',
            'projects', 'project_groups',
            'owners',
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def _get_filtered_data(self, objects, serializer):
        try:
            user = self.context['request'].user
        except (KeyError, AttributeError):
            return None

        queryset = filter_queryset_for_user(objects, user)
        serializer_instance = serializer(queryset, many=True, context={'request': self.context['request']})
        return serializer_instance.data

    def get_customer_projects(self, obj):
        return self._get_filtered_data(obj.projects.all(), BasicProjectSerializer)

    def get_customer_project_groups(self, obj):
        return self._get_filtered_data(obj.project_groups.all(), BasicProjectGroupSerializer)

    # TODO: cleanup after migration to drf 3
    def validate(self, attrs):
        return fix_non_nullable_attrs(attrs)


class ProjectGroupSerializer(PermissionFieldFilteringMixin,
                             core_serializers.AugmentedSerializerMixin,
                             serializers.HyperlinkedModelSerializer):
    projects = BasicProjectSerializer(many=True, read_only=True)

    class Meta(object):
        model = models.ProjectGroup
        fields = (
            'url',
            'uuid',
            'name',
            'customer', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'projects',
            'description',
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }
        related_paths = {
            'customer': ('uuid', 'name', 'native_name', 'abbreviation')
        }

    def get_filtered_field_names(self):
        return 'customer',

    def get_fields(self):
        # TODO: Extract to a proper mixin
        fields = super(ProjectGroupSerializer, self).get_fields()

        try:
            method = self.context['view'].request.method
        except (KeyError, AttributeError):
            return fields

        if method in ('PUT', 'PATCH'):
            fields['customer'].read_only = True

        return fields

    # TODO: cleanup after migration to drf 3
    def validate(self, attrs):
        return fix_non_nullable_attrs(attrs)


class ProjectGroupMembershipSerializer(PermissionFieldFilteringMixin,
                                       serializers.HyperlinkedModelSerializer):
    project_group = serializers.HyperlinkedRelatedField(
        source='projectgroup',
        view_name='projectgroup-detail',
        lookup_field='uuid',
        queryset=models.ProjectGroup.objects.all(),
    )
    project_group_name = serializers.ReadOnlyField(source='projectgroup.name')
    project = serializers.HyperlinkedRelatedField(
        view_name='project-detail',
        lookup_field='uuid',
        queryset=models.Project.objects.all(),
    )
    project_name = serializers.ReadOnlyField(source='project.name')

    class Meta(object):
        model = models.ProjectGroup.projects.through
        fields = (
            'url',
            'project_group', 'project_group_name',
            'project', 'project_name',
        )
        view_name = 'projectgroup_membership-detail'

    def get_filtered_field_names(self):
        return 'project', 'project_group'


class CustomerPermissionSerializer(PermissionFieldFilteringMixin,
                                   core_serializers.AugmentedSerializerMixin,
                                   serializers.HyperlinkedModelSerializer):
    customer = serializers.HyperlinkedRelatedField(
        source='group.customerrole.customer',
        view_name='customer-detail',
        lookup_field='uuid',
        queryset=models.Customer.objects.all(),
    )

    role = MappedChoiceField(
        source='group.customerrole.role_type',
        choices=(
            ('owner', 'Owner'),
        ),
        choice_mappings={
            'owner': models.CustomerRole.OWNER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = (
            'url', 'role',
            'customer', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'user', 'user_full_name', 'user_native_name', 'user_username',
        )
        related_paths = {
            'user': ('username', 'full_name', 'native_name'),
            'group.customerrole.customer': ('name', 'native_name', 'abbreviation')
        }
        extra_kwargs = {
            'user': {
                'view_name': 'user-detail',
                'lookup_field': 'uuid',
                'queryset': User.objects.all(),
            },
        }
        view_name = 'customer_permission-detail'

    def create(self, validated_data):
        customer = validated_data['customer']
        user = validated_data['user']
        role = validated_data['role']

        permission, _ = customer.add_user(user, role)

        return permission

    def to_internal_value(self, data):
        value = super(CustomerPermissionSerializer, self).to_internal_value(data)
        return {
            'user': value['user'],
            'customer': value['group']['customerrole']['customer'],
            'role': value['group']['customerrole']['role_type'],
        }

    def validate(self, data):
        customer = data['customer']
        user = data['user']
        role = data['role']

        if customer.has_user(user, role):
            raise serializers.ValidationError('The fields customer, user, role must make a unique set.')

        return data

    def get_filtered_field_names(self):
        return 'customer',


class ProjectPermissionSerializer(PermissionFieldFilteringMixin,
                                  core_serializers.AugmentedSerializerMixin,
                                  serializers.HyperlinkedModelSerializer):
    project = serializers.HyperlinkedRelatedField(
        source='group.projectrole.project',
        view_name='project-detail',
        lookup_field='uuid',
        queryset=models.Project.objects.all(),
    )

    role = MappedChoiceField(
        source='group.projectrole.role_type',
        choices=(
            ('admin', 'Administrator'),
            ('manager', 'Manager'),
        ),
        choice_mappings={
            'admin': models.ProjectRole.ADMINISTRATOR,
            'manager': models.ProjectRole.MANAGER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = (
            'url',
            'role',
            'project', 'project_name',
            'user', 'user_full_name', 'user_native_name', 'user_username',
        )
        related_paths = {
            'user': ('username', 'full_name', 'native_name'),
            'group.projectrole.project': ('name',)
        }
        extra_kwargs = {
            'user': {
                'view_name': 'user-detail',
                'lookup_field': 'uuid',
                'queryset': User.objects.all(),
            },
        }
        view_name = 'project_permission-detail'

    def create(self, validated_data):
        project = validated_data['project']
        user = validated_data['user']
        role = validated_data['role']

        permission, _ = project.add_user(user, role)

        return permission

    def to_internal_value(self, data):
        value = super(ProjectPermissionSerializer, self).to_internal_value(data)
        return {
            'user': value['user'],
            'project': value['group']['projectrole']['project'],
            'role': value['group']['projectrole']['role_type'],
        }

    def validate(self, data):
        project = data['project']
        user = data['user']
        role = data['role']

        if project.has_user(user, role):
            raise serializers.ValidationError('The fields project, user, role must make a unique set.')

        return data

    def get_filtered_field_names(self):
        return 'project',


class ProjectGroupPermissionSerializer(PermissionFieldFilteringMixin,
                                       core_serializers.AugmentedSerializerMixin,
                                       serializers.HyperlinkedModelSerializer):
    project_group = serializers.HyperlinkedRelatedField(
        source='group.projectgrouprole.project_group',
        view_name='projectgroup-detail',
        lookup_field='uuid',
        queryset=models.ProjectGroup.objects.all(),
    )

    role = MappedChoiceField(
        source='group.projectgrouprole.role_type',
        choices=(
            ('manager', 'Manager'),
        ),
        choice_mappings={
            'manager': models.ProjectGroupRole.MANAGER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = (
            'url',
            'role',
            'project_group', 'project_group_name',
            'user', 'user_full_name', 'user_native_name', 'user_username',
        )
        related_paths = {
            'user': ('username', 'full_name', 'native_name'),
            'group.projectgrouprole.project_group': ('name',)
        }
        extra_kwargs = {
            'user': {
                'view_name': 'user-detail',
                'lookup_field': 'uuid',
                'queryset': User.objects.all(),
            },
        }
        view_name = 'projectgroup_permission-detail'

    def create(self, validated_data):
        project_group = validated_data['project_group']
        user = validated_data['user']
        role = validated_data['role']

        permission, _ = project_group.add_user(user, role)

        return permission

    def to_internal_value(self, data):
        value = super(ProjectGroupPermissionSerializer, self).to_internal_value(data)
        return {
            'user': value['user'],
            'project_group': value['group']['projectgrouprole']['project_group'],
            'role': value['group']['projectgrouprole']['role_type'],
        }

    def validate(self, data):
        project_group = data['project_group']
        user = data['user']
        role = data['role']

        if project_group.has_user(user, role):
            raise serializers.ValidationError('The fields project_group, user, role must make a unique set.')

        return data

    def get_filtered_field_names(self):
        return 'project_group',


class UserOrganizationSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = User
        fields = ('organization',)


class UserSerializer(serializers.HyperlinkedModelSerializer):
    email = serializers.EmailField()

    class Meta(object):
        model = User
        fields = (
            'url',
            'uuid', 'username',
            'full_name', 'native_name',
            'job_title', 'email', 'phone_number',
            'organization', 'organization_approved',
            'civil_number',
            'description',
            'is_staff', 'is_active',
        )
        read_only_fields = (
            'uuid',
            'civil_number',
            'organization',
            'organization_approved',
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    # TODO: cleanup after migration to drf 3
    def validate(self, attrs):
        return fix_non_nullable_attrs(attrs)

    def get_fields(self):
        fields = super(UserSerializer, self).get_fields()

        try:
            request = self.context['view'].request
            user = request.user
        except (KeyError, AttributeError):
            return fields

        if not user.is_staff:
            del fields['is_active']
            del fields['is_staff']
            fields['description'].read_only = True

        if request.method in ('PUT', 'PATCH'):
            fields['username'].read_only = True

        return fields


class CreationTimeStatsSerializer(serializers.Serializer):
    MODEL_NAME_CHOICES = (('project', 'project'), ('customer', 'customer'), ('project_group', 'project_group'))
    MODEL_CLASSES = {'project': models.Project, 'customer': models.Customer, 'project_group': models.ProjectGroup}

    model_name = serializers.ChoiceField(choices=MODEL_NAME_CHOICES)
    start_timestamp = serializers.IntegerField(min_value=0)
    end_timestamp = serializers.IntegerField(min_value=0)
    segments_count = serializers.IntegerField(min_value=0)

    def get_stats(self, user):
        start_datetime = core_utils.timestamp_to_datetime(self.data['start_timestamp'])
        end_datetime = core_utils.timestamp_to_datetime(self.data['end_timestamp'])

        model = self.MODEL_CLASSES[self.data['model_name']]
        filtered_queryset = filters.filter_queryset_for_user(model.objects.all(), user)
        created_datetimes = (
            filtered_queryset
            .filter(created__gte=start_datetime, created__lte=end_datetime)
            .values('created')
            .annotate(count=django_models.Count('id', distinct=True)))

        time_and_value_list = [
            (core_utils.datetime_to_timestamp(dt['created']), dt['count']) for dt in created_datetimes]

        return core_utils.format_time_and_value_to_segment_list(
            time_and_value_list, self.data['segments_count'],
            self.data['start_timestamp'], self.data['end_timestamp'])


class PasswordSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=7)

    def validate_password(self, value):
        if not re.search('\d+', value):
            raise serializers.ValidationError("Password must contain one or more digits")

        if not re.search('[^\W\d_]+', value):
            raise serializers.ValidationError("Password must contain one or more upper- or lower-case characters")

        return value
