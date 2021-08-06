import json
from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Exists, OuterRef, prefetch_related_objects
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.http.response import HttpResponseBadRequest
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy as _lazy
from django.views.decorators.csrf import csrf_protect

from network.forms import EditAccountForm, NewPostForm, RegisterAccountForm, RegisterAccountStage2Form, RegisterAccountStage3Form
from network.models import User, Post, Conversation
from network import utils

PAGINATION_POST_COUNT = 10



# +-----------------------------------------+
# |        VIEWS THAT RETURN PAGES          |
# +-----------------------------------------+

@login_required
def dms(request):
    threads = utils.get_dm_threads_paginated(request)
    return render(request, "network/dms.html", {
        "threads": threads,
    })


@login_required
def dm_thread(request, username):
    convo_partner = utils.get_user_from_username(username)
    page = request.GET.get('page', 1)
    user_id = request.user.id
    convo_partner_id = convo_partner.id
    conversation = Conversation.objects.get(
        user_ids=[user_id, convo_partner_id]
    )
    thread = conversation.messages.all()
    p = Paginator(thread, PAGINATION_POST_COUNT)
    # TODO if thread doesn't exist, give error
    return render(request, "network/dm_thread.html", {
        "thread": p.page(page),
        "thread_id": conversation.id,
    })


@login_required
def following(request):
    if request.method == "GET":
        user = request.user

        posts = Post.objects.filter(
            author__in=user.following.all()
        ).prefetch_related(
            'author__blocked_users',
            'author__blocked_by',
        ).select_related(
            'author',
            'reply_to',
        ).annotate(
            Count('users_who_liked'),
            Count('replies'),
        )

        paginated = Paginator(posts, PAGINATION_POST_COUNT)
        page = request.GET.get('page', 1)
        posts = paginated.get_page(page)

        for post in posts:
            utils.get_post_additional_data(request, post)

        context = {'posts': posts}

        return render(request, "network/following.html", context)

    else:
        return HttpResponseBadRequest()


def index(request):
    """RETURNS THE INDEX PAGE"""
    if request.method == "GET":
            
        posts = Post.objects.all().prefetch_related(
            'author__blocked_users',
            'author__blocked_by',
        ).select_related(
            'author',
            'reply_to'
        ).annotate(
            Count('users_who_liked'),
            Count('replies'),
        )

        paginated = Paginator(posts, PAGINATION_POST_COUNT)
        page = request.GET.get('page', 1)
        posts = paginated.get_page(page)

        # TODO maybe loop inside the function instead of here?
        for post in posts:
            utils.get_post_additional_data(request, post)

        context = {
            'posts': posts,
            'new_post_form': NewPostForm(auto_id=True),
        }

        return render(request, "network/index.html", context)

    else:
        return HttpResponseBadRequest()


def likes(request, username):
    """RETURNS THE LIKED POSTS PAGE"""
    if request.method == "GET":
        view_user = User.objects.get(username=username)
        context = {'view_user': view_user}

        # create posts object (paginated)
        if view_user.show_liked_posts == True:
            posts = Post.objects.filter(
                users_who_liked=view_user
            ).prefetch_related(
                'author__blocked_users__id',
                'author__blocked_by__id',
            ).select_related(
                'author',
                'reply_to',
            ).annotate(
                Count('users_who_liked'),
                Count('replies'),
            )

            paginated = Paginator(posts, PAGINATION_POST_COUNT)
            page = request.GET.get('page', 1)
            posts = paginated.get_page(page)

            for post in posts:
                utils.get_post_additional_data(request, post)

            context['posts'] = posts

        return render(request, "network/likes.html", context)

    else:
        return HttpResponseBadRequest()


def login_view(request):
    """RETURNS THE LOGIN VIEW"""
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "network/login.html", {
                "message": _("Invalid username and/or password."),
            })
    else:
        return render(request, "network/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


@login_required
def mentions(request):
    if request.method == "GET":
        user = request.user

        posts = Post.objects.filter(
            mentioned_users__in=[user]
        ).prefetch_related(
            'author__blocked_users',
            'author__blocked_by',
        ).select_related(
            'author',
            'reply_to',
        ).annotate(
            Count('users_who_liked'),
            Count('replies'),
        )

        paginated = Paginator(posts, PAGINATION_POST_COUNT)
        page = request.GET.get('page', 1)
        posts = paginated.get_page(page)

        for post in posts:
            utils.get_post_additional_data(request, post)

        context = {'posts': posts}

        return render(request, "network/mentions.html", context)

    else:
        return HttpResponseRedirect(reverse("index"))


def post(request, id):
    if request.method == "GET":
        post = Post.objects.get(id=id)
        replies = post.replies.all(
        ).prefetch_related(
            'author__blocked_users',
            'author__blocked_by',
        ).select_related(
            'author',
            'reply_to',
        ).annotate(
            Count('users_who_liked'),
            Count('replies'),
        )

        paginated = Paginator(replies, PAGINATION_POST_COUNT)
        page = request.GET.get('page', 1)
        replies = paginated.get_page(page)

        context = {
            'view_user': post.author,
            'post': post,
            'posts': replies, #call it that to make it work with posts.html
        }

        return render(request, "network/post.html", context)
    
    else:
        return HttpResponseBadRequest()


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        displayname = request.POST["displayname"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "network/register.html", {
                "message": _("Passwords must match."),
                "form": RegisterAccountForm(),
            })

        if not utils.check_username_validity(username):
            return render(request, "network/register.html", {
                "message": _("Username is not valid."),
                "form": RegisterAccountForm(),
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.displayname = displayname
            user.save()
        except IntegrityError:
            return render(request, "network/register.html", {
                "message": _("Username already taken."),
                "form": RegisterAccountForm(),
            })
        login(request, user)
        return HttpResponseRedirect(reverse("register2"))

    elif request.method == "GET":
        return render(request, "network/register.html", {
            "form": RegisterAccountForm()
        })

    else:
        return HttpResponseBadRequest()


@login_required
def register2(request):
    user = request.user
    if request.method == "GET":
        if user.has_completed_onboarding == False:
            return render(request, "network/register2.html", {
                "form": RegisterAccountStage2Form(instance = user)
            })
        else:
            return HttpResponseRedirect(reverse("index"))
    elif request.method == "POST":
        form = RegisterAccountStage2Form(request.POST, request.FILES, instance = user)
        if form.is_valid():
            user.bio = form.cleaned_data['bio']
            user.avatar = form.cleaned_data['avatar']
            form.save()
            return HttpResponseRedirect(reverse("register3"))
        else:
            return render(request, "network/register2.html", {
                "form": form,
                "message": _("Form data is invalid")
            })
            
    else:
        return HttpResponseBadRequest()


@login_required
def register3(request):
    user = request.user
    if request.method == "GET":
        if user.has_completed_onboarding == False:
            return render(request, "network/register3.html", {
                "form": RegisterAccountStage3Form(instance = user)
            })
        else:
            return HttpResponseRedirect(reverse("index"))

    elif request.method == "POST":
        form = RegisterAccountStage3Form(request.POST, instance = user)
        if form.is_valid():
            user.theme = form.cleaned_data['theme']
            user.language = form.cleaned_data['language']
            user.show_liked_posts = form.cleaned_data['show_liked_posts']
            user.has_completed_onboarding = True
            user.save()
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "network/register3.html", {
                "form": form,
                "message": _("Form data is invalid")
            })

    else:
        return HttpResponseBadRequest()


@login_required
def settings(request):
    user = request.user
    blocklist = user.blocked_users.all().order_by('username')

    if request.method == "GET":
        return render(request, "network/settings.html", {
            "account_form": EditAccountForm(instance = user),
            "preferences_form": RegisterAccountStage3Form(instance = user),
            "blocklist": blocklist,
        })

    elif request.method == "POST":
        if 'account-form-button' in request.POST:
            form = EditAccountForm(request.POST, request.FILES, instance = user)
            if form.is_valid():
                user = authenticate(
                    request, 
                    username=utils.get_user_from_id(request.user.id), 
                    password=form.cleaned_data["password"]
                )
                if user is None:
                    return render(request, "network/settings.html", {
                        "account_form": EditAccountForm(instance = user),
                        "preferences_form": RegisterAccountStage3Form(instance = user),
                        "blocklist": blocklist,
                        "message": _("Invalid password."),
                        "start_tab": "account",
                    })
                if utils.check_username_validity(form.cleaned_data["username"]) == False:
                    user = utils.get_user_from_id(request.user.id) # dirty hack to clean the username field NICE-TO-HAVE refactor
                    # return an EditAccountForm with the user's original information
                    return render(request, "network/settings.html", {
                        "account_form": EditAccountForm(instance = user),
                        "preferences_form": RegisterAccountStage3Form(instance = user),
                        "blocklist": blocklist,
                        "message": _("Username is not valid."),
                        "start_tab": "account",
                    })

                # get new_password and new_pass_confirm from form
                # check if they are the same, if so change the password
                # if not, return an EditAccountForm with the user's original information
                # and a message saying the passwords don't match
                new_password = form.cleaned_data["new_password"]
                new_password_confirm = form.cleaned_data["new_password_confirm"]
                if new_password != new_password_confirm:
                    return render(request, "network/settings.html", {
                        "account_form": EditAccountForm(instance = user),
                        "preferences_form": RegisterAccountStage3Form(instance = user),
                        "blocklist": blocklist,
                        "message": _("New passwords don't match."),
                        "start_tab": "account",
                    })
                if new_password != None and new_password != "":
                    user.set_password(new_password)

                user.save()
                form.save()

            # form is not valid
            else:
                print(form.data)
                return render(request, "network/settings.html", {
                    "account_form": EditAccountForm(instance = user),
                    "preferences_form": RegisterAccountStage3Form(instance = user),
                    "blocklist": blocklist,
                    "message": _("Form data is invalid"),
                    "start_tab": "account",
                })

            # Form is valid. This is the place we _want_ to end up.
            user.refresh_from_db()
            return render(request, "network/settings.html", {
                "account_form": EditAccountForm(instance = user),
                "preferences_form": RegisterAccountStage3Form(instance = user),
                "blocklist": blocklist,
                "start_tab": "account",
            })

        elif 'preferences-form-button' in request.POST:
            form = RegisterAccountStage3Form(request.POST, instance = user)
            if form.is_valid():
                user.theme = form.cleaned_data['theme']
                user.language = form.cleaned_data['language']
                user.show_liked_posts = form.cleaned_data['show_liked_posts']
                user.save()
                print("preferences form good")
                return render(request,"network/settings.html", {
                    "account_form": EditAccountForm(instance = user),
                    "preferences_form": RegisterAccountStage3Form(instance = user),
                    "blocklist": blocklist,
                    "start_tab": "preferences",
                })
            else:
                print("preferences form bad")
                return render(request, "network/settings.html", {
                    "account_form": EditAccountForm(instance = user),
                    "preferences_form": RegisterAccountStage3Form(instance = user),
                    "blocklist": blocklist,
                    "message": _("Form data is invalid"),
                    "start_tab": "preferences",
                })

    else:
        return HttpResponseBadRequest()


def user(request, username):
    if request.method == "GET":
        view_user = User.objects.get(username=username)
        context = {}

        posts = Post.objects.filter(
            author__username=username
        ).prefetch_related(
            'author__blocked_users',
            'author__blocked_by',
        ).select_related(
            'author',
            'reply_to',
        ).annotate(
            Count('users_who_liked'),
            Count('replies'),
        )

        paginated = Paginator(posts, PAGINATION_POST_COUNT)
        page = request.GET.get('page', 1)
        posts = paginated.get_page(page)

        for post in posts:
            utils.get_post_additional_data(request, post)

        context['view_user'] = view_user
        context['posts'] = posts

        if request.user == view_user:
            context['new_post_form'] = NewPostForm()

        return render(request, "network/user.html", context)

    else:
        return HttpResponseBadRequest()


# +-----------------------------------------+
# |        VIEWS THAT RETURN JSON           |
# +-----------------------------------------+
@csrf_protect
def block_toggle(request, user_id):
    if request.method == "PUT":
        user = request.user
        view_user = utils.get_user_from_id(user_id)
        data = json.loads(request.body)
        if data['intent'] == 'block':
            if not view_user in user.blocked_users.all():
                user.blocked_users.add(view_user)
                # end follow relation in both directions
                if view_user in user.following.all():
                    user.following.remove(view_user)
                if user in view_user.following.all():
                    view_user.following.remove(user)
                # remove post likes in both directions
                for post in user.posts.all():
                    if view_user in post.users_who_liked.all():
                        post.users_who_liked.remove(view_user)
                for post in view_user.posts.all():
                    if user in post.users_who_liked.all():
                        post.users_who_liked.remove(user)
                return JsonResponse({
                    "intent": "block",
                    "success": True,
                    "user": {
                        "username": view_user.username,
                        "avatar": view_user.avatar.url,
                        "id": view_user.id
                    }
                }, status=200)
            else:
                return JsonResponse({
                    "intent": "block",
                    "success": False,
                    "message": _("User is already blocked."),
                }, status=400)
        elif data['intent'] == 'unblock':
            if view_user in user.blocked_users.all():
                user.blocked_users.remove(view_user)
                return JsonResponse({
                    "intent": "unblock",
                    "success": True,
                }, status=200)
            else:
                return JsonResponse({
                    "intent": "unblock",
                    "success": False,
                    "message": _("User is already not blocked."),
                }, status=400)
        else:
            return HttpResponseBadRequest()

    else:
        return JsonResponse({
            "error": _("PUT request required.")
        }, status=400)


@csrf_protect
def block_toggle_username(request, username):
    # NICE-TO-HAVE this is not very DRY! (a lot of code is repeated from block_toggle)
    # REFACTOR: block_toggle should take user=None and username=None, then sees if at least one exist
    user = request.user
    if request.method == 'PUT':
        view_user = utils.get_user_from_username(username)
        if not view_user in user.blocked_users.all():
            user.blocked_users.add(view_user)
        # end follow relation in both directions
        if view_user in user.following.all():
            user.following.remove(view_user)
        if user in view_user.following.all():
            view_user.following.remove(user)
        # remove post likes in both directions
        for post in user.posts.all():
            if view_user in post.users_who_liked.all():
                post.users_who_liked.remove(view_user)
        for post in view_user.posts.all():
            if user in post.users_who_liked.all():
                post.users_who_liked.remove(user)
        return JsonResponse({
            "intent": "block",
            "success": True,
            "user": {
                "username": view_user.username,
                "displayname": view_user.displayname,
                "avatar": view_user.avatar.url,
                "id": view_user.id
            }
        }, status=200)
    else:
        return HttpResponseBadRequest()


@csrf_protect
def clear_mentions_count(request):
    if request.method == "PUT":
        data = json.loads(request.body)
        if data['intent'] == 'clear_mentions_count':
            user = request.user
            user.mentions_since_last_checked = 0
            user.save()
            return HttpResponse(status=200)
        else:
            print(data['intent'])
            return HttpResponse(status=400)
    else:
        return HttpResponse(status=405)


@csrf_protect
def compose(request):
    print(request.headers)
    form = NewPostForm(request.POST, request.FILES)
    if form.is_valid():
        post_text = form.cleaned_data["text"]
        if post_text == "":
            return JsonResponse({
                "message": _("You can't submit an empty post")
            }, status=400)
        user=request.user
        mentioned_users = utils.get_mentions_from_post(post_text)
        image = form.cleaned_data['image']
        post = Post(author=user, text=post_text, image=image)
        post.save()
        for user in mentioned_users:
            post.mentioned_users.add(user)
        return HttpResponseRedirect(request.headers['Referer'])
    else:
        return JsonResponse({
            "message": _("Form data invalid")
        }, status=400)


@csrf_protect
def edit(request, post_id):
    if request.method == "PUT":
        data = json.loads(request.body)
        new_text = data['new_text']
        if len(new_text) > 140:
            return JsonResponse({
                "message": _("Maximum post length is 140 characters"),
                "edited": False,
            }, status=400)
        post = utils.get_post_from_id(request, post_id)
        if request.user == post.user:
            new_mentioned_users = utils.get_mentions_from_post(new_text)
            for user in new_mentioned_users:
                post.mentioned_users.add(user)
            post.text = new_text
            post.save()
            return JsonResponse({
                "message": _("Post edited successfully"),
                "edited": True,
            }, status=201)
        else:
            return JsonResponse({
                "message": _("You are not authorized to edit this post"),
                "edited": False,
            }, status=400)


@csrf_protect
def follow(request, user_id):
    if request.method == "PUT":
        user = request.user
        # user is trying to follow themselves
        if user_id == user.id:
            return JsonResponse({
                "error": _("You cannot follow your own account.")
            }, status=400)
        else: 
            data = json.loads(request.body)
            user_to_follow = User.objects.get(id=user_id) 
            # good follow request
            if data['intent'] == 'follow' and user_to_follow not in user.following.all():
                # check for block relationship
                if user_to_follow in user.blocked_users.all() or user in user_to_follow.blocked_users.all():
                    return JsonResponse({
                        "error": _("You cannot follow this user because there is a block relationship.")
                    }, status=400)
                user.following.add(user_to_follow)
                return JsonResponse({
                    "message": _(f"followed user {user_to_follow}")
                }, status=201)
            # good unfollow request
            if data['intent'] == 'unfollow' and user_to_follow in user.following.all():
                print("you are currently following this user")
                user.following.remove(user_to_follow)
                return JsonResponse({
                    "message": _(f"unfollowed user {user_to_follow}")
                }, status=201)
            # We reach this page if the intent does not match the current follow status
            return JsonResponse({
                "error": _("follow intent does not match current follow state")
            }, status=400)
    # user did not make a put request
    else:
        return JsonResponse({
            "error": _("PUT request required.")
        }, status=400)


@csrf_protect
def like(request, post_id):
    if request.method == "PUT":
        data = json.loads(request.body)
        user = request.user
        post = utils.get_post_from_id(request, post_id)
        if data['like'] == True:
            if user in post.author.blocked_users.all() or post.author in user.blocked_users.all():
                return JsonResponse({
                    "error": _("You cannot like this post because there is a block relationship.")
                }, status=400)
            user.liked_posts.add(post)
            return JsonResponse({
                "message": _("Post liked successfully"),
                "post_id": post_id,
                "is_liked": True,
                "like_count": post.users_who_liked.count(),
                }, status=201)
        elif data['like'] == False:
            user.liked_posts.remove(post)
            return JsonResponse({
                "message": _("Post unliked successfully"),
                "post_id": post_id,
                "is_liked": False,
                "like_count": post.users_who_liked.count(),
                }, status=201)
    else:
        print("ERROR please only come here via PUT")
        return JsonResponse({
            "error": _("PUT request required.")
        }, status=400)


@csrf_protect
def notifications(request):
    """checks for notifications
    * for both logged in and non logged in users:
        * new posts in the current view
    * only for logged in users:
        * new mentions
        * new DMs

    expects a json object in the request. that object should contain a 'context' variable. inside that variable:
        'location': can be 'public_feed', 'user', or 'following' (can add more later for different views)
        if 'location' == 'user':
            'username': the username of the user who we are checking for new posts

    Returns a JsonResponse with the following fields:
        'new_post_count': the number of new posts in the current view
        'new_mention_count': the number of new mentions (only for logged in users)
        'new_dm_count': the number of new DMs (only for logged in users)
    """
    if request.method == "PUT":
        data = json.loads(request.body)
        datetime_obj = utils.convert_javascript_date_to_python(data['timestamp'])
        new_post_count = utils.get_post_count_since_timestamp(request, datetime_obj, data['context'])
        user = request.user
        if user.is_authenticated:
            print("user authenticated :)")
            new_mention_count = user.mentions_since_last_checked
            new_dm_count = user.DMs_since_last_checked
            return JsonResponse({
                "new_post_count": new_post_count,
                "new_mention_count": new_mention_count,
                "new_dm_count": new_dm_count,
                }, status=200)
        return JsonResponse({
            "new_post_count": new_post_count,
            }, status=200)
    else:
        return JsonResponse({
            "error": _("GET request required.")
            }, status=400)


@csrf_protect
def reply(request, post_id):
    print(request.headers)
    if request.method == "PUT":
        data = json.loads(request.body)
        text = data["text"]
        user = request.user
        post = utils.get_post_from_id(request, post_id)
        # check for a block relationship
        if user in post.author.blocked_users.all() or post.author in user.blocked_users.all():
            return JsonResponse({
                "error": _("You cannot reply to this post because there is a block relationship.")
            }, status=400)
        reply = Post(author=user, text=text, reply_to=post)
        reply.save()
        mentioned_users = utils.get_mentions_from_post(text)
        for user in mentioned_users:
            reply.mentioned_users.add(user)
        # this is the reply count that updates on the website, for the post that is being replied to
        reply_count = post.replies.count()
        return JsonResponse({
            "reply_count": reply_count,
        }, status=201)
    else:
        return JsonResponse({
            "error": _("PUT request required.")
        }, status=400)


@csrf_protect
def thread_read_status(request, thread_id):
    """marks all unread DMs in a thread as read"""
    if request.method == "PUT":
        thread = Conversation.objects.get(id=thread_id)
        # TODO make sure the user is actually in the thread
        try:
            for message in thread.messages.all():
                if message.recipient == request.user and message.is_read == False:
                    message.is_read = True
                    message.save()
            return JsonResponse({
                "message": _("All posts marked as read")
            }, status=201)
        except Exception:
            return JsonResponse({
                "error": _("Error setting thread to read")
            }, status=500)
    else:
        return JsonResponse({
            "error": _("PUT request required")
        }, status=400)