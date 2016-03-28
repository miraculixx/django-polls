# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import polls.models
import django.utils.timezone
from django.conf import settings
import django_extensions.db.fields.json
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Choice',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('choice', models.CharField(max_length=255)),
                ('code', models.CharField(default=b'', max_length=36, blank=True)),
            ],
            options={
                'ordering': ['poll', 'choice'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Poll',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('question', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('reference', models.CharField(default=uuid.uuid4, unique=True, max_length=36)),
                ('is_anonymous', models.BooleanField(default=False, help_text='Allow to vote for anonymous user')),
                ('is_multiple', models.BooleanField(default=False, help_text='Allow to make multiple choices')),
                ('is_closed', models.BooleanField(default=False, help_text='Do not accept votes')),
                ('start_votes', models.DateTimeField(default=django.utils.timezone.now, help_text='The earliest time votes get accepted')),
                ('end_votes', models.DateTimeField(default=polls.models.vote_endtime, help_text='The latest time votes get accepted')),
            ],
            options={
                'ordering': ['-start_votes'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Vote',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('comment', models.TextField(max_length=144, null=True, blank=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('data', django_extensions.db.fields.json.JSONField(null=True, blank=True)),
                ('choice', models.ForeignKey(to='polls.Choice')),
                ('poll', models.ForeignKey(to='polls.Poll')),
                ('user', models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ['poll', 'choice'],
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='vote',
            unique_together=set([('user', 'poll', 'choice')]),
        ),
        migrations.AddField(
            model_name='choice',
            name='poll',
            field=models.ForeignKey(to='polls.Poll'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='choice',
            unique_together=set([('poll', 'code')]),
        ),
    ]
