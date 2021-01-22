FROM python:3.8

RUN apt-get update && \
    apt-get install -y supervisor redis-server

RUN curl -fsSL https://get.docker.com -o - | /bin/sh

RUN mkdir /cartprograph
WORKDIR /cartprograph

ADD . .

RUN pip install -ve .

ENV NUM_TRACERS=4

EXPOSE 4242

CMD ["/usr/bin/supervisord"]
