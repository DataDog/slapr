# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/)
# Copyright 2023-present Datadog, Inc.

from setuptools import setup

setup(
    name="slapr",
    description="Add emoji on Slack posts on PR updates",
    version="0.0.0",
    packages=["slapr"],
    python_requires=">=3.7",
    install_requires=["slack_sdk==3.27.1", "pygithub==1.45.*"],
)
