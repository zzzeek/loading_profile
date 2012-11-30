from . import fixture
from . import profiling
from . import util
from sqlalchemy import create_engine

def run(_fixture, engine):
    print "-" * 20
    print "Setting up..."
    print _fixture
    _fixture.setup(engine)
    try:
        print "Querying..."
        stats = profiling.profile_sql(e, lambda: _fixture.traverse(engine))
    finally:
        _fixture.teardown(engine)

    print stats


def shallow_wide_onetomany():
    for strategy in strategies:
#        if strategy == 'joined':
#            continue
        o = fixture.objects(20)
        o.onetomany(strategy, 30)
        o.onetomany(strategy, 30)
        o.onetomany(strategy, 30)
        yield o

def deep_narrow_onetomany():
    for strategy in strategies:
        o = fixture.objects(20)
        o.onetomany(strategy, 10).onetomany(strategy, 10).onetomany(strategy, 10)
        yield o


def deep_wide_onetomany():
    for strategy in strategies:
        if strategy == 'joined':
            continue
        o = fixture.objects(20)
        o1 = o.onetomany(strategy, 10)
        o2 = o.onetomany(strategy, 10)
        o3 = o.onetomany(strategy, 10)
        o1.onetomany(strategy, 5)
        o2.onetomany(strategy, 5)
        o3.onetomany(strategy, 5)
        yield o




e = create_engine("akiban+psycopg2://@localhost:15432/")

#e = create_engine("postgresql+psycopg2://scott:tiger@localhost/test")

util.drop_all(e)


if e.dialect.name == 'akiban':
    from sqlalchemy_akiban import orm
    strategies = ('select', 'joined', 'subquery', 'akiban_nested')
else:
    strategies = ('select', 'joined', 'subquery')

for fn in (shallow_wide_onetomany, deep_narrow_onetomany, deep_wide_onetomany):
    for _fixture in fn():
        run(_fixture, e)

