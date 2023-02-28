from django.core.mail import send_mail
from django.shortcuts import render, get_object_or_404
from taggit.models import Tag

from .models import Post, Comment
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .forms import EmailPostForm, CommentForm, SearchForm
from decouple import config
from django.views.decorators.http import require_POST

from django.db.models import Count

from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank


def post_list(request, tag_slug=None):
    post_list = Post.published.all()
    tag = None
    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        post_list = post_list.filter(tags__in=[tag])
    # Pagination with 3 posts per page
    paginator = Paginator(post_list, 3)
    page_number = request.GET.get('page', 1)
    try:
        posts = paginator.page(page_number)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)
    context = {
        'posts': posts,
        'tag': tag,
    }
    return render(request, 'post/list.html', context)


def post_detail(request, year, month, day, post):
    post = get_object_or_404(
        Post,
        status=Post.Status.PUBLISHED,
        slug=post,
        publish__year=year,
        publish__month=month,
        publish__day=day)
    comments = post.comments.filter(active=True)
    form = CommentForm()
    post_tags_ids = post.tags.values_list('id', flat=True)
    similar_posts = Post.published.filter(tags__in=post_tags_ids). \
        exclude(id=post.id)
    similar_posts = similar_posts.annotate(same_tags=Count('tags')). \
                        order_by('-same_tags', '-publish')[:4]
    context = {
        'post': post,
        'comments': comments,
        'form': form,
        'similar_posts': similar_posts,
    }
    return render(request, 'post/detail.html', context)


def post_share(request, post_id):
    post = get_object_or_404(
        Post,
        id=post_id,
        status=Post.Status.PUBLISHED)
    form = EmailPostForm()
    sent = False
    if request.method == 'POST':
        form = EmailPostForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            post_url = request.build_absolute_uri(
                post.get_absolute_url())
            subject = f"{cd['name']} recommends you read {post.title}"
            message = f"Read {post.title} at {post_url}\n\n " \
                      f"{cd['name']}'s comments: {cd['comments']}"
            send_mail(subject, message, config('EMAIL_HOST_USER'), [cd['to']])
            sent = True
        else:
            form = EmailPostForm()

    context = {
        'post': post,
        'form': form,
        'sent': sent
    }
    return render(request, 'post/share.html', context)


@require_POST
def post_comment(request, post_id):
    post = get_object_or_404(
        Post,
        id=post_id,
        status=Post.Status.PUBLISHED,
    )
    comment = None
    form = CommentForm(data=request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.save()
    context = {
        'post': post,
        'form': form,
        'comment': comment,
    }
    return render(request, 'post/comment.html', context)


def post_search(request):
    form = SearchForm()
    query = None
    results = []
    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            search_vector = SearchVector('title', weight='A') + SearchVector('body', weight='B')
            search_query = SearchQuery(query)
            results = Post.published.annotate(
                search=search_vector, rank=SearchRank(search_vector, search_query)).filter(
                rank__gte=0.3).order_by('-rank')
    return render(request, 'post/search.html', {
        'form': form,
        'query': query,
        'results': results,
    })
