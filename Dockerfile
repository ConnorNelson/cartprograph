FROM python:3.8

RUN apt-get update && \
    apt-get install -y supervisor redis-server

RUN curl -fsSL https://get.docker.com -o - | /bin/sh

RUN mkdir /cartprograph
WORKDIR /cartprograph

ADD requirements.txt .
RUN pip install "archr[qtrace] @ git+https://github.com/angr/archr"  # TODO: remove once archr[qtrace] on pypi
RUN pip install -r requirements.txt

ADD setup.py .
ADD tracer tracer
RUN pip install -ve .

ADD supervisord.conf .
ADD web web
ADD workers workers

ENV NUM_TRACERS=4
EXPOSE 4242

CMD ["/usr/bin/supervisord"]
