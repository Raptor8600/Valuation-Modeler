# Data snapshots

* `reference/` - committed, used by the tests and the worked example (see each file's `_meta.provenance`).
* `<TICKER>_<YYYYMMDDTHHMMSS>.json` - written when you run a live fetch locally with `save=True` (the hosted app keeps
  searches in the visitor's session instead and offers them as a download): the raw SEC and Yahoo responses exactly as
  returned, the request URLs and the fetch time. Git-ignored by default (several MB each); commit one deliberately if you
  want a reviewer to see it.
