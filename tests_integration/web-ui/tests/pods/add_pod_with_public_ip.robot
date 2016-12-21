*** Settings ***
Documentation       A test suite containing for tests creating pods with public IP, accessing
...                 pods via public IP, checking access logs in pod's container page.

Resource            ./resource.robot

Test Setup          Login into the Kuberdock
Test Teardown       Run Keywords  Go To User's Pods Page  Delete New Pod  Exit Login As Mode  Logout

*** Test Cases ***
Create pod with nginx container, start pod, check its status and access via public IP
    Go to the Users page
    Login as "test_user"
    Main View Should Be Open
    Create Pod From Docker Hub Using Container Image  nginx  Open Ports  Start It
    Go To New Pod's Page
    Access New Pod's Public IP 1 Times

Create pod with nginx container, start pod, access via public IP several times and check logs
    Go to the Users page
    Login as "test_user"
    Main View Should Be Open
    Create Pod From Docker Hub Using Container Image  nginx  Open Ports
    Start New Pod
    Go To New Pod's Page
    Access New Pod's Public IP 5 Times
    Go To New Pod's nginx Container Page And Wait For 5 Access Logs To Appear
