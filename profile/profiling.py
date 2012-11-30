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


def _nested_fetch(cursor):
    colcount = [0]
    rowcount = [0]

    def fetch(cursor):
        for row in cursor.fetchall():
            rowcount[0] += 1
            for i, col in enumerate(cursor.description):
                colcount[0] += 1
                if col[1] == 5001:
                    fetch(row[i])
    fetch(cursor)
    return rowcount[0], colcount[0]


def _warmup_statement(cursor, statement, parameters, cache):
    if statement not in cache:
        cache[statement] = True
        for i in xrange(20):
            time_, ret = _timeit(cursor.execute, statement, parameters)
            #print "warmup", statement
            if time_ > 2:
                return


def _timeit(fn, *arg, **kw):
    now = time.time()
    ret = fn(*arg, **kw)
    total = time.time() - now
    return total, ret

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
    total_fetch_time = 0
    total_statements = 0
    total_rows = 0
    total_columns = 0

    delays = []

    # we want to run statements 20 times for akiban warmup
    cache = {}

    prev_timestamp = start_time
    dbapi_conn = engine.raw_connection()
    try:
        for statement, parameters, executemany, timestamp in stmt_catch:
            delays.append(timestamp - prev_timestamp)
            prev_timestamp = timestamp

            total_statements += 1
            cursor = dbapi_conn.cursor()

            #_warmup_statement(cursor, statement, parameters, cache)

            if executemany:
                exec_only_time, ret = _timeit(cursor.executemany, statement, parameters)
                fetch_time = 0
                rows = 0
                columns = 0
            else:
                exec_only_time, ret = _timeit(cursor.execute, statement, parameters)
                fetch_time, (rows, columns) = _timeit(_nested_fetch, cursor)

            total_exec_time += exec_only_time
            total_fetch_time += fetch_time
            total_rows += rows
            total_columns += columns
            cursor.close()
    finally:
        dbapi_conn.close()

    delays.append(end_time - prev_timestamp)

    return {
        'orm_time': end_time - start_time,
        'exec_time': total_exec_time,
        'fetch_time': total_fetch_time,
        'statements': total_statements,
        'rows': total_rows,
        'columns': total_columns,
        'average_btw_exec': sum(delays) / len(delays)
    }


