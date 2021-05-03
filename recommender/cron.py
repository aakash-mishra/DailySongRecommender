from .song_recommender import main
from django.conf import settings
import datetime
import logging

def cron_job():
    print("CALLING VIA CRON JOB AT {}".format(datetime.datetime.now()))
    main()

if __name__ == "__main__":
    cron_job()
    
