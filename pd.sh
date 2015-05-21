#!/bin/bash
#TMS=$(date +"%Y-%m-%d %H:%M:%S")
#echo "$TMS $1 $2 $3 $4" >> /tmp/pd.log

if [ $1 == umount ]; then
    ACTION=$1
    UUID=$2
else
    UUID=$1
    ACTION=$2
fi

DEVICE=$3
NAME=$4
SIZE=$5

MP="/var/lib/kubelet/pods/$UUID/volumes/kubernetes.io~scriptable-disk/$NAME"

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
    rbd create $DEVICE --size=$SIZE
    DEVICE=$(rbd map $DEVICE)
    mkfs.ext4 $DEVICE
    mount "$DEVICE" "$MP"
}

function map_and_mount {
    rbd showmapped|awk "NR>1{if(\$3==\"$DEVICE\"){exit 1}}"
    if [ $? -ne 0 ];then
        echo "Drive $DEVICE is already mapped"
        exit 1
    fi
    mkdir_if_missing
    DEVICE=$(rbd map $DEVICE)
    mount "$DEVICE" "$MP"
}

function lookup {
    LIST=$(rbd ls)
    if [ -z "$LIST" ];then
        return 0
    else
        while read -r LINE; do
            if [ $LINE == $DEVICE ];then
                return 1
            fi
        done <<< "$LIST"
        return 0
    fi
}

function make_unmount {
    DRIVES=$(mount | awk "/$UUID/ {print \$1}")
    if [ -z "$DRIVES" ];then
        exit 0
    fi

    while read -r DRIVE;do
        umount $DRIVE
        rbd unmap $DRIVE
    done <<< "$DRIVES"
}

if [ $ACTION == "create" ];then
    lookup
    if [ $? -eq 0 ];then
        create_map_and_mount
    else
        echo "Image $DEVICE exists"
        exit 1
    fi
elif [ $ACTION == "mount" ];then
    lookup
    if [ $? -eq 0 ];then
        echo "Image $DEVICE not found"
        exit 1
    else
        map_and_mount
    fi
elif [ $ACTION == "umount" ];then
    make_unmount
fi
