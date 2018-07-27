---
title: Online Schema Changes
summary: Update table schemas without external tools or downtime.
toc: true
---

Traditional, non-distributed databases cannot handle making schema changes while allowing writes.  If you want to make a schema change to a table in a traditional single-node non-distributed database, you usually need to:

1. Lock the table so that no one can write to it (read-only mode)
2. Make all the necessary changes while the table is locked
3. Open up the table for writes again

CockroachDB does not have these limitations.  Its schema change engine is designed to update table schemas without:

- Downtime
- Ad hoc sequencing of operations
- Reliance on external tools
- Increases in read/write latency

In other words, you can change your table schema while the database is running and expect it to run the schema change as a background job while performing normally.

{{site.data.alerts.callout_info}}
This page has information about how online schema changes work.  For more information about the commands that perform the schema changes, see the documentation for [`ALTER TABLE`][alter] and its subcommands.
{{site.data.alerts.end}}

## How online schema changes work

At a high level, online schema changes are accomplished by using a bridging strategy involving concurrent uses of multiple versions of the schema.  This approach allows us to roll out a new schema while the previous version is still in use.  We then backfill or delete the underlying table data as needed in the background, while the cluster is still running.

The table begins in its current state, let’s call it *v1*, is then brought into an intermediate state (call it *v1.5*), and finally ends up with the schema changes applied on all nodes; we’ll call this state *v2*.

The gateway node receives the [`ALTER TABLE`][alter] command from the [client][client]. Given:

- The current state of the schema (*v1*)
- And the desired end state (*v2*)

the node calculates an intermediate state (*v1.5*) which will act as a bridge between them.

The gateway node transmits this intermediate (*v1.5*) schema to the other nodes, which update their local caches of the schema to use *v1.5*. After a few seconds, the locally cached *v1* schemas on all of the nodes will have expired and been replaced with *v1.5*.  During this time, they continue to service reads and writes to the user as if they were still using the *v1* schema.

Once all of the nodes are using the *v1.5* intermediate schema, backfilling (or deletion, depending on the statement) can start.

Once the *v1.5* intermediate schema has been transmitted to all of the other nodes, each of them operate as follows:

- On reads, they report to the user that they have 3 columns, as before (in *v1*).

- On writes, they accept three columns as before (again from *v1*); in addition, they automatically add a fourth column `inventory_count` with a default value of 5 to the write, but without telling the user. From the user’s POV, the schema is still at *v1*.

During the backfilling process, the nodes will go through and update all of the underlying table data to make sure all instances of the table are stored according to the requirements of the *v2* schema.

Once backfilling is complete, all nodes will switch over to the *v2* schema, and will allow reads and writes of the table using the new schema.

## Example

Let’s look at an example.  Given a table `fruits` with three columns

{% include copy-clipboard.html %}
~~~ sql
> CREATE TABLE fruits (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      name STRING,
      color STRING
  );
~~~

let's add a fourth schema element, a new column with a default value of 5:

{% include copy-clipboard.html %}
~~~ sql
> ALTER TABLE fruits ADD COLUMN inventory_count INTEGER DEFAULT 5;
~~~

You can check on the status of a schema change at any time using the [`SHOW JOBS`][show] statement as follows (note the "schema change" in the type column):

{% include copy-clipboard.html %}
~~~ sql
> SHOW JOBS;
~~~

~~~
+--------------------+---------------+-----------------------------------------------------------------------------+----------+-----------+----------------------------+----------------------------+----------------------------+----------------------------+--------------------+-------+----------------+
|         id         |     type      |                                 description                                 | username |  status   |          created           |          started           |          finished          |          modified          | fraction_completed | error | coordinator_id |
+--------------------+---------------+-----------------------------------------------------------------------------+----------+-----------+----------------------------+----------------------------+----------------------------+----------------------------+--------------------+-------+----------------+
| 368863345707909121 | SCHEMA CHANGE | ALTER TABLE test.public.fruits ADD COLUMN inventory_count INTEGER DEFAULT 5 | root     | succeeded | 2018-07-26 20:55:59.698793 | 2018-07-26 20:55:59.739032 | 2018-07-26 20:55:59.816007 | 2018-07-26 20:55:59.816008 |                  1 |       |           NULL |
+--------------------+---------------+-----------------------------------------------------------------------------+----------+-----------+----------------------------+----------------------------+----------------------------+----------------------------+--------------------+-------+----------------+
(1 row)
~~~

This example was intentionally kept simple, but the process is the same for more complex schema changes.

## Limitations

Because schemas are cached on every node, there are limitations on how you can use schema changes in [transactions][txns].

Specifically, as described above in [How it works](), there are two versions of every schema: the cached (intermediate) version, and the written version.

You can do transactions on schemas that are already written, but not on cached schemas.  For example, you cannot do a [`CREATE INDEX`][create] followed immediately by a [`SELECT`][select] on that index inside the same transaction.

This behavior is necessary because in order to support schema changes inside a transaction would mean requiring that transaction to propagate across all the nodes of a cluster.  In other words, all other transactions would have to block on the schema change, since the schema change-containing transaction would have to commit before any other transactions could make progress.

## Statements that use online schema changes

The following SQL statements use online schema changes to do their work:

+ The [`ALTER TABLE`][alter] subcommands
+ [`DROP INDEX`][drop]
+ ???
+ PROFIT!

## See Also

+ [How online schema changes are possible in CockroachDB][blog]: Blog post introducing this feature
+ [Online, asynchronous schema change in F1][f1]: Paper from Google Research describing schema changes in F1 database, which served as an inspiration for our system.
+ [ALTER TABLE][alter]
+ [CREATE INDEX][create]
+ [DROP INDEX][drop]

<!-- Links -->

[alter-drop]: drop-column.html
[alter]: alter-table.html
[blog]: https://cockroachlabs.com/blog/how-online-schema-changes-are-possible-in-cockroachdb/
[client]: use-the-built-in-sql-client.html
[drop]: drop-index.html
[create]: create-index.html
[f1]: https://ai.google/research/pubs/pub41376
[show]: show-jobs.html
[txns]: transactions.html
[select]: selection-queries.html
