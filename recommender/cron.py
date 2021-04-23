from .song_recommender import main
from django.conf import settings
import datetime

def cron_job():
    print("CALLING VIA CRON JOB AT {}".format(datetime.datetime.now()))
    main()