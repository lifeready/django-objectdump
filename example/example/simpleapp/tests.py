import datetime
import json
from io import StringIO

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from objectdump import settings

from .models import (Article, Author, AuthorProfile, Category, Tag,
                     TaggedArticle, TaggedItem)


def get_tagged_items(obj):
    items = TaggedItem.objects.filter(
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk)
    return items

class Utc(datetime.tzinfo):
    """UTC

    """
    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return datetime.timedelta(0)
UTC = Utc()

class ObjectDumpTestCase(TestCase):
    def setUp(self):
        self.c1 = Category.objects.create(name="World")
        self.c2 = Category.objects.create(name="Nation")
        self.c3 = Category.objects.create(name="State")
        self.a1 = Author.objects.create(name="Obi Wan")
        self.a2 = Author.objects.create(name="Luke")
        self.a3 = Author.objects.create(name="Leia")
        self.ap1 = AuthorProfile.objects.create(author=self.a1, date_of_birth=datetime.date(1970, 1, 1))
        self.ap2 = AuthorProfile.objects.create(author=self.a2, date_of_birth=datetime.date(1980, 1, 1))
        self.ap3 = AuthorProfile.objects.create(author=self.a3, date_of_birth=datetime.date(1980, 1, 1))
        self.ar1 = Article.objects.create(author=self.a1, headline="Stars at war", pub_date=datetime.datetime(2013, 1, 1, 12, 0, 0, 0, UTC))
        self.ar1.categories.add(self.c1)
        self.ar2 = Article.objects.create(author=self.a2, headline="Underdogs could win it all", pub_date=datetime.datetime(2013, 1, 1, 12, 0, 0, 0, UTC))
        self.ar2.categories.add(self.c2)
        self.ar3 = Article.objects.create(author=self.a3, headline="Princess fashion", pub_date=datetime.datetime(2013, 1, 1, 12, 0, 0, 0, UTC))
        self.ar3.categories.add(self.c3)

    def test_serialization(self):
        output = StringIO()
        ADDITIONAL_RELATIONS = {'simpleapp.article': []}
        settings.ADDITIONAL_RELATIONS = ADDITIONAL_RELATIONS
        call_command("object_dump", "simpleapp.article", "1", stdout=output)
        ar1_output = '[{"model": "simpleapp.author", "pk": 1, "fields": {"name": "Obi Wan"}}, {"model": "simpleapp.category", "pk": 1, "fields": {"name": "World"}}, {"model": "simpleapp.article", "pk": 1, "fields": {"author": 1, "headline": "Stars at war", "pub_date": "2013-01-01T12:00:00Z", "categories": [1]}}, {"model": "simpleapp.authorprofile", "pk": 1, "fields": {"date_of_birth": "1970-01-01"}}]'

        result = output.getvalue()
        self.assertEquals(json.loads(ar1_output), json.loads(result))


class CommonObjectDumpTestCase(TestCase):
    def setUp(self):
        self.c1 = Category.objects.create(name="World")
        self.c2 = Category.objects.create(name="Nation")
        self.c3 = Category.objects.create(name="State")
        self.a1 = Author.objects.create(name="Obi Wan")
        self.a2 = Author.objects.create(name="Luke")
        self.a3 = Author.objects.create(name="Leia")
        self.t1 = Tag.objects.create(name="Star")
        self.t2 = Tag.objects.create(name="War")
        self.t3 = Tag.objects.create(name="Fashion")
        self.ap1 = AuthorProfile.objects.create(author=self.a1, date_of_birth=datetime.date(1970, 1, 1))
        self.ap2 = AuthorProfile.objects.create(author=self.a2, date_of_birth=datetime.date(1980, 1, 1))
        self.ap3 = AuthorProfile.objects.create(author=self.a3, date_of_birth=datetime.date(1980, 1, 1))
        self.ar1 = TaggedArticle.objects.create(author=self.a1, headline="Stars at war", pub_date=datetime.datetime(2013, 1, 1, 12, 0, 0, 0, UTC))
        self.ar1.categories.add(self.c1)
        self.ti1 = TaggedItem.objects.create(tag=self.t1, content_object=self.ar1)
        self.ti2 = TaggedItem.objects.create(tag=self.t2, content_object=self.ar1)
        self.ar2 = TaggedArticle.objects.create(author=self.a2, headline="Underdogs could win it all", pub_date=datetime.datetime(2013, 1, 1, 12, 0, 0, 0, UTC))
        self.ar2.categories.add(self.c2)
        self.ti3 = TaggedItem.objects.create(tag=self.t1, content_object=self.ar2)
        self.ti4 = TaggedItem.objects.create(tag=self.t2, content_object=self.ar2)
        self.ar3 = TaggedArticle.objects.create(author=self.a3, headline="Princess fashion", pub_date=datetime.datetime(2013, 1, 1, 12, 0, 0, 0, UTC))
        self.ar3.categories.add(self.c3)
        self.ti5 = TaggedItem.objects.create(tag=self.t3, content_object=self.ar3)


class CustomObjectDumpTestCase(CommonObjectDumpTestCase):
    def test_serialization(self):
        output = StringIO()
        MODEL_SETTINGS = {
            'simpleapp.taggedarticle': {'addl_relations': [get_tagged_items]},
            'simpleapp.taggeditem': {'fk_fields': ['tag'], 'm2m_fields': False},
            'simpleapp.author': {'reverse_relations': ['authorprofile']},
            'simpleapp.tag': {'reverse_relations': False}
        }
        settings.MODEL_SETTINGS = MODEL_SETTINGS
        call_command("object_dump", "simpleapp.taggedarticle", "1", stdout=output)
        ar1_output = '[{"model": "simpleapp.author", "pk": 1, "fields": {"name": "Obi Wan"}}, {"model": "simpleapp.category", "pk": 1, "fields": {"name": "World"}}, {"model": "simpleapp.tag", "pk": 1, "fields": {"name": "Star"}}, {"model": "simpleapp.tag", "pk": 2, "fields": {"name": "War"}}, {"model": "simpleapp.authorprofile", "pk": 1, "fields": {"date_of_birth": "1970-01-01"}}, {"model": "simpleapp.taggedarticle", "pk": 1, "fields": {"author": 1, "headline": "Stars at war", "pub_date": "2013-01-01T12:00:00Z", "categories": [1]}}, {"model": "simpleapp.taggeditem", "pk": 1, "fields": {"tag": 1, "content_type": 13, "object_id": 1}}, {"model": "simpleapp.taggeditem", "pk": 2, "fields": {"tag": 2, "content_type": 13, "object_id": 1}}]'

        result = output.getvalue()
        self.assertEquals(json.loads(ar1_output), json.loads(result))

    def test_exclude(self):
        output = StringIO()

        MODEL_SETTINGS = {
            'simpleapp.taggedarticle': {'addl_relations': [get_tagged_items]},
            'simpleapp.taggeditem': {'fk_fields': False, 'm2m_fields': False, 'exclude': ['tag']},
            'simpleapp.author': {'reverse_relations': ['authorprofile']},
            'simpleapp.tag': {'reverse_relations': False}
        }
        settings.MODEL_SETTINGS = MODEL_SETTINGS
        call_command("object_dump", "simpleapp.taggedarticle", "1", stdout=output)
        ar1_output = '[{"model": "simpleapp.author", "pk": 1, "fields": {"name": "Obi Wan"}}, {"model": "simpleapp.category", "pk": 1, "fields": {"name": "World"}}, {"model": "simpleapp.authorprofile", "pk": 1, "fields": {"date_of_birth": "1970-01-01"}}, {"model": "simpleapp.taggedarticle", "pk": 1, "fields": {"author": 1, "headline": "Stars at war", "pub_date": "2013-01-01T12:00:00Z", "categories": [1]}}, {"model": "simpleapp.taggeditem", "pk": 1, "fields": {"object_id": 1}}, {"model": "simpleapp.taggeditem", "pk": 2, "fields": {"object_id": 1}}]'
        
        result = output.getvalue()
        self.assertEquals(json.loads(ar1_output), json.loads(result))

    # TODO is this test useful?
    # def test_debug(self):
    #     output = StringIO()
    #     from django.core.management import call_command

    #     from objectdump import settings
    #     MODEL_SETTINGS = {
    #         'simpleapp.taggedarticle': {'addl_relations': [get_tagged_items]},
    #         'simpleapp.taggeditem': {'fk_fields': ['tag'], 'm2m_fields': False},
    #         'simpleapp.author': {'reverse_relations': ['authorprofile']},
    #         'simpleapp.tag': {'reverse_relations': False}
    #     }
    #     settings.MODEL_SETTINGS = MODEL_SETTINGS
    #     call_command("object_dump", "simpleapp.taggedarticle", "1", debug=True, stdout=output, stderr=output)
    #     ar1_output = "{'simpleapp:author:1': set(['simpleapp:authorprofile:1']),\n 'simpleapp:authorprofile:1': set(['simpleapp:author:1']),\n 'simpleapp:taggedarticle:1': set(['simpleapp:author:1',\n                                   'simpleapp:category:1',\n                                   'simpleapp:taggeditem:1',\n                                   'simpleapp:taggeditem:2']),\n 'simpleapp:taggeditem:1': set(['simpleapp:tag:1']),\n 'simpleapp:taggeditem:2': set(['simpleapp:tag:2'])}\n" \
    #     '[<Author: Obi Wan>,\n <AuthorProfile: Profile of Obi Wan>,\n <Category: World>,\n <Tag: Star>,\n <Tag: War>,\n <TaggedArticle: Stars at war>,\n <TaggedItem: Tag: Star, Model: Stars at war>,\n <TaggedItem: Tag: War, Model: Stars at war>]\n'

    #     self.assertEquals(ar1_output, output.getvalue())
