FROM python:3.8

RUN mkdir /app
WORKDIR /app

ADD . .

RUN pip install -ve .
