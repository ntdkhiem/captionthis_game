FROM python:3.9.1-slim-buster as base

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install --upgrade pip
COPY ./requirements.txt /usr/src/app/requirements.txt
RUN pip install -r requirements.txt

COPY . /usr/src/app

# FOR LOCAL
FROM base as local
WORKDIR  /usr/src/app
ENTRYPOINT [ "python" ]
CMD [ "manage.py", "run", "-h", "0.0.0.0", "-p", "5000" ]
