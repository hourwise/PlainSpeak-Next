# Release 3.2.0

## Added

- Export to Parquet, in addition to CSV and JSON.
- A `--dry-run` flag for the import command.

## Changed

- The default timeout is now 30 seconds (previously 60).
- Imports larger than 2 GB are processed in batches of 10,000 rows.

## Fixed

- Dates before 1970 were exported as negative numbers.
- The progress bar no longer freezes at 99%.

## Removed

- Support for Python 3.8, which reached end of life.
