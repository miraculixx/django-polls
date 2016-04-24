# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('polls', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='poll',
            name='allow_multi_votes',
            field=models.BooleanField(default=False, help_text='Allow multiple votes by same user'),
            preserve_default=True,
        ),
    ]
