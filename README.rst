==================
Django Object Dump
==================

Installation
============

#. Installation is easy using ``pip``\ .

   .. code-block:: bash

      $ pip install django-objectdump

#. Add to ``INSTALLED_APPS``

#. Optionally add configuration information (``OBJECTDUMP_SETTINGS``\ )


Settings
========

.. code-block:: python

   OBJECTDUMP_SETTINGS = {
       'MODEL_SETTINGS': {
           'app.model': {
               'ignore': False,
               'fk_fields': True,  # or False, or ['whitelist', 'of', 'fks']
               'm2m_fields': True,  # or False, or ['whitelist', 'of', 'm2m fields']
               'addl_relations': []  # additional relations, callable or 'othermodel_set.all' strings
           }
       }
   }


``ignore``
    If ``True``\ , always ignore this model. Acts as if you used ``--exclude`` with this model.

``fk_fields``
    If ``False``\ , do not include related objects through foreign keys. Otherwise, a white-list of foreign keys to include related objects.

``m2m_keys``
    If ``False``\ , do not include related objects through many-to-many fields. Otherwise, a white-list of many-to-many field names to include related objects.

``addl_relations``
    Additional relations, a list of callables, which get passed an object, or strings in Django template syntax (``'author_set.all.0'`` becomes ``'object.author_set.all.0'`` and evaluates to ``object.author_set.all()[0]``\ )

Options
=======

``--format``
    **Default:** ``json``

    Specifies the output serialization format for fixtures. Options depend on ``SERIALIZATION_MODULES`` settings. ``xml`` and ``json`` and ``yaml`` are built-in.

``--indent``
    **Default:** ``None``

    Specifies the indent level to use. The default will not do any pretty-printing or indenting of content.

``--database``
    **Default:** ``DEFAULT_DB_ALIAS``

    Nominates a specific database to dump fixtures from. Defaults to the "default" database.

``-e``\ , ``--exclude``
    **Default:** ``[]``

    An appname or appname.ModelName to exclude (use multiple ``--exclude`` to exclude multiple apps/models).

``-n``\ , ``--natural``
    **Default:** ``False``

    Use natural keys if they are available.

``--depth``
    **Default:** ``None``

    Max depth related objects to get. The initial object specified is considered level 0. The default will get all objects.

``--limit``
    **Default:** ``None``

    Max number of related objects to get. Default gets all related objects.

``-i``\ , ``--include``
    **Default:** all

    An appname or appname.ModelName to whitelist related objects included in the export (use multiple ``--include`` to include multiple apps/models).

``--idtype``
    **Default:** ``'int'``

    The natural type of the id(s) specified. Options are: ``int``, ``unicode``, ``long``

``--nocycle``
    **Default:** ``False``

    If True, will fail on any cyclic foreign key dependencies. Cyclic dependencies are usually fine in fixtures because the "loaddata" command temporarily disables the FK constraints.

``--debug``
    **Default:** ``False``

    Output debug information. Shows what related objects each object generates. Use with ``--verbosity 2`` to also see which fields are the link.

Demo app and tests
=======

To setup the demo app:
```
cd examples

[setup your virtual env, eg. virtualenv -p /usr/bin/python3.7 .venv]

pip install -r requirements.txt

./manage.py migrate

./manage.py createsuperuser

./manage.py runserver

```

You can now visit: http://localhost:8000/admin


To run the tests:
```
./manage.py test
```

