import json
from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse

from network.forms import EditAccountForm, NewPostForm, RegisterAccountForm, RegisterAccountStage2Form
from network.models import User, Post
from network import utils

# TODO temp imports remove later
from django.views.decorators.csrf import csrf_exempt, csrf_protect


# +-----------------------------------------+
# |        VIEWS THAT RETURN PAGES          |
# +-----------------------------------------+

@login_required
def account(request):
    user = request.user

    if request.method == "GET":
        return render(request, "network/account.html", {
            "form": EditAccountForm(instance = user)
    })
    if request.method == "POST":
        form = EditAccountForm(request.POST, request.FILES, instance = user)

        if form.is_valid():
            user = authenticate(
                request, 
                username=utils.get_user_from_id(request.user.id), 
                password=form.cleaned_data["password"]
            )
            if user is None:
                print("Exception during verification")
                return render(request, "network/account.html", {
                    "form": EditAccountForm(instance = utils.get_user_from_id(request.user.id)),
                    "message": "Invalid password."
                })
            print("verification successful, logged in as:", user)
            print(form.cleaned_data["username"])
            if utils.check_username_validity(form.cleaned_data["username"]) == False:
                user = utils.get_user_from_id(request.user.id) # dirty hack to clean the username field TODO refactor
                # return an EditAccountForm with the user's original information
                return render(request, "network/account.html", {
                    "form": EditAccountForm(instance = user),
                    "message": "Username is not valid."
                })

            # get new_password and new_pass_confirm from form
            # check if they are the same, if so change the password
            # if not, return an EditAccountForm with the user's original information
            # and a message saying the passwords don't match
            new_password = form.cleaned_data["new_password"]
            new_password_confirm = form.cleaned_data["new_password_confirm"]
            if new_password != new_password_confirm:
                return render(request, "network/account.html", {
                    "form": EditAccountForm(instance = user),
                    "message": "New passwords don't match."
                })
            if new_password != None and new_password != "":
                user.set_password(new_password)
                user.save()

            form.save()


        # form is not valid
        else:
            print(form.data)
            return render(request, "network/account.html", {
                "form": EditAccountForm(instance = user),
                "message": "Form data is invalid"
            })
        print("everything went good!")
        return render(request, "network/account.html", {
            "form": EditAccountForm(instance = utils.get_user_from_id(request.user.id))
        })


@login_required
def following(request):
    posts = utils.get_posts_from_followed_accounts(request)
    return render(request, "network/following.html", {
        "posts": posts,
    })


def index(request):
    """RETURNS THE INDEX PAGE"""
    posts = utils.get_posts(request)
    return render(request, "network/index.html", {
        "posts": posts,
        "new_post_form": NewPostForm(auto_id=True),
    })


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
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "network/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


@login_required
def mentions(request):
    user = request.user
    if request.method == "GET":
        return render(request, "network/mentions.html", {
            "posts": utils.get_posts_with_mention(request, user.username),
        })
    else:
        return HttpResponseRedirect(reverse("index"))


def post(request, id):
    post = utils.get_post_from_id(id)
    # TODO do something if it's a bad post
    return render(request, "network/post.html", {
        "post": post
    })


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
                "message": "Passwords must match.",
                "form": RegisterAccountForm(),
            })

        if not utils.check_username_validity(username):
            return render(request, "network/register.html", {
                "message": "Username is not valid.",
                "form": RegisterAccountForm(),
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.displayname = displayname
            user.save()
        except IntegrityError:
            return render(request, "network/register.html", {
                "message": "Username already taken.",
                "form": RegisterAccountForm(),
            })
        login(request, user)
        return HttpResponseRedirect(reverse("register2"))
    else:
        return render(request, "network/register.html", {
            "form": RegisterAccountForm()
        })


def register2(request):
    user = request.user
    print(user)
    if request.method == "GET":
        return render(request, "network/register2.html", {
            "form": RegisterAccountStage2Form(instance = user)
        })
    if request.method == "POST":
        form = EditAccountForm(request.POST, request.FILES or None, instance = user)
        if form.is_valid():
            # set the user's bio and avatar based on form data
            user.bio = form.cleaned_data['bio']
            user.avatar = form.cleaned_data['avatar']
            print(user.username)
            print(user.bio)
            print(user.avatar)
            user.save()
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "network/register2.html", {
                "form": RegisterAccountStage2Form(),
                "message": "Form data is invalid"
            })


def user(request, username):
    user = utils.get_user_from_username(username)
    request.view_user = user
    posts = utils.get_posts(request, username)
    return render(request, "network/user.html", {
        "view_user": user,
        "posts": posts,
        "new_post_form": NewPostForm(),
    })


# +-----------------------------------------+
# |        VIEWS THAT RETURN JSON           |
# +-----------------------------------------+
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
    form = NewPostForm(request.POST)
    if form.is_valid():
        post_text = form.cleaned_data["post_text"]
        if post_text == "":
            return JsonResponse({
                "message": "You can't submit an empty post"
            }, status=400)
        user=request.user
        mentioned_users = utils.get_mentions_from_post(post_text)
        post = Post(user=user, text=post_text)
        post.save()
        for user in mentioned_users:
            post.mentioned_users.add(user)
        return HttpResponseRedirect(request.headers['Referer'])
    else:
        return JsonResponse({
            "message": "Form data invalid"
        }, status=400)


@csrf_protect
def edit(request, post_id):
    if request.method == "PUT":
        data = json.loads(request.body)
        new_text = data['new_text']
        if len(new_text) > 500:
            return JsonResponse({
                "message": "Maximum post length is 500 characters",
                "edited": False,
            }, status=400)
        post = utils.get_post_from_id(post_id)
        if request.user == post.user:
            post.text = new_text
            post.save()
            return JsonResponse({
                "message": "Post edited successfully",
                "edited": True,
            }, status=201)
        else:
            return JsonResponse({
                "message": "You are not authorized to edit this post",
                "edited": False,
            }, status=400)


@csrf_protect
def follow(request, user_id):
    if request.method == "PUT":
        user = request.user
        # user is trying to follow themselves
        if user_id == user.id:
            return JsonResponse({
                "error": "You cannot follow your own account."
            }, status=400)
        else: 
            data = json.loads(request.body)
            user_to_follow = User.objects.get(id=user_id) 
            # good follow request
            if data['intent'] == 'follow' and user_to_follow not in user.following.all():
                print("You are not currently following this user")
                user.following.add(user_to_follow)
                return JsonResponse({
                    "message": f"followed user {user_to_follow}"
                }, status=201)
            # good unfollow request
            if data['intent'] == 'unfollow' and user_to_follow in user.following.all():
                print("you are currently following this user")
                user.following.remove(user_to_follow)
                return JsonResponse({
                    "message": f"unfollowed user {user_to_follow}"
                }, status=201)
            # We reach this page if the intent does not match the current follow status
            print("follow intent does not match current follow state")
            return JsonResponse({
                "error": "follow intent does not match current follow state"
            }, status=400)
    # user did not make a put request
    else:
        return JsonResponse({
            "error": "PUT request required."
        }, status=400)


@csrf_protect
def get_notifications(request):
    if request.method == "PUT":
        user = request.user
        if user == None:
            return JsonResponse({
                "error": "You are not logged in."
            }, status=400)
        # build a JSON response that contains any notifications
        # (for now just unread mentions, but might add more stuff ie DMs later)
        # maybe also a total count of notifications, for app badge etc?
        return JsonResponse({
            "mention_count": user.mentions_since_last_checked
        }, status=200)
    else:
        return JsonResponse({
            "error": "PUT request required."
        }, status=400)


@csrf_protect
def like(request, post_id):
    if request.method == "PUT":
        data = json.loads(request.body)
        user = request.user
        post = utils.get_post_from_id(post_id)
        if data['like'] == True:
            user.liked_posts.add(post)
            return JsonResponse({
                "message": "Post liked successfully",
                "post_id": post_id,
                "is_liked": True,
                "like_count": post.users_who_liked.count(),
                }, status=201)
        elif data['like'] == False:
            user.liked_posts.remove(post)
            return JsonResponse({
                "message": "Post unliked successfully",
                "post_id": post_id,
                "is_liked": False,
                "like_count": post.users_who_liked.count(),
                }, status=201)
    else:
        print("ERROR please only come here via PUT")
        return JsonResponse({
            "error": "PUT request required."
        }, status=400)


def new_posts(request):
    """checks for new post count
    expects a json object in the request. that object should contain a 'context' variable. inside that variable:
        'location': can be 'public_feed', 'user', or 'following' (can add more later for different views)
        if 'location' == 'user':
            'username': the username of the user who we are checking for new posts
    returns a JsonResponse with the key 'count' which is the new post count
    """
    if request.method == "PUT":
        data = json.loads(request.body)
        datetime_obj = utils.convert_javascript_date_to_python(data['timestamp'])
        new_post_count = utils.get_post_count_since_timestamp(request, datetime_obj, data['context'])
        return JsonResponse({
            "new_post_count": new_post_count,
        }, status=201)
    else:
        return JsonResponse({
            "error": "GET request required."
        }, status=400)
