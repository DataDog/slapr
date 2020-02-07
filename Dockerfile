# Use 3.7 instead of 3.8 for faster builds (a.k.a. The Wheels Problem™).
FROM python:3.7

WORKDIR /app
COPY setup.py /app/
COPY slapr/ /app/slapr/
RUN pip install .

WORKDIR /
ENTRYPOINT [ "python", "-m", "slapr" ]
