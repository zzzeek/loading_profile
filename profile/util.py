import re

def drop_all(engine):
    # this is a special drop all hardcoded to the workings of fixture.py,
    # since Akiban won't let us drop constraints separately

    from sqlalchemy.engine import reflection
    from sqlalchemy.schema import DropTable
    from sqlalchemy.sql import table

    inspector = reflection.Inspector.from_engine(engine)

    to_drop = set()
    for table_name in inspector.get_table_names():
        if re.match(r'[abcdefghijk]\d?', table_name):
            to_drop.add(table_name)

    for tname in reversed(sorted(to_drop)):
        engine.execute(DropTable(table(tname)))
