#!/bin/bash
set -e
echo "Resetting Gita Q&A storage..."
rm -f /data/gita.db
rm -rf /data/chroma
echo "Storage cleared. Ready for fresh ingest."
