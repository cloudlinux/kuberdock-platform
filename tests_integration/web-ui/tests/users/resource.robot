*** Settings ***
Documentation     A resource file for users tests
Resource          global_resources.robot
Library           String


*** Keywords ***
Go to the Create User page
    Go to the Users page
    Click    jquery=button:contains(Create user)
    "Create User" View Should Be Open

Go to the Profile page
    Click    jquery=.profile-menu > a    1 s
    Click    jquery=.profile-menu a:contains(Settings)    1 s
    "Settings" view should be open


Input "${value}" in "${field_name}" field
    Input Text    jquery=label:contains("${field_name}") ~ input   ${value}

Fill Password
    [Arguments]    ${password}    ${password_again}=${password}
    Input Text    jquery=label:contains(Password) ~ input:first   ${password}
    Input Text    jquery=label:contains(Password) ~ input:last   ${password_again}
    [Return]    ${password}

Select "${value}" in "${field_name}" field
    ${field_locator}=    Set Variable    label:contains("${field_name}") ~ .bootstrap-select
    Click    jquery=${field_locator} > button
    Click    jquery=${field_locator} .dropdown-menu a:contains("${value}")    1 s

Select "${value}" in status
    ${field_locator}=    Set Variable    div.form-group.clearfix > div.btn-group.bootstrap-select
    Click    jquery=${field_locator} > button
    Click    jquery=${field_locator} .dropdown-menu a:contains("${value}")    1 s

Fill user create form and Submit
    [Documentation]    All arguments are optional.
    ...  If username, email or password weren't provided, generate random values.
    ...  Returns the same data, but with generated username, email, and password.

    [Arguments]    ${username}=${None}    ${email}=${None}
    ...  ${password}=${None}    ${password_again}=${None}
    ...  ${first_name}=${None}    ${last_name}=${None}    ${middle_initials}=${None}
    ...  ${timezone}=${None}    ${role}=${None}    ${package}=${None}
    ...  ${status}=${None}    ${suspended}=${None}

    ${random_username}=    Generate Random String
    ${random_email}=       Generate Random String
    ${random_password}=    Generate Random String
    ${username}=    Set Variable If    $username is None    ${random_username}    ${username}
    ${email}=       Set Variable If    $email is None       ${random_email}@test.com       ${email}
    ${password}=    Set Variable If    $password is None    ${random_password}    ${password}
    ${password_again}=    Set Variable If    $password_again is None    ${password}    ${password_again}

    Input "${username}" in "Username" field
    Input "${email}" in "E-mail" field
    Fill Password    ${password}    ${password_again}

    Run Keyword If    $first_name is not None         Input "${first_name}" in "First name" field
    Run Keyword If    $last_name is not None          Input "${last_name}" in "Last name" field
    Run Keyword If    $middle_initials is not None    Input "${middle_initials}" in "Middle initials" field
    Run Keyword If    $timezone is not None           Select "${timezone}" in "Timezone" field
    Run Keyword If    $role is not None               Select "${role}" in "Role" field
    Run Keyword If    $package is not None            Select "${package}" in "Package" field
    Run Keyword If    $status is not None             Select "${status}" in status
    Run Keyword If    $suspended                      Click    jquery=label:contains("Suspended")

    Click Element    jquery=button:contains(Create)

    # return the same data, but with generated username, email, and password.
    Run Keyword And Return    Create Dictionary
    ...  username=${username}    email=${email}
    ...  password=${password}    password_again=${password_again}
    ...  first_name=${first_name}    last_name=${last_name}
    ...  middle_initials=${middle_initials}    timezone=${timezone}    role=${role}
    ...  package=${package}    status=${status}    suspended=${suspended}


Add user and log in
    [Arguments]  &{user_data}
    Go to the Create User page
    &{user_data}=    Fill user create form and Submit    &{user_data}
    "Users" view should be open
    Logout
    Login into the Kuberdock as "${user_data.username}" with password "${user_data.password}"
    [Return]    &{user_data}
