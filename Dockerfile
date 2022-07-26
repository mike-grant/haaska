FROM python:3.10

RUN \
  apt-get update && \
  apt-get install -y jq zip && \
  pip install awscli && \
  apt-get clean && \
  cd /var/lib/apt/lists && rm -fr *Release* *Sources* *Packages* && \
  truncate -s 0 /var/log/*log

RUN mkdir -p /usr/src/app

WORKDIR /usr/src/app

COPY . /usr/src/app

CMD ["make"]
