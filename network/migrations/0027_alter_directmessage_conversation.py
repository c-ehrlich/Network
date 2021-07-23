# Generated by Django 3.2.4 on 2021-07-23 21:04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('network', '0026_auto_20210723_2050'),
    ]

    operations = [
        migrations.AlterField(
            model_name='directmessage',
            name='conversation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='network.conversation'),
        ),
    ]
