#!/bin/sh
set -e
touch /etc/crontab /etc/cron.*/*
service cron start

exec "$@"