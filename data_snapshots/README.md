# Data snapshots

* `reference/` - committed, used by the tests and the worked example (see each file's `_meta.provenance`).
* `<TICKER>_<YYYYMMDDTHHMMSS>.json` - written by every live fetch in the app: the raw SEC and Yahoo responses exactly as
  returned, the request URLs and the fetch time. Git-ignored by default (several MB each); commit one deliberately if you
  want a reviewer to see it.
