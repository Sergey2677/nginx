FROM nginx:latest

RUN apt-get update && apt-get install python3 certbot python3-certbot-nginx -y

COPY ./letsencrypt-initialize.py /letsencrypt-initialize.py

RUN chmod +x /letsencrypt-initialize.py
