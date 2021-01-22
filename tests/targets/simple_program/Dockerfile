FROM ubuntu:20.04

RUN apt-get update && \
    apt-get install -y build-essential

RUN mkdir /simple_program
WORKDIR /simple_program

ADD simple_program.c .

RUN gcc simple_program.c -o simple_program

CMD ["./simple_program"]