*** Settings ***
Documentation     A test suite with a single test for valid login.
...
...               This test has a workflow that is created using keywords in
...               the imported resource file.
Resource          global_resources.robot
Suite Setup       Open Browser To Kuberdock Page
Suite Teardown    Close All Browsers

*** Test Cases ***
All Service Pods Should Be Running
    Login Into The Kuberdock
    Go To The Users Page
    Login As "kuberdock-internal"
    "Pods" View Should Be Open
    All Pods Should Be "running"
    [Teardown]    Run Keywords    Exit Login As Mode
    ...                           Logout
