import sys

import uvicorn


def main():
    """CLI entry point for llmring-server."""
    uvicorn.run(
        "llmring_server.main:app",
        host="0.0.0.0",
        port=8000,
        reload="--reload" in sys.argv,
    )


if __name__ == "__main__":
    main()
