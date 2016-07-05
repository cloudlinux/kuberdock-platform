cd /vagrant/ && mkdir k && rpm2cpio kuberdock*.rpm > k/k.cpio && cd k && cpio -idm < k.cpio && cp var/opt/kuberdock/deploy.sh ../ && cd ../ && rm -rf ./k
