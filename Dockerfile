FROM alpine:3.6
MAINTAINER Henning Jacobs <henning@jacobs1.de>

RUN apk add --no-cache python3 ca-certificates && \
    pip3 install --upgrade pip setuptools pykube && \
    rm -rf /var/cache/apk/* /root/.cache /tmp/* 

WORKDIR /

COPY kube_downscaler /kube_downscaler
COPY scm-source.json /

ARG VERSION=dev
RUN sed -i "s/__version__ = .*/__version__ = '${VERSION}'/" /kube_downscaler/__init__.py

ENTRYPOINT ["python3", "-m", "kube_downscaler"]
