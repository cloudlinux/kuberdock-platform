*** Settings ***
Documentation     Tests that relate to IP Pool

Resource          global_resources.robot
Resource          ../ip_pool/resource.robot

Suite Teardown    Close All Browsers
Test Setup        Login into the KuberDock


*** Test Cases ***
Add Simple IP Pool
    Add IP pool
    [Teardown]  Delete IP Pool