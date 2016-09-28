*** Settings ***
Documentation    Check successful cases for suspended and locked users.

Resource          ./resource.robot

Suite Setup       Open Browser To Kuberdock Page
Suite Teardown    Close All Browsers

Test Setup        Login into the KuberDock

*** Test Cases ***
Create suspended user and try to create pods
    &{user_data}=    Add user and login     suspended=True
    "Pods" view should be open
    Page Should Not Contain Element    jquery=a#add_pod
    [Teardown]  Delete user and logout    ${user_data.username}

Create locked user and try to login
    &{user_data}=    Add user and login     status=Locked
    Login Page Should Be Open
    Page Should Contain Error Message "Insufficient permissions for requested action"
    [Teardown]  Proceed to delete user    ${user_data.username}

*** Keywords ***
Delete user and logout
    [Arguments]    ${username}
    Logout
    Proceed to delete user    ${username}

Proceed to delete user
    [Arguments]    ${username}
    Login into the KuberDock
    Go to the Users page
    Delete User    ${username}
    [Teardown]    Logout