from .models import User, Post
from babel.dates import format_date, format_datetime, format_time
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
import datetime
from pytz import timezone


# +-----------------------------------------+
# |           GLOBAL VARIABLES              |
# +-----------------------------------------+
# shouild probably factor these out in a more elegant way
PAGINATION_POST_COUNT = 10


# +-----------------------------------------+
# |          UTILITY FUNCTIONS              |
# +-----------------------------------------+
def check_username_validity(username):
    """CHECKS USERNAME VALIDITY
    
    input: username (string)
    output: boolean (true or false)
    
    conditions:
    The username must be at least 2 characters long
    The first character must be alphanumeric
    Every character after that must be either alphanumeric or underscore"""
    if len(username) < 2:
        return False
    if not username[0].isalnum():
        return False
    for character in username[1:]:
        if not (character.isalnum() or character == '_'):
            return False
    return True


def convert_javascript_date_to_python(js_date_now):
    """takes a javascript Date.now() value, and converts it to a Python datetime object
    
    input: javascript Date.now (epoch time)
    output: Python datetime object that represents the same time"""
    js_date_formatted = js_date_now / 1000
    utc = timezone('UTC')
    date = datetime.datetime.fromtimestamp(js_date_formatted, tz=utc)
    return date


def get_display_time(request, datetime_input):
    """Takes a datatime object, and returns a time difference string.
    
    input: a date, in datetime object format
    output: a string showing the amount of time that has elapsed
    
    Sample output strings:
    less than 1 minute:   'now'
    less than 1 hour:     '22m'
    less than 1 day:      '4h'
    this year:            'Mar 11'
    older:                'Mar 11, 2019'
    """

    if request.user.is_authenticated and request.user.language:
        language = request.user.language
    elif request.LANGUAGE_CODE and next((v[0] for i, v in enumerate(settings.LANGUAGES) if v[0] == request.LANGUAGE_CODE), None) != None:
        language = request.LANGUAGE_CODE
    else: language = 'en'

    utc = timezone('UTC')
    post = datetime_input
    now = datetime.datetime.now(tz=utc)
    difference = now - post
    td_days = difference.days
    td_secs = difference.seconds

    if language == 'de':
        if td_days == 0 and td_secs < 60:
            return 'Jetzt'
        if td_days == 0 and td_secs < 3600:
            return f"{td_secs // 60} Min."
        if td_days == 0 and td_secs < 86400:
            return f"{td_secs // 3600} Std."
        if post.year == now.year:
            return format_datetime(post, 'd. MMM', locale=language)
        if post.year != now.year:
            return format_datetime(post, 'd. MMM yyyy', locale=language)

    elif language == 'ja':
        if td_days == 0 and td_secs < 60:
            return '今'
        if td_days == 0 and td_secs < 3600:
            return f"{td_secs // 60}分前"
        if td_days == 0 and td_secs < 86400:
            return f"{td_secs // 3600}時間前"
        if post.year == now.year:
            return format_datetime(post, 'M月d日', locale=language)
        if post.year != now.year:
            return format_datetime(post, 'yyyy年M月d日', locale=language)

    else:
        # default language is 'en'
        if td_days == 0 and td_secs < 60:
            return "now"
        if td_days == 0 and td_secs < 3600:
            return f"{td_secs // 60}m"
        if td_days == 0 and td_secs < 86400:
            return f"{td_secs // 3600}h"
        if post.year == now.year:
            return datetime.datetime.strftime(post, "%b %-d")
        if post.year != now.year:
            return datetime.datetime.strftime(post, "%b %-d, %Y")

    return "if you see this, there was an error in get_display_time"


def get_mentions_from_post(post_text):
    """Takes a post text, and returns a list of mentions (User objects) in the post"""
    mentions = []
    for word in post_text.split():
        # compare the word to a regular expression:
        # the first character must be '@'
        # the second and third character must be alphanumeric
        # keep going until you reach a character that isn't alphanumeric or '_',
        # which means it's the end of the username
        length = len(word)
        if length >= 2:
            if word[0] == '@' and word[1].isalnum():
                # create a new string object that is the word without the '@'
                username = word[1]
                # then, keep adding characters to the new word until you hit a character that is neither alphanumeric nor '_'
                location = 2
                while location < length:
                    if word[location].isalnum() or word[location] == '_':
                        username += word[location]
                        location += 1
                    else:
                        break
                # if a user with that username exists, add it to the list
                try:
                    user = User.objects.get(username=username)
                    if not user in mentions:
                        mentions.append(user)
                        user.mentions_since_last_checked += 1
                        user.save()
                except User.DoesNotExist:
                    pass
    return mentions


def get_post_additional_data(request, post):
    """takes a post object, and appends additional information
    
    Data that is always added, whether user is logged in or not:
        timestamp_f (string): formatted and localised timestamp for timeline view

    Data that is only added if user is logged in:
        author_blocked_by_user (boolean): is the post author blocked by the user requesting the post
        user_blocked_by_author (boolean): is the user requesting the post blocked by the author"""

    post.timestamp_f = get_display_time(request, post.timestamp)

    if request.user:
        post.author_blocked_by_user = request.user in post.author.blocked_by.all()
        post.user_blocked_by_author = request.user in post.author.blocked_users.all()
        if post.user_blocked_by_author:
            post.text = "You do not have permission to see this post because you have been blocked by " + post.author.username + "."


def get_post_from_id(request, id):
    post = Post.objects.get(id=id)
    get_post_additional_data(request, post)
    return post


def get_post_count_since_timestamp(request, timestamp, context):
    """returns the number of new posts for a given context since a given timestamp
    
    inputs: timestamp (python datetime object)
            context (dictionary)
    outputs: new_post_count (int)

    context options: 
        'location':
            'public_feed'
            'user' (/<username>)
            'following'
            'mentions'
            'likes' (/<username>)
        'username': (this will not contain anything unless the view requires it)
            '<username>'

    """
    user = request.user
    posts = {}
    if context['location'] == 'user':
        post_user = User.objects.get(username=context['username'])
        # get posts by post_user, newer than timestamp
        posts = Post.objects.filter(author=post_user, timestamp__gte=timestamp).count()
    if context['location'] == 'following':
        # get posts by followed users, newer than timestamp
        posts = Post.objects.filter(author__in=user.following.all()).filter(timestamp__gt=timestamp).count()
    if context['location'] == 'index':
        posts = Post.objects.filter(timestamp__gt=timestamp).count()
    if context['location'] == 'mentions':
        posts = Post.objects.filter(mentioned_users__in=[user], timestamp__gt=timestamp).count()
    if context['location'] == 'likes':
        post_user = User.objects.get(username=context['username'])
        print(post_user)
        posts = post_user.liked_posts.filter(timestamp__gt=timestamp).count()
        print(posts)
    # if we haven't created posts yet, return an error
    if  posts:
        return posts
    else:
        return 0
