"""Profiling functions.

Counts Python function calls.    Some filtering allows us to also
count how many statements are executed, how many rows/columns iterated.

"""

import cProfile
import os
import pstats
import time


def cprofiled(fn):
    filename = "_loaders.profile"

    cProfile.runctx('fn()', globals(), locals(), filename)
    stats = pstats.Stats(filename)

    #counts_by_methname = dict((key[2], stats.stats[key][0]) for key in stats.stats)

    sort_ = ('time', 'calls')
    stats.sort_stats(*sort_)
    stats.print_stats()

    return stats

from sqlalchemy import event


def profile_sql(engine, fn):
    stmt_catch = []

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement,
                        parameters, context, executemany):
        stmt_catch.append(
            (statement, parameters, executemany, time.time())
        )

    start_time = time.time()
    fn()
    end_time = time.time()

    total_exec_time = 0
    total_statements = 0
    total_rows = 0
    total_columns = 0

    delays = []

    prev_timestamp = start_time
    dbapi_conn = engine.raw_connection()
    try:
        for statement, parameters, executemany, timestamp in stmt_catch:
            delays.append(timestamp - prev_timestamp)
            prev_timestamp = timestamp

            total_statements += 1
            cursor = dbapi_conn.cursor()
            now = time.time()
            if executemany:
                cursor.executemany(statement, parameters)
                rows = []
            else:
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()
            total_exec_time = time.time() - now
            total_rows += len(rows)
            total_columns += len(rows) * len(cursor.description)
            cursor.close()
    finally:
        dbapi_conn.close()

    delays.append(end_time - prev_timestamp)

    return {
        'orm_time': end_time - start_time,
        'exec_time': total_exec_time,
        'statements': total_statements,
        'rows': total_rows,
        'columns': total_columns,
        'average_btw_exec': sum(delays) / len(delays)
    }


