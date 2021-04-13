#!/bin/sh -ex

celery --app=captionthis worker --loglevel=DEBUG &
celery --app=captionthis beat --loglevel=DEBUG &
tail -f /dev/null
