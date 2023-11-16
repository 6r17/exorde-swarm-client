FROM python:3.10-slim as base

COPY requirements.txt /app/requirements.txt
RUN pip3.10 install -r /app/requirements.txt

FROM base

COPY multi.py /app/multi.py
COPY blades /app/blades
