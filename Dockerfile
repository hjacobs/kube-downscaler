FROM python:3.7-alpine3.8
MAINTAINER Henning Jacobs <henning@jacobs1.de>

WORKDIR /

RUN pip3 install pykube

WORKDIR /

COPY kube_downscaler /kube_downscaler

ARG VERSION=dev
RUN sed -i "s/__version__ = .*/__version__ = '${VERSION}'/" /kube_downscaler/__init__.py

ENTRYPOINT ["python3", "-m", "kube_downscaler"]
