"""Job entrypoint to redact old request logs."""

import os

from wikidatasearch.services.logger import Logger


def main() -> None:
    """Run one redaction cycle and print the number of redacted rows."""
    days = int(os.getenv("REDACTION_DAYS", str(90)))
    batch_size = int(os.getenv("REDACTION_BATCH_SIZE", str(2000)))

    redacted = Logger.redact_old_requests(days=days, batch_size=batch_size)
    print(f"redaction complete: redacted_rows={redacted} days={days} batch_size={batch_size}")


if __name__ == "__main__":
    main()
