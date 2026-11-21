"""Stable process entry point; HTTP and worker register the same Huey task."""
from api.jobs import work

if __name__ == "__main__":
    work()
