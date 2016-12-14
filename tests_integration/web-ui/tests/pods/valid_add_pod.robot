*** Settings ***
Documentation     A test suite containing tests of adding, checking and deleting of the Pod.

Resource          ./resource.robot

Test Setup        Login into the KuberDock
Test Teardown     Logout

*** Test Cases ***
Create pod with nginx container, start and remove pod
    Select billing type "No billing"
    Go to the Users page
    Login as "test_user"
    Main View Should Be Open
    Create Pod From Docker Hub Using Container Image    nginx
    Start New Pod
    Delete New Pod
    Exit Login As Mode
