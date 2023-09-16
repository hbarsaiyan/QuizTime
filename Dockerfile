# syntax=docker/dockerfile:1

FROM python:3.11.4

WORKDIR /code

COPY requirements.txt .

RUN apt-get update
RUN apt-get -y install libglib2.0-0
RUN apt-get -y install libgl1
RUN apt-get -y install libsm6 \
     libxrender-dev \
     libxext6

RUN pip3 install -r requirements.txt

COPY . .

EXPOSE 50505

ENTRYPOINT ["gunicorn", "app:app"]