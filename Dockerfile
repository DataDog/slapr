# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2020-present Datadog, Inc.

# Use 3.7 instead of 3.8 for faster builds (a.k.a. The Wheels Problem™).
FROM python:3.7

WORKDIR /app
COPY setup.py /app/
COPY slapr/ /app/slapr/
RUN pip install .

WORKDIR /
ENTRYPOINT [ "python", "-m", "slapr" ]
