# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import uuidfield.fields
import django.core.validators


class Migration(migrations.Migration):

    replaces = [('cost_tracking', '0001_initial'), ('cost_tracking', '0002_price_list'), ('cost_tracking', '0003_new_price_list_items'), ('cost_tracking', '0004_remove_connection_to_resource'), ('cost_tracking', '0005_expand_item_type_size'), ('cost_tracking', '0006_add_backend_cache_fields_to_pricelist'), ('cost_tracking', '0007_remove_obsolete_billing_fields')]

    dependencies = [
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PriceEstimate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('object_id', models.PositiveIntegerField()),
                ('total', models.FloatField(default=0)),
                ('details', jsonfield.fields.JSONField(blank=True)),
                ('month', models.PositiveSmallIntegerField(validators=[django.core.validators.MaxValueValidator(12), django.core.validators.MinValueValidator(1)])),
                ('year', models.PositiveSmallIntegerField()),
                ('is_manually_input', models.BooleanField(default=False)),
                ('is_visible', models.BooleanField(default=True)),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='priceestimate',
            unique_together=set([('content_type', 'object_id', 'month', 'year', 'is_manually_input')]),
        ),
        migrations.CreateModel(
            name='PriceListItem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
                ('object_id', models.PositiveIntegerField()),
                ('key', models.CharField(max_length=50)),
                ('value', models.DecimalField(default=0, verbose_name=b'Hourly rate', max_digits=9, decimal_places=2)),
                ('units', models.CharField(max_length=30, blank=True)),
                ('item_type', models.CharField(default=b'flavor', max_length=30, choices=[(b'flavor', b'flavor'), (b'storage', b'storage'), (b'license-application', b'license-application'), (b'license-os', b'license-os'), (b'support', b'support'), (b'network', b'network')])),
                ('is_manually_input', models.BooleanField(default=False)),
                ('resource_content_type', models.ForeignKey(related_name='+', default=None, to='contenttypes.ContentType')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='pricelistitem',
            unique_together=set([('key', 'content_type', 'object_id')]),
        ),
        migrations.CreateModel(
            name='DefaultPriceListItem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('key', models.CharField(max_length=50)),
                ('value', models.DecimalField(default=0, verbose_name=b'Hourly rate', max_digits=9, decimal_places=2)),
                ('units', models.CharField(max_length=30, blank=True)),
                ('item_type', models.CharField(default=b'flavor', max_length=30, choices=[(b'flavor', b'flavor'), (b'storage', b'storage'), (b'license-application', b'license-application'), (b'license-os', b'license-os'), (b'support', b'support'), (b'network', b'network')])),
                ('resource_content_type', models.ForeignKey(default=None, to='contenttypes.ContentType')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ResourceUsage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('date', models.DateField()),
                ('object_id', models.PositiveIntegerField()),
                ('units', models.CharField(max_length=30, blank=True)),
                ('value', models.DecimalField(default=0, max_digits=9, decimal_places=2)),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='resourceusage',
            unique_together=set([('date', 'content_type', 'object_id', 'units')]),
        ),
    ]
