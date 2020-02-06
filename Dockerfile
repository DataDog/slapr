FROM python:3.8

COPY main.py requirements.txt /app/

WORKDIR /app/

RUN pip install -r requirements.txt

ENTRYPOINT [ "python", "main.py" ]
