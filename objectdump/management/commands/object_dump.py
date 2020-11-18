import pprint
from itertools import chain
from optparse import make_option
from collections import defaultdict, Iterable
from django.db import DEFAULT_DB_ALIAS

from django.core.exceptions import FieldError, ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db.models import ForeignKey
from django.apps import apps
from django.db import models
from django.template import Variable

from ...models import (
    get_key,
    get_reverse_relations,
    get_many_to_many,
    ObjectFilter,
)
# If importing MODEL_SETTINGS directly, the tests can't update the settings between tests.
from ... import settings
from ...serializer import get_serializer
from ...diagram import make_dot


def get_fields():
    """
    Return two dicts: the configured "fields" and "exclude" for all models
    """
    fields = {}
    excluded_fields = {}
    for key, val in settings.MODEL_SETTINGS.items():
        if "fields" in settings.MODEL_SETTINGS[key]:
            fields[key] = settings.MODEL_SETTINGS[key]["fields"]
        if "exclude" in settings.MODEL_SETTINGS[key]:
            excluded_fields[key] = settings.MODEL_SETTINGS[key]["exclude"]
    return fields, excluded_fields

def get_all_field_names(obj):
    return list(set(chain.from_iterable(
        (field.name, field.attname) if hasattr(field, 'attname') else (field.name,)
        for field in obj._meta.get_fields()
        # For complete backwards compatibility, you may want to exclude
        # GenericForeignKey from the results.
        if not (field.many_to_one and field.related_model is None)
    )))

class Command(BaseCommand):
    help = ("Output the contents of one or more objects and their related "
            "items as a fixture of the given format.")
    args = "app_name.model_name [id1 [id2 [...]]]"

    def add_arguments(self, parser):
        parser.add_argument("model", nargs="+")
        parser.add_argument(
            "--format",
            default="json",
            dest="format",
            help="Specifies the output serialization format for fixtures.",
        )
        parser.add_argument(
            "--indent",
            default=None,
            dest="indent",
            type=int,
            help="Specifies the indent level to use when pretty-printing output",
        )
        parser.add_argument(
            "--database",
            action="store",
            dest="database",
            default=DEFAULT_DB_ALIAS,
            help="Nominates a specific database to dump "
            'fixtures from. Defaults to the "default" database.',
        )
        parser.add_argument(
            "-e",
            "--exclude",
            dest="exclude",
            action="append",
            default=[],
            help="An appname or appname.ModelName to exclude (use multiple "
            "--exclude to exclude multiple apps/models).",
        )
        parser.add_argument(
            "-n",
            "--natural",
            action="store_true",
            dest="use_natural_keys",
            default=False,
            help="Use natural keys if they are available.",
        )
        parser.add_argument(
            "--depth",
            dest="depth",
            default=None,
            type=int,
            help="Max depth related objects to get",
        )
        parser.add_argument(
            "--limit",
            dest="limit",
            default=None,
            type=int,
            help="Max number of related objects to get",
        )
        parser.add_argument(
            "--include",
            "-i",
            dest="include",
            action="append",
            default=[],
            help="An appname or appname.ModelName to whitelist related objects "
            "included in the export (use multiple --include to include "
            "multiple apps/models).",
        )
        parser.add_argument(
            "--idtype",
            dest="idtype",
            default="int",
            help="The natural type of the id(s) specified. [int, unicode, long]",
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            dest="debug",
            default=False,
            help="Output debug information. Shows what additional objects each object generates.",
        )
        parser.add_argument(
            "--modeldiagram",
            dest="modeldiagram",
            default=None,
            type=str,
            help="Output a GraphViz (.dot) diagram of the model dependencies to the passed filepath.",
        )
        parser.add_argument(
            "--objdiagram",
            dest="objdiagram",
            default=None,
            type=str,
            help="Output a GraphViz (.dot) diagram of the object dependencies to the passed filepath.",
        )

    def process_additional_relations(self, obj, limit=None):
        key = ".".join([obj._meta.app_label, obj._meta.model_name])
        addl_relations = settings.MODEL_SETTINGS.get(key, {}).get('addl_relations', [])
        output = []
        obj_key = get_key(obj, include_pk=self.use_obj_key)
        add_dependency = False
        for rel in addl_relations:
            if callable(rel):
                rel_objs = rel(obj)
                add_dependency = getattr(rel, 'depends_on_obj', False)
            else:
                add_dependency = False
                rel_objs = Variable("object.%s" % rel).resolve({'object': obj})
            if not rel_objs:
                continue
            if not isinstance(rel_objs, Iterable):
                rel_objs = [rel_objs]
            for rel_obj in rel_objs:
                rel_key = get_key(rel_obj, include_pk=self.use_obj_key)
                if add_dependency:
                    self.depends_on[rel_obj].add(obj)
                    self.relationships[obj_key][rel.__name__].add(rel_key)
                self.generates[obj_key].add(rel_key)
                if self.verbose:
                    pprint.pprint("%s.%s -> %s" % (obj_key, rel, rel_key),
                        stream=self.stderr)
                output.append(rel_obj)
        return output

    def process_related_fields(self, obj, limit=None, obj_filter=None):
        related_fields = get_reverse_relations(obj)
        output = []
        obj_key = get_key(obj, include_pk=self.use_obj_key)
        key = ".".join([obj._meta.app_label, obj._meta.model_name])
        m2m_fields = settings.MODEL_SETTINGS.get(key, {}).get('reverse_relations', related_fields)
        # m2m_fields could be True for all, False for none, or an iterable for
        # some of the m2m_fields
        if m2m_fields is True:
            m2m_fields = related_fields
        elif m2m_fields is False:
            m2m_fields = []
        for rel in m2m_fields:
            try:
                related_objs = obj.__getattribute__(rel)
                if related_objs is None:
                    raise ObjectDoesNotExist()
                # handle OneToOneField case for related object
                if isinstance(related_objs, models.Model):
                    related_objs = [related_objs]
                else:  # everything else uses a related manager
                    related_objs = related_objs.all()

                if limit:
                    related_objs = related_objs[:limit]
                for rel_obj in related_objs:
                    if obj_filter is not None and obj_filter.skip(rel_obj):
                        continue
                    rel_key = get_key(rel_obj, include_pk=self.use_obj_key)
                    self.generates[obj_key].add(rel_key)
                    if self.verbose:
                        pprint.pprint("%s.%s -> %s" % (obj_key, rel, rel_key),
                                      stream=self.stderr)
                    output.append(rel_obj)
            except (FieldError, ObjectDoesNotExist):
                pass
        return output

    def process_many2many(self, obj, limit=None, obj_filter=None):
        output = []
        obj_key = get_key(obj, include_pk=self.use_obj_key)
        key = ".".join([obj._meta.app_label, obj._meta.model_name])
        related_fields = get_many_to_many(obj)
        m2m_fields = settings.MODEL_SETTINGS.get(key, {}).get('m2m_fields', related_fields)

        # m2m_fields could be True for all, False for none, or an iterable for
        # some of the m2m_fields
        if m2m_fields is True:
            m2m_fields = related_fields
        elif m2m_fields is False:
            m2m_fields = []
        for rel in m2m_fields:
            try:
                related_objs = obj.__getattribute__(rel)
                related_objs = related_objs.all()

                if limit:
                    related_objs = related_objs[:limit]
                for rel_obj in related_objs:
                    if obj_filter is not None and obj_filter.skip(rel_obj):
                        continue
                    rel_key = get_key(rel_obj, include_pk=self.use_obj_key)
                    self.depends_on[obj].add(rel_obj)
                    self.relationships[obj_key][rel].add(rel_key)
                    self.generates[obj_key].add(rel_key)
                    if self.verbose:
                        pprint.pprint("%s.%s -> %s" % (obj_key, rel, rel_key),
                                      stream=self.stderr)
                    output.append(rel_obj)
            except (FieldError, ObjectDoesNotExist):
                pass
        return output

    def process_foreignkeys(self, obj, obj_filter=None):
        output = []
        obj_key = get_key(obj, include_pk=self.use_obj_key)
        key = ".".join([obj._meta.app_label, obj._meta.model_name])
        all_field_names = get_all_field_names(obj)
        fk_fields = settings.MODEL_SETTINGS.get(key, {}).get('fk_fields', all_field_names)
        # fk_fields could be True for all, False for none, or an iterable for
        # some of the m2m_fields
        if fk_fields is True:
            fk_fields = all_field_names
        elif fk_fields is False:
            fk_fields = []
        for field in obj._meta.fields:
            if isinstance(field, ForeignKey) and field.name in fk_fields:
                try:
                    fk_obj = obj.__getattribute__(field.name)
                    if fk_obj and obj_filter is not None and not obj_filter.skip(fk_obj):
                        fk_key = get_key(fk_obj, include_pk=self.use_obj_key)
                        self.depends_on[obj].add(fk_obj)
                        self.relationships[obj_key][field.name].add(fk_key)
                        self.generates[obj_key].add(fk_key)
                        if self.verbose:
                            pprint.pprint("%s.%s -> %s" % (obj_key, field.name, fk_key),
                                          stream=self.stderr)
                        output.append(fk_obj)
                except TypeError as e:
                    print("Error processing FK:", e, obj, field.name)
        return output

    # TODO Port over to Python 3 as well
    def process_genericforeignkeys(self, obj, obj_filter=None):
        output = []
        obj_key = get_key(obj, include_pk=self.use_obj_key)
        key = ".".join([obj._meta.app_label, obj._meta.model_name])
        all_field_names = [x.name for x in obj._meta.private_fields]
        gfk_fields = settings.MODEL_SETTINGS.get(key, {}).get("gfk_fields", all_field_names)
        if gfk_fields is True:
            gfk_fields = all_field_names
        elif gfk_fields is False:
            gfk_fields = []
        for field in obj._meta.private_fields:
            if field.name in gfk_fields:
                try:
                    gfk_obj = obj.__getattribute__(field.name)
                    if (
                        gfk_obj
                        and obj_filter is not None
                        and not obj_filter.skip(gfk_obj)
                    ):
                        gfk_key = get_key(gfk_obj, include_pk=self.use_obj_key)
                        self.depends_on[obj].add(gfk_obj)
                        self.relationships[obj_key][field.name].add(gfk_key)
                        self.generates[obj_key].add(gfk_key)
                        if self.verbose:
                            pprint.pprint(
                                "%s.%s -> %s" % (obj_key, field.name, gfk_key),
                                stream=self.stderr,
                            )
                        output.append(gfk_obj)
                except TypeError:
                    print("Error getting GFK %s" % field.name)
        return output

    def process_object(self, obj, obj_filter=None):
        # Abort cyclic references.
        if obj._meta.proxy:
            obj = obj._meta.proxy_for_model.objects.get(pk=obj.pk)

        if obj in self.priors:
            return
        self.priors.add(obj)

        if obj_filter is not None and obj_filter.skip(obj):
            return

        obj_key = get_key(obj, include_pk=self.use_obj_key)
        self.to_serialize.append(obj)
        if obj not in self.depends_on:
            self.depends_on[obj] = set()
        return obj_key

    def process_queue(self, objs, obj_filter=None, limit=None, max_depth=None):
        """
        Generate a list of objects to serialize
        """
        self.depends_on = defaultdict(set)  # {key: set(keys being pointed to)}
        self.relationships = defaultdict(lambda: defaultdict(set))  # {key: {'field': set(objs)}}
        self.generates = defaultdict(set)
        self.to_serialize = []

        # Recursively serialize all related objects.
        self.priors = set()
        _queue = list(objs)

        self.queue = list(zip(_queue, [0] * len(_queue)))  # queue is obj, depth
        while self.queue:
            obj, depth = self.queue.pop(0)
            obj_key = self.process_object(obj, obj_filter)
            if obj_key is None:
                continue

            if max_depth is None or depth <= max_depth:
                rel_objs = self.process_related_fields(obj, limit, obj_filter)
                for rel in rel_objs:
                    self.queue.append((rel, depth + 1))
                rel_objs = self.process_many2many(obj, limit, obj_filter)
                for rel in rel_objs:
                    self.queue.append((rel, depth + 1))
            addl_rel_objs = self.process_additional_relations(obj)
            for ar_obj in addl_rel_objs:
                self.queue.append((ar_obj, depth + 1))
            fk_objs = self.process_foreignkeys(obj, obj_filter)
            for fk_obj in fk_objs:
                self.queue.append((fk_obj, depth + 1))
            # TODO port to Python 3
            gfk_objs = self.process_genericforeignkeys(obj, obj_filter)
            for gfk_obj in gfk_objs:
                self.queue.append((gfk_obj, depth + 1))

    def handle(self, *args, **options):
        format = options.get('format')
        indent = options.get('indent')
        using = options.get('database')
        excludes = options.get('exclude')
        includes = options.get('include')
        show_traceback = options.get('traceback')
        use_natural_keys = options.get('use_natural_keys')
        max_depth = options.get("depth")
        limit = options.get("limit")
        debug = options.get("debug")
        model_diagram_file = options.get("modeldiagram")
        object_diagram_file = options.get("objdiagram")

        SerializerClass = get_serializer(format)()  # NOQA
        self.use_gfks = hasattr(SerializerClass, 'handle_gfk_field')
        if model_diagram_file and object_diagram_file:
            raise CommandError("You can't generate a model diagram and an object diagram at the same time.")
        self.use_obj_key = model_diagram_file is None
        self.verbose = int(options.get('verbosity')) > 1
        id_cast = {
            'int': int,
        }[options.get('idtype')]

        args = options["model"]

        if len(args) < 1:
            raise CommandError('You must specify the model.')
        if "." not in args[0]:
            raise CommandError('You must specify the model as "appname.modelname".')

        main_model = args[0]
        app_label, model_name = main_model.split('.')
        primary_model = apps.get_model(app_label, model_name)
        obj_filter = ObjectFilter(primary_model, excludes, includes)

        ids = [id_cast(i) for i in args[1:]]

        # Lookup initial model records.
        if ids:
            objs = primary_model.objects.using(using).filter(pk__in=ids).iterator()
        else:
            objs = primary_model.objects.using(using).iterator()

        self.process_queue(objs, obj_filter, limit, max_depth)

        # Order serialization so that dependents come after dependencies.
        depends_on = dict(self.depends_on)
        from ...topological_sort import toposort
        serialization_order = toposort(depends_on)
        try:
            try:
                self.stdout.ending = None
            except AttributeError:
                pass
            if debug:
                pprint.pprint("----------------------------------------------", stream=self.stderr)
                pprint.pprint("Which models cause which others to be included", stream=self.stderr)
                pprint.pprint("----------------------------------------------", stream=self.stderr)
                pprint.pprint(dict(self.generates), stream=self.stderr)
                pprint.pprint("----------------------------------------------", stream=self.stderr)
                pprint.pprint("Dependencies", stream=self.stderr)
                pprint.pprint("----------------------------------------------", stream=self.stderr)
                for model, fields in sorted(self.relationships.items()):
                    pprint.pprint(model, stream=self.stderr)
                    for field, items in sorted(fields.items()):
                        pprint.pprint("     %s" % field, stream=self.stderr)
                        for item in items:
                            pprint.pprint("         %s" % item, stream=self.stderr)
                pprint.pprint("----------------------------------------------", stream=self.stderr)
                pprint.pprint("Serialization order", stream=self.stderr)
                pprint.pprint("----------------------------------------------", stream=self.stderr)
                pprint.pprint(list(serialization_order), stream=self.stderr)
                return
            if model_diagram_file:
                make_dot(self.relationships, model_diagram_file)
            elif object_diagram_file:
                make_dot(self.relationships, object_diagram_file)
            to_serialize = [o for o in list(serialization_order) if o is not None]
            if self.verbose:
                pprint.pprint(to_serialize, stream=self.stderr)
            fields, excluded = get_fields()
            SerializerClass.serialize(
                to_serialize,
                indent=indent,
                use_natural_keys=use_natural_keys,
                stream=self.stdout,
                fields=fields,
                exclude_fields=excluded)
        except Exception as e:
            if show_traceback:
                raise
            raise CommandError("Unable to serialize database: %s" % e)
