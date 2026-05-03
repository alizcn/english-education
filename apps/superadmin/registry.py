from collections import OrderedDict


REGISTRY = OrderedDict()


class Resource:
    """Declarative config for a model managed by the superadmin.

    Subclass and decorate with @register('slug')."""
    model = None
    slug = ''
    label = ''
    label_singular = ''
    icon = '📋'
    section = 'Diğer'
    list_columns = ()      # iterable of (attr_or_callable, header)
    search_fields = ()     # ORM lookups, used with __icontains
    filters = ()           # iterable of (field_name, label) — only choice/bool/fk supported
    form_fields = None     # list of field names; None = all editable
    form_exclude = ()
    detail_extra = ()      # iterable of (attr_or_callable, label) shown after main fields
    order_by = ('-pk',)
    can_create = True
    can_edit = True
    can_delete = True
    select_related = ()
    prefetch_related = ()
    actions = ()           # iterable of dicts: {'url_name': ..., 'label': ..., 'pk_arg': bool}

    def get_queryset(self):
        qs = self.model._default_manager.all()
        if self.select_related:
            qs = qs.select_related(*self.select_related)
        if self.prefetch_related:
            qs = qs.prefetch_related(*self.prefetch_related)
        if self.order_by:
            qs = qs.order_by(*self.order_by)
        return qs

    def cell(self, obj, column):
        """Resolve a column descriptor to a display value for a row."""
        attr, _ = column
        if callable(attr):
            return attr(obj)
        if hasattr(self, attr) and callable(getattr(self, attr)):
            return getattr(self, attr)(obj)
        value = obj
        for part in attr.split('.'):
            if value is None:
                return ''
            value = getattr(value, part, '')
        if callable(value):
            value = value()
        return value


def register(slug):
    def deco(cls):
        cls.slug = slug
        if not cls.label:
            cls.label = cls.model._meta.verbose_name_plural.title()
        if not cls.label_singular:
            cls.label_singular = cls.model._meta.verbose_name.title()
        REGISTRY[slug] = cls
        return cls
    return deco


def get_resource(slug):
    cls = REGISTRY.get(slug)
    return cls() if cls else None


def grouped_resources():
    """Return resources grouped by section, preserving registration order."""
    sections = OrderedDict()
    for slug, cls in REGISTRY.items():
        sections.setdefault(cls.section, []).append((slug, cls))
    return sections
