"""Compatibility entrypoint that forwards to the backend application bootstrap."""

from __future__ import annotations

from backend.application import create_application_context, main


if __name__ == "__main__":
    main()
