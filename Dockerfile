FROM python:3.10-slim as base

COPY requirements.txt /app/requirements.txt
RUN pip3.10 install -r /app/requirements.txt

COPY exorde_data /lib/exorde_data
RUN pip3.10 install /lib/exorde_data

RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

FROM base as blade

COPY multi.py /app/multi.py
COPY blades /app/blades
