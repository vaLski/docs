---
title: Online Schema Changes
summary: Update table schemas without external tools or downtime.
toc: true
---

Traditional, non-distributed databases cannot handle making schema changes while allowing writes.  If you want to make a schema change to a table in a traditional single-node non-distributed database, you usually need to:

1. Lock the table so that no one can write to it (read-only mode)
2. Make all the necessary changes while the table is locked
3. Open up the table for writes again

CockroachDB does not have these limitations.  It accepts schema changes to the live, running database.

CockroachDB's schema change engine is designed to provide a simple way to update a table schema without:

- Downtime
- Ad hoc sequencing of operations
- Reliance on external tools
- Increases in read/write latency

## How online schema changes work

At a high level, this is accomplished by using a bridging strategy.  The table begins in its current state, let’s call it "v1", is brought into an intermediate state (call it "v1.5"), and finally ends up with the schema changes applied, which we’ll call "v2".

Let’s look at a concrete example.  Given a table `fruits` with three columns

{% include copy-clipboard.html %}
~~~
> CREATE TABLE fruits (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      name STRING,
      color STRING
  );
~~~

Now let's add a fourth element, which should have a default value of 5:

{% include copy-clipboard.html %}
~~~ sql
> ALTER TABLE fruits ADD COLUMN inventory_count INTEGER DEFAULT 5;
~~~

The gateway node receives the ALTER TABLE schema update command from the [client][client]. Given the current state (v1) and the desired end state (v2), it calculates an intermediate state (v1.5) which will act as a bridge between the two.

When the coordinating node interacts with other nodes, it transmits the intermediate "v1.5" schema.  The nodes each have a local cache of the schema, which they update to v1.5.  v1.5 has the 4th column, constrained to default to 5.

The way the nodes operate using the v1.5 schema in this example is:

- On reads, they report to the user that they have 3 columns, as before
- On writes, they accept three columns as before, and automatically add a fourth column `inventory_count` with a default value of 5, but without telling the user. From the user’s POV, the schema is still at "v1".

After 2 seconds, the locally cached v1 schemas on all of the nodes will have expired and been replaced with v1.5.  During this time, they continue to service reads and writes to the user as if they were still on the v1 schema.

Now that all of the nodes are using the v1.5 intermediate schema, backfilling can start.

During the backfilling process, the nodes will go through and update all of the data underlying the table to make sure all instances of the table are stored according to the requirements of the v2 schema.

Once backfilling is complete, all nodes will switch over to the v2 schema, and will allow reads and writes of the latest 4-element table (with the new element meeting the constraint that it defaults to 5).

This process can be visualized in the diagram below, which shows the `fruits` table schema at v1, v1.5, and v2. This example was intentionally kept simple, but the process is the same for more complex schema changes.

<img src="{{ 'images/v2.1/online-schema-changes.png' | relative_url }}" alt="Online schema changes diagram" style="border:1px solid #eee;max-width:100%" />

## Limitations

There are limitations on how you can use schema changes in transactions.  This stems from the fact that schemas are cached on every node.

+ There are already 2 versions; one cached, one written. 

+ You can do transactions on the ones that are written, but not the ones that are cached. 

+ This isn’t well explained in our docs. 

In the wild this shows up like this: create index + select that references the index in the same transaction. 

+ Usability through better error messages: Today CRDB will say “index not found” or “column not found” -- however the user clearly sees column in the transaction. This is confusing 

+ This isn’t as bad as it used to be because we fixed a problem in 2.1 because we can now add the create table as part of a txn. 

How often do users change schemas within transactions? What is the benefit of addressing this? What should we fix, and what should we document?

Can’t make this “just work” since its a txn across ALL nodes. It would be weird to make it work since all other txns would have to wait. Not worth the effort. Docs work needs to be done here.

## See Also

+ [ALTER TABLE][alter]
+ [How online schema changes are possible in CockroachDB][blog]

<!-- Links -->

[alter]: alter-table.html
[blog]: https://cockroachlabs.com/blog/how-online-schema-changes-are-possible-in-cockroachdb/
[client]: use-the-built-in-sql-client.html
