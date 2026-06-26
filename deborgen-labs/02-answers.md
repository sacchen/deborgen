1. `sqlite3.connect` is called with `check_same_thread=False`. What does that argument do, and what does `self._lock = threading.Lock()` do that SQLite itself does not?

I'm guessing that check_same_thread=False means the SQL database can not run on the same thread as some other process. I don't know what threading.Lock() does.

2. `assert_job_lease` acquires `self._lock`, and then `finish_job` acquires it again in a separate call. Why is this potentially a problem? What would you need to change to make the lease check and the status update atomic?

