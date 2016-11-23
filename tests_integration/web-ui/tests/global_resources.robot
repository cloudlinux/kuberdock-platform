*** Settings ***
Documentation     A resource file with common reusable keywords and variables.

Library           Selenium2Library
Library           OperatingSystem
Library           Collections
Library           Utils


*** Variables ***
${SERVER}                   192.168.33.114
${BROWSER}                  Chrome
${ADMIN PASSWORD}           admin
${TIMEOUT}                  10 s
${DELAY}                    0
${MAIN URL}                 https://${SERVER}/

*** Keywords ***
Open Browser To Kuberdock Page
    Prepare And Open Browser    ${BROWSER}    ${MAIN URL}
    Login Page Should Be Open

Login Page Should Be Open
    Wait Until Page Contains Element    jquery=button:contains(Log in)

Click
    [Arguments]    ${locator}    ${delay}=${DELAY}    ${timeout}=${TIMEOUT}
    [Documentation]
    ...  Wait until element is visible and animations are finished then click
    Sleep    ${delay}
    Wait Until Keyword Succeeds    ${timeout}    0.1s    Click Element    ${locator}

Login into the Kuberdock as "${username}" with password "${password}"
    Input Text    css=#login-form-username-field    ${username}
    Input Text    css=#login-form-password-field    ${password}
    Click    css=button.login

Login into the Kuberdock
    Login into the Kuberdock as "admin" with password "${ADMIN PASSWORD}"
    "Nodes" View Should Be Open

Exit Login As Mode
    Click    jquery=.login-view-mode-wrapper span:contains(Exit Mode)
    Breadcrumb Should Contain "Users"

Logout
    Click    jquery=.profile-menu > a    1 s
    Click    jquery=.profile-menu span:contains(Logout)    1 s
    Login Page Should Be Open

Breadcrumb Should Contain "${text}"
    Wait Until Page Contains Element    jquery=ul.breadcrumb:contains("${text}")

Breadcrumb Should Contain Button "${text}"
    Page Should Contain Element    jquery=.breadcrumbs .control-group:contains("${text}")

Breadcrumb Should Not Contain Button "${text}"
    Page Should Not Contain Element    jquery=.breadcrumbs .control-group:contains("${text}")

"${name}" View Should Be Open
    Breadcrumb Should Contain "${name}"
    Wait Until Keyword Succeeds    ${timeout}    0.1
    ...  Element Should Be Visible    jquery=.profile-menu > a    menu in header was not fully rendered

Main View Should Be Open
    ${nodes}=    Run Keyword And Return Status    "Nodes" View Should Be Open
    Run Keyword Unless    ${nodes}    "Pods" View Should Be Open

Page Should Not Contain Error Messages
    Page Should Not Contain Element    jquery=.notifyjs-container

Page Should Contain Inline Error Message "${text}"
    Wait Until Page Contains Element    jquery=.notifyjs-container span:contains("${text}")

Page Should Contain Error Message "${text}"
    Wait Until Page Contains Element    jquery=.notifyjs-container:contains("${text}")

Page Should Contain Only Error Message "${text}"
    Page Should Contain Error Message "${text}"
    ${elements}=    Get Webelements    jquery=.notifyjs-container
    Length Should Be    ${elements}    1    There is more than one error message.
    Page Should Not Contain Element    jquery=.notify-multi    There is more than one error message.

Close Error Message "${text}"
    Click    jquery=.notifyjs-container:contains("${text}") ~ .notify-close
    Wait Until Page Does Not Contain Element    jquery=.notifyjs-container:contains("${text}")

Click "${button}" In Modal Dialog
    Click    jquery=.modal.in button:contains("${button}")

Go to the Users page
    Click    jquery=.navbar a:contains(Administration)    1 s
    Click    jquery=.navbar a:contains(Users)    1 s
    "Users" View Should Be Open

Go to the Predefined Apps page
    Click    jquery=.navbar a:contains(Predefined Applications)
    "Predefined Apps" View Should Be Open

Go to the Settings page
    Click    jquery=.navbar a:contains(Settings)
    "Settings" View Should Be Open

Login as "${username}"
    Click    jquery=#userslist-table a:contains("${username}")
    Breadcrumb Should Contain "${username}"
    Click    jquery=button:contains(Login as this user)
    Click "Ok" In Modal Dialog

All pods should be "${status}"
    Wait Until Page Does Not Contain Element
    ...    jquery=#podlist-table tr td:nth-of-type(3):not(:contains(${status}))
