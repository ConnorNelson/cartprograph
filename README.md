# Cartprograph

For interactively mapping out the state space of a program

## Setup

```sh
git clone https://github.com/ConnorNelson/cartprograph
cd cartprograph
docker build -t cartprograph .
docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock -p 4242:4242 -e TARGET_IMAGE=<TARGET> cartprograph
```

### Simple Program testcase

```sh
docker build -t simple_program tests/targets/simple_program
```

### Simple Client

```sh
docker build -t cartprograph-client client
docker run -it --rm --net=host cartprograph-client
```
