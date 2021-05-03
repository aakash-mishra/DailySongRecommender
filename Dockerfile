FROM python:3.9

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN rm /etc/localtime
RUN ln -s /usr/share/zoneinfo/Asia/Kolkata /etc/localtime

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt .
COPY ./.cache-spotipy /root
RUN pip install -r requirements.txt

# copy project
COPY . .

RUN apt-get clean \
    && apt-get -y update \
    && apt-get -y install cron

RUN chmod +x entrypoint.sh
ENTRYPOINT [ "./entrypoint.sh" ]

EXPOSE 8800
RUN python manage.py crontab add
CMD ["python", "manage.py", "runserver", "0.0.0.0:8800"]