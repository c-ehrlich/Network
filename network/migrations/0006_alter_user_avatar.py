# Generated by Django 3.2.4 on 2021-07-04 14:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('network', '0005_alter_user_avatar'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='avatar',
            field=models.ImageField(default='avatars/default/default_avatar.png', height_field='avatar_height', help_text='Avatar', upload_to='media/avatars', verbose_name='Avatar', width_field='avatar_width'),
        ),
    ]
