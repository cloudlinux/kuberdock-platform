*** Settings ***
Documentation     A test suite containing tests of adding, checking and deleting of the Pod.

Resource          ./resource.robot

Suite Teardown    Close All Browsers

Test Setup        Login into the KuberDock

*** Test Cases ***
Create pod with nginx container, start and remove pod
    Select billing status "No billing"
    Go to the Users page
    Login as "test_user"
    Main View Should Be Open
    Create Pod With nginx Container From Docker Hub And Start It
    Delete New Pod
    Exit Login As Mode
    [Teardown]    Logout