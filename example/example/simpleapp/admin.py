# -*- coding: utf-8 -*-
from .models import Actor, Article, Author, AuthorProfile, Category, Tag, TaggedArticle, TaggedItem
from django.contrib import admin

def create_admin_cls(model_cls):
    return type(
        # Class name must be different for different types. So we let the
        # user to choose a unique class name.
        model_cls.__name__ + "Admin",
        (admin.ModelAdmin,),
        {},
    )

def register(model_cls):
    admin.site.register(model_cls, create_admin_cls(model_cls))
    

register(Category)
register(Author)
register(Tag)
register(TaggedItem)
register(Article)
register(TaggedArticle)
register(AuthorProfile)
register(Actor)
