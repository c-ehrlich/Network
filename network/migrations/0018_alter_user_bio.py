# Generated by Django 3.2.4 on 2021-07-15 08:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('network', '0017_auto_20210714_0959'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='bio',
            field=models.TextField(default='', max_length=500),
        ),
    ]
