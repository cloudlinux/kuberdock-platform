*** Settings ***
Documentation     Check successful cases for users creation.

Resource          ./resource.robot

Suite Setup       Open Browser To Kuberdock Page
Suite Teardown    Close All Browsers

Test Setup        Login into the KuberDock


*** Test Cases ***
Create User and try to log in
    &{user_data}=    Add user and log in
    "Pods" view should be open
    Breadcrumb Should Contain Button "Add new container"
    [Teardown]    Delete user and logout    ${user_data.username}

Create LimitedUser and try to log in
    &{user_data}=    Add user and log in    role=LimitedUser
    "Pods" view should be open
    Breadcrumb Should Not Contain Button "Add new container"
    [Teardown]    Delete user and logout    ${user_data.username}

Create User and check data in profile
    &{user_data}=    Add user and log in    timezone=Asia/Hong_Kong
    ...  first_name=Qwe    last_name=Asd    middle_initials=zxc
    Go to the Profile page
    Wait Until Page Contains    ${user_data.email}
    Wait Until Page Contains    ${user_data.timezone}
    Wait Until Page Contains    ${user_data.first_name}
    Wait Until Page Contains    ${user_data.last_name}
    Wait Until Page Contains    ${user_data.middle_initials}
    [Teardown]    Delete user and logout    ${user_data.username}


*** Keywords ***
Delete user and logout
    [Arguments]    ${username}
    Logout
    Login into the KuberDock
    Go to the Users page
    Delete User    ${username}
    [Teardown]    Logout
