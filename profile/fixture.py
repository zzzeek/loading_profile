"""ORM fixtures.

This module presents a DSL for generating ORM models with a particular
nesting structure as well as object counts.

Such as, to produce a model where parent objects have a one-to-many
relationship to a child class, and then that child class has a many-to-one
relationship to a sub-child class, specifying 20 parent objects with 10 child
objects each::

    model = objects(20).onetomany(10, 'select').manytoone().root

    e = create_engine("sqlite://", echo=True)

    # generate tables and mappings, produce 20 * (10 + 1) = 220 rows:
    o.setup(e)

    # select all 20 parent objects, traverse into each 10 subrows
    # and each single sub-subrow from there
    o.traverse(e)

The model created by the above looks like::

    class A(Base):
        __tablename__ = 'a'
        id = Column(Integer, primary_key=True)
        data = Column(String(200))
        b1s = relationship("B", lazy='select')

    class AB1(Base):
        __tablename__ = 'ab1'
        id = Column(Integer, primary_key=True)
        data = Column(String(200))

        a_id = Column(Integer, ForeignKey('a.id'))
        c1_id = Column(Integer, ForeignKey('ab1c1.id'))

        c1 = relationship("C", lazy='select')

    class AB1C1(Base):
        __tablename__ = 'ab1c1'
        id = Column(Integer, primary_key=True)
        data = Column(String(200))

A model can have any number of relationships set up::

    model = objects(20)
    model.onetomany(10, 'select')
    model.onetomany(20, 'select').onetomany(20, 'select')

The "strategy" argument specifies the type of collection/related-object
loading which should be applied: 'select', 'joined', 'subquery', or
'akiban_nested'.


"""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Session
from sqlalchemy.ext.declarative import declarative_base, declared_attr
import itertools
import collections

class objects(object):
    @classmethod
    def _base(cls):
        class Base(object):
            @declared_attr
            def __tablename__(cls):
                return cls.__name__.lower()

            id = Column(Integer, primary_key=True)
            data = Column(String(200))

        Base = declarative_base(cls=Base)
        return Base

    def __init__(self, count, _parent=None, _name="A"):
        self.count = count
        self.parent = _parent
        self.id_seq = itertools.count(1)

        if self.parent is None:
            self.base = self._base()
            self.letters = collections.defaultdict(int)
        else:
            self.base = self.parent.base

        self.name = _name
        self.klass = type(self.name, (self.base,), {})
        self.children = collections.OrderedDict()
        self.strategy = 'select'

    def __str__(self):
        return self._str("")

    def _str(self, indent):
        has_children = bool(self.children)
        text = ""
        if self.parent:
            text += indent + "|\n"
            text += indent + "+-> %s -> " % (self.__class__.__name__)
            text += "%s (%d rows each, %s loading)" % (
                        self.name,
                        self.count,
                        self.strategy
                    )
        else:
            text += "%s (%d rows)" % (
                        self.name,
                        self.count
                    )
        if has_children:
            text += "\n"
            indent += "    "
            for k, v in self.children.items():
                text += v._str(indent)
        else:
            text += "\n"
        return text

    def manytoone(self, strategy):
        return manytoone(self, strategy)

    def onetomany(self, strategy, count):
        return onetomany(self, strategy, count)

    @property
    def root(self):
        p = self
        while p.parent is not None:
            p = p.parent
        return p

    def _new_instance(self, index, parent_obj=None):
        data = "%s(%d)" % (self.name, index)
        if parent_obj:
            data = parent_obj.data + "_" + data
        return self.klass(id=self.id_seq.next(), data=data)

    def traverse(self, engine):
        assert not self.parent, "Can only call traverse() from the root."
        s = Session(engine)
        try:
            for obj in s.query(self.klass):
                for child in self.children.values():
                    child._traverse(obj)
        finally:
            s.close()

    def setup(self, engine):
        assert not self.parent, "Can only call setup() from the root."
        self.base.metadata.create_all(engine)
        s = Session(engine)
        try:
            for i in xrange(self.count):
                obj = self._new_instance(1)
                for child_cls in self.children.values():
                    child_cls._setup(obj)
                s.add(obj)
                s.flush()
            s.commit()
        finally:
            s.close()

    def teardown(self, engine):
        assert not self.parent, "Can only call teardown() from the root."
        self.base.metadata.drop_all(engine)

class _related(objects):
    def __init__(self, parent, strategy, count):
        letter = chr(ord(parent.name[0]) + 1)
        number = parent.root.letters[letter] + 1
        parent.root.letters[letter] = number
        name = "%s%d" % (letter, number)

        super(_related, self).__init__(count, _parent=parent, _name=name)
        self.strategy = strategy
        self.parent = parent

        self._setup_foreign_key()
        setattr(parent.klass, self.relationship_name,
                relationship(self.klass, lazy=self.strategy, innerjoin=True))
        parent.children[self.name] = self

class manytoone(_related):
    def __init__(self, parent, strategy):
        super(manytoone, self).__init__(parent, strategy, 1)

    def _setup(self, parent_obj):
        obj = self._new_instance(1, parent_obj)
        setattr(
            parent_obj,
            self.relationship_name,
            obj
        )
        for child_cls in self.children.values():
            child_cls._setup(obj)

    def _traverse(self, parent_obj):
        obj = getattr(parent_obj, self.relationship_name)
        for child in self.children.values():
            child._traverse(obj)

    @property
    def relationship_name(self):
        return self.name.lower()

    def _setup_foreign_key(self):
        setattr(
                self.parent.klass,
                self.name.lower() + "_id",
                Column(Integer,
                        ForeignKey("%s.id" % self.name.lower()),
                        nullable=False
                )
        )

class onetomany(_related):

    def _setup(self, parent_obj):
        collection = getattr(parent_obj, self.relationship_name)
        for i in xrange(self.count):
            collection.append(self._new_instance(i + 1, parent_obj))
        for obj in collection:
            for child_cls in self.children.values():
                child_cls._setup(obj)

    def _traverse(self, parent_obj):
        collection = getattr(parent_obj, self.relationship_name)
        for obj in collection:
            for child in self.children.values():
                child._traverse(obj)

    @property
    def relationship_name(self):
        return self.name.lower() + "s"

    def _setup_foreign_key(self):
        setattr(
                self.klass,
                self.parent.name.lower() + "_id",
                Column(Integer,
                        ForeignKey("%s.id" % self.parent.name.lower()),
                        nullable=False
                )
        )

