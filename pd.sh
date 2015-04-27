#!/bin/bash

ACTION=$1
NAME=$2
SIZE=$3
PREFIX=/var/lib/kuberdock/mp
MP="$PREFIX/$NAME"

if [ $USER != root ];then
    echo "Superuser privileges required"
    exit 0
fi

function mkdir_if_missing {
    if [ ! -d "$MP" ];then
        mkdir -p "$MP"
    fi
}

function create_map_and_mount {
    mkdir_if_missing
    rbd create $NAME --size=$SIZE
    DEVICE=$(rbd map $NAME)
    mkfs.ext4 $DEVICE
    mount "$DEVICE" "$MP"
}

function lookup {
    LIST=$(rbd ls)
    if [ -z "$LIST" ];then
        return 0
    else
        while read -r LINE; do
            if [ $LINE == $NAME ];then
                return 1
            fi
        done <<< "$LIST"
        return 0
    fi
}

if [ $ACTION == "create" ];then
    lookup
    if [ $? -eq 0 ];then
        create_map_and_mount
    else
        echo "Image $NAME exists"
        exit 1
    fi
fi
