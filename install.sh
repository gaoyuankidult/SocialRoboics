# build docker image according to dockerfile
docker build -f website.dockerfile . -t website

# run a detached container
docker run -d -p 8888:8888 website:latest

# follow motor-blog instructions to run the website.
