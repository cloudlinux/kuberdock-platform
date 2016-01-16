#!/bin/bash
 
# the following command will not remove running containers, just displaying errors on them
docker rm $(docker ps -a -q) 
docker rm $(docker ps -f=status=exited -q)
docker rmi `docker images -qf 'dangling=true'`
docker rm -f `docker ps -a | grep Dead | awk '{print $1 }'`
