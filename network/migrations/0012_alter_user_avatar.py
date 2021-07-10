# Generated by Django 3.2.4 on 2021-07-10 16:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('network', '0011_alter_user_avatar'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='avatar',
            field=models.ImageField(blank=True, default='avatars/default/dafault_avatar.jpg', height_field='avatar_height', help_text='Avatar', null=True, upload_to='avatars', verbose_name='Avatar', width_field='avatar_width'),
        ),
    ]
