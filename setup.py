from setuptools import setup

setup(
    name="slapr",
    description="Add emoji on Slack posts on PR updates",
    version="0.0.0",
    packages=["slapr"],
    python_requires=">=3.7",
    install_requires=["slackclient==2.5.*", "pygithub==1.45.*"],
)
