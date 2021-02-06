FROM python:3.8

RUN apt-get update && \
    apt-get install -y supervisor redis-server

RUN curl -fsSL https://get.docker.com -o - | /bin/sh

RUN mkdir /cartprograph
WORKDIR /cartprograph

ADD requirements.txt .
RUN pip install -r requirements.txt
RUN pip install --upgrade --no-deps "archr[qtrace] @ git+https://github.com/angr/archr"  # TODO: remove once changes propogate to pypi

ADD setup.py .
ADD cartprograph cartprograph
RUN pip install --no-deps -ve .

ADD supervisord.conf .
ADD web web
ADD workers workers

ENV NUM_TRACERS=4
EXPOSE 4242

CMD ["/usr/bin/supervisord"]
