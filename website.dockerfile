FROM ubuntu:14.04
MAINTAINER Alex Yuan Gao "gaoyuankidult@gmail.com"

RUN apt-get update
RUN apt-get install -y python-pip wget git python-dev


RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10
RUN echo "deb http://repo.mongodb.org/apt/ubuntu trusty/mongodb-org/3.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-3.0.list
RUN apt-get update
RUN apt-get install -y mongodb-org


RUN pip install tornado
RUN python -m pip install motor
RUN pip install greenlet

RUN cd /root \
    && git clone https://github.com/gaoyuankidult/SocialRoboics.git\
    && cd SocialRoboics/motor-blog \
    && pip install -r requirements.txt \
    && mkdir data \
    && cp /root/SocialRoboics/motor-blog/motor_blog.conf.example /root/SocialRoboics/motor-blog/motor_blog.conf \
    && mkdir log \
    && touch log/motor-blog.log

EXPOSE 8888

CMD mongod --dbpath /root/SocialRoboics/motor-blog/data --logpath /root/SocialRoboics/motor-blog/data/mongod.log --fork --setParameter textSearchEnabled=true && cd /root/SocialRoboics/motor-blog && python server.py --debug --config=motor_blog.conf --ensure-indexes

