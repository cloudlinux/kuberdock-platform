*** Settings ***
Documentation     Check validation in the user create form.

Resource          ./resource.robot

Suite Setup       Open Browser To Kuberdock Page
Suite Teardown    Close All Browsers

Test Setup        Login into the KuberDock
Test Teardown     Logout


*** Test Cases ***
Add user with invalid data
    [Template]    Add user with invalid data and check message
    # MESSAGE                        DATA
    The E-mail format is invalid.    email=really bad email
    Username should be unique.       username=admin
    Username should be unique.       username=kuberdock-internal    timezone=Europe/Moscow


*** Keywords ***
Add user with invalid data and check message
    [Arguments]    ${message}    &{user_data}
    Go to the Create User page
    &{user_data}=    Fill user create form and Submit    &{user_data}
    Page Should Contain Inline Error Message "${message}"
