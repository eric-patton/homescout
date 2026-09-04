# Delta — browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

- **AC-96**: A request costs the same at hour six as at minute one. On Windows, the server asks the
  operating system not to power-throttle its process when it starts, because Windows 11 moves a
  hidden background process, which is what the scheduled task starts, into its efficiency mode
  some time after it starts, and everything in that process then runs at a fraction of the speed.
  Measured on the real workspace with nothing else changed: a results answer of 1,251 rows took
  0.7 seconds in a fresh process and between 3 and 4.8 seconds in the copy that had been up for
  three hours, doing the same reads and holding the same memory; lifting the throttling alone took
  it back to 0.7, and restoring it took it back to 4.8. The request is best effort: a refusal is
  not an error and the server starts either way, and anywhere other than Windows nothing is asked.
  A test asserts, on Windows, that the process's throttling state reads as explicitly off once the
  server has prepared itself, and everywhere else that preparing is harmless.

## MODIFIED

None.

## REMOVED

None.
