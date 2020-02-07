# Use 3.7 instead of 3.8 for faster builds (a.k.a. The Wheels Problem™).
FROM python:3.7

COPY requirements.txt /
RUN pip install -r /requirements.txt

COPY slapr/ /slapr/

ENTRYPOINT [ "python", "-m", "slapr" ]
