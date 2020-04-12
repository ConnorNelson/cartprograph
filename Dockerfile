FROM python:3.8

RUN apt-get update && \
    apt-get install -y supervisor redis-server

RUN mkdir /app
WORKDIR /app

ADD . .

RUN pip install -ve .

EXPOSE 4242

CMD ["/usr/bin/supervisord"]
