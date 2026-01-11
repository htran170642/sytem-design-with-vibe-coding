#!/bin/bash
# Create the project folder structure

mkdir -p observability/{ingestion,agents,processing,storage,api,ui,infra,tests}
mkdir -p observability/common
mkdir -p observability/tests/{unit,integration}
mkdir -p config
mkdir -p scripts
mkdir -p docs

# Create __init__.py files
touch observability/__init__.py
touch observability/ingestion/__init__.py
touch observability/agents/__init__.py
touch observability/processing/__init__.py
touch observability/storage/__init__.py
touch observability/api/__init__.py
touch observability/ui/__init__.py
touch observability/common/__init__.py
touch observability/tests/__init__.py

echo "Project structure created successfully!"
