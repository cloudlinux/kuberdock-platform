<?php require 'init.php'; require 'modules/addons/KuberDock/KuberDock.php'; $res=KuberDock_activate();
if ($res['status']!='success') {throw new Exception($res['description']);}
